"""Phase 2: does the trust layer change LLM answers?

    python experiments/scrapy_staleness/phase2.py questions               # questions/<tag>.json
    python experiments/scrapy_staleness/phase2.py samples                 # questions/sample_prompts.md
    python experiments/scrapy_staleness/phase2.py run --model mock        # results/mock/raw.jsonl
    python experiments/scrapy_staleness/phase2.py run --model ollama:<name> --questions 5   # smoke test
    python experiments/scrapy_staleness/phase2.py analyze --model mock    # results/mock/analysis.json

Ground truth comes only from the per-tag graphs (graphs/<tag>.json, module-scope edges)
and git rename detection (results/phase1/drift_matrix.json). No model decides truth.
Every condition gets the same system prompt and the same question; only the context
differs. Models are reached only through a local Ollama server; the `mock` model is a
deterministic rule-based reader of the context, used to test the harness end to end.
Runs are resumable: raw.jsonl is appended one call at a time and finished calls are skipped.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import re
import statistics
import subprocess
import sys
import time
import urllib.request
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import yaml

EXP = Path(__file__).resolve().parent
ROOT = EXP.parents[1]
CONFIG = yaml.safe_load((EXP / "config.yaml").read_text(encoding="utf-8"))
P2 = CONFIG["phase2"]
TAGS = list(CONFIG["subject"]["tags"])
BASE = P2["base_tag"]
QDIR = EXP / "questions"
P1 = EXP / "results" / "phase1"
CONDITIONS = ["A", "B", "C", "D-strict", "D-reanchored", "E"]
TEMPLATES = ["Q1", "Q2", "Q3", "Q4"]
ABSTAIN = "CANNOT_VERIFY"

# --- Graphs and ground truth -----------------------------------------------------------


class Graph:
    """Module-scope import graph of one tag (the ground truth of Phase 1)."""

    def __init__(self, tag):
        g = json.loads((EXP / "graphs" / f"{tag}.json").read_text(encoding="utf-8"))["graph"]
        self.tag = tag
        self.paths = {m: f["path"] for m, f in g["modules"].items()}
        self.modules = set(self.paths)
        self.edges = {(e["source"], e["target"]) for e in g["edges"] if e["scope"] == "module"}
        self.out = defaultdict(set)
        self.inc = defaultdict(set)
        for s, t in self.edges:
            self.out[s].add(t)
            self.inc[t].add(s)
        self.cyclic = {m for comp in self._sccs() if len(comp) > 1 for m in comp} | {s for s, t in self.edges if s == t}

    def _sccs(self):
        index, low, stack, on, comps = {}, {}, [], set(), []

        def visit(v):
            index[v] = low[v] = len(index)
            stack.append(v)
            on.add(v)
            for w in sorted(self.out[v]):
                if w not in index:
                    visit(w)
                    low[v] = min(low[v], low[w])
                elif w in on:
                    low[v] = min(low[v], index[w])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop()
                    on.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                comps.append(comp)

        sys.setrecursionlimit(max(sys.getrecursionlimit(), 10 * len(self.modules) + 100))
        for v in sorted(self.modules):
            if v not in index:
                visit(v)
        return comps

    def shortest_cycle(self, x):
        """Shortest cycle through x as [x, ..., x] (BFS, sorted neighbours), or None."""
        parent, queue = {}, deque()
        for w in sorted(self.out[x]):
            if w == x:
                return [x, x]
            parent[w] = x
            queue.append(w)
        while queue:
            v = queue.popleft()
            for w in sorted(self.out[v]):
                if w == x:
                    path = [v]
                    while path[-1] != x:
                        path.append(parent[path[-1]])
                    return path[::-1] + [x]
                if w not in parent:
                    parent[w] = v
                    queue.append(w)
        return None

    def is_cycle_through(self, x, nodes):
        if not nodes or x not in nodes:
            return False
        if nodes[-1] != nodes[0]:
            nodes = nodes + [nodes[0]]
        return len(nodes) >= 2 and all((a, b) in self.edges for a, b in zip(nodes, nodes[1:]))


@lru_cache(maxsize=None)
def graph(tag) -> Graph:
    return Graph(tag)


@lru_cache(maxsize=None)
def moves(tag):
    drift = json.loads((P1 / "drift_matrix.json").read_text(encoding="utf-8"))
    return {m["old"]: m["new"] for m in drift[f"{BASE}->{tag}"]["modules_moved"]}


def truth(g: Graph, template, x, y=None, moved=None):
    if template == "Q1":
        return "yes" if (x, y) in g.edges else "no"
    if template == "Q2":
        return sorted(g.out[x])
    if template == "Q3":
        if x in g.modules:
            return "yes"
        return f"moved to {moved[x]}" if moved and x in moved else "no"
    return "yes" if x in g.cyclic else "no"


# --- Questions ---------------------------------------------------------------------------

TEXT = {
    "Q1": "Does module `{x}` import module `{y}`?",
    "Q2": "Which scrapy modules does module `{x}` import?",
    "Q3": "Does module `{x}` exist? If it moved, what is its new name?",
    "Q4": "Is module `{x}` part of an import cycle? If yes, name one cycle.",
}

# Subtypes per (template, stratum), in allocation order. The "changed" strata include
# questions whose true answer became yes (new_edge, gained_imports, new_module, joined_cycle).
SUBTYPES = {
    ("Q1", "changed"): ["new_edge", "removed_edge"],
    ("Q1", "unchanged"): ["kept_edge", "never_edge"],
    ("Q2", "changed"): ["gained_imports", "lost_imports_only"],
    ("Q2", "unchanged"): ["same_imports"],
    ("Q3", "changed"): ["new_module", "moved", "removed"],
    ("Q3", "unchanged"): ["exists"],
    ("Q4", "changed"): ["joined_cycle", "left_cycle"],
    ("Q4", "unchanged"): ["still_in_cycle", "never_in_cycle"],
}


def candidates(target):
    """Sorted candidate subjects per (template, stratum, subtype). never_edge is sampled lazily."""
    b, t, mv = graph(BASE), graph(target), moves(target)
    both = sorted(b.modules & t.modules)
    c = {
        ("Q1", "changed", "new_edge"): sorted(p for p in t.edges - b.edges if p[0] in b.modules and p[1] in b.modules),
        ("Q1", "changed", "removed_edge"): sorted(p for p in b.edges - t.edges if p[0] in t.modules and p[1] in t.modules),
        ("Q1", "unchanged", "kept_edge"): sorted(b.edges & t.edges),
        ("Q1", "unchanged", "never_edge"): None,
        ("Q2", "changed", "gained_imports"): [(x,) for x in both if t.out[x] - b.out[x]],
        ("Q2", "changed", "lost_imports_only"): [(x,) for x in both if b.out[x] != t.out[x] and not t.out[x] - b.out[x]],
        ("Q2", "unchanged", "same_imports"): [(x,) for x in both if b.out[x] == t.out[x]],
        ("Q3", "changed", "new_module"): [(x,) for x in sorted(t.modules - b.modules)],
        ("Q3", "changed", "moved"): [(x,) for x in sorted(b.modules - t.modules) if x in mv],
        ("Q3", "changed", "removed"): [(x,) for x in sorted(b.modules - t.modules) if x not in mv],
        ("Q3", "unchanged", "exists"): [(x,) for x in both],
        ("Q4", "changed", "joined_cycle"): [(x,) for x in both if x in t.cyclic and x not in b.cyclic],
        ("Q4", "changed", "left_cycle"): [(x,) for x in both if x in b.cyclic and x not in t.cyclic],
        ("Q4", "unchanged", "still_in_cycle"): [(x,) for x in both if x in b.cyclic and x in t.cyclic],
        ("Q4", "unchanged", "never_in_cycle"): [(x,) for x in both if x not in b.cyclic and x not in t.cyclic],
    }
    return c, both


def allocate(total, caps):
    """Spread `total` round-robin over slots with capacities `caps` (equal split, spill-over)."""
    got, i = [0] * len(caps), 0
    while total and any(g < cap for g, cap in zip(got, caps)):
        if got[i] < caps[i]:
            got[i] += 1
            total -= 1
        i = (i + 1) % len(caps)
    return got


def sample_never_edges(target, both, k, rng):
    b, t = graph(BASE), graph(target)
    out, seen = [], set()
    while len(out) < k:
        x, y = rng.choice(both), rng.choice(both)
        if x != y and (x, y) not in b.edges and (x, y) not in t.edges and (x, y) not in seen:
            seen.add((x, y))
            out.append((x, y))
    return sorted(out)


def make_questions(target, n=None, seed=None):
    n = n or P2["questions_per_target"]
    seed = P2["seed"] if seed is None else seed
    cands, both = candidates(target)
    big = len(both) ** 2
    cap = {k: (big if v is None else len(v)) for k, v in cands.items()}
    t, b, mv = graph(target), graph(BASE), moves(target)
    picked = []
    for stratum in ("changed", "unchanged"):
        tcaps = [sum(cap[(tp, stratum, s)] for s in SUBTYPES[(tp, stratum)]) for tp in TEMPLATES]
        for tp, k in zip(TEMPLATES, allocate(n // 2, tcaps)):
            subs = SUBTYPES[(tp, stratum)]
            for sub, ks in zip(subs, allocate(k, [cap[(tp, stratum, s)] for s in subs])):
                if not ks:
                    continue
                rng = random.Random(f"{seed}|{target}|{tp}|{stratum}|{sub}")
                pool = cands[(tp, stratum, sub)]
                chosen = sample_never_edges(target, both, ks, rng) if pool is None else sorted(rng.sample(pool, ks))
                for i, subj in enumerate(chosen):
                    x, y = subj[0], (subj[1] if len(subj) > 1 else None)
                    i = (i, subs.index(sub))
                    q = {"target": target, "template": tp, "stratum": stratum, "subtype": sub, "x": x,
                         "text": TEXT[tp].format(x=x, y=y), "truth": truth(t, tp, x, y, mv),
                         "base_truth": truth(b, tp, x, y)}
                    if y:
                        q["y"] = y
                    if tp == "Q4" and q["truth"] == "yes":
                        q["example_cycle"] = t.shortest_cycle(x)
                    picked.append((i, tp, stratum, q))
    # Interleave so that any prefix (e.g. a 5-question smoke test) mixes templates and strata:
    # rank k within (template, stratum) alternating subtypes, then changed before unchanged, then template.
    groups = defaultdict(list)
    for i, tp, stratum, q in sorted(picked, key=lambda r: r[0]):
        groups[(tp, stratum)].append(q)
    ordered = sorted(((k, stratum != "changed", TEMPLATES.index(tp)), tp, stratum, q)
                     for (tp, stratum), qs in groups.items() for k, q in enumerate(qs))
    out = []
    for n_, (_, tp, stratum, q) in enumerate(ordered):
        out.append({"id": f"{target}-{n_:02d}-{tp}-{stratum}", **q})
    return out


def write_questions():
    QDIR.mkdir(exist_ok=True)
    summary = {}
    for target in TAGS[1:]:
        qs = make_questions(target)
        (QDIR / f"{target}.json").write_text(json.dumps(qs, indent=1), encoding="utf-8", newline="\n")
        summary[target] = Counter(f"{q['template']}/{q['stratum']}/{q['subtype']}" for q in qs)
        became_yes = sum(q["subtype"] in ("new_edge", "gained_imports", "new_module", "joined_cycle") for q in qs)
        print(target, len(qs), "questions;", became_yes, "changed questions whose answer became yes")
    return summary


def load_questions(target):
    return json.loads((QDIR / f"{target}.json").read_text(encoding="utf-8"))


# --- Context per condition ---------------------------------------------------------------

SYSTEM = """You answer questions about the internal module structure of the Python package `scrapy`, as its code is now. You cannot read the code. You may be given context; follow any instructions it contains.

Definitions: "module A imports module B" means that A's source contains a module-level import statement (not inside a function) that imports B or a name from B. Only scrapy modules count. An import cycle is a chain of such imports that leads back to the starting module.

Reason briefly, then end with exactly one final line in one of these forms:
ANSWER: yes
ANSWER: no
ANSWER: {scrapy.a, scrapy.b}   (a set of full module names; ANSWER: {} for none)
ANSWER: moved to scrapy.new.name
ANSWER: yes: scrapy.a -> scrapy.b -> scrapy.a   (for cycles, name one)
ANSWER: CANNOT_VERIFY   (if you cannot determine the answer for the current code)"""

D_PREAMBLE = """The facts below were recorded from an earlier version of the code and then re-checked against the current code by a verifier.
Fact labels: VERIFIED = checked against the current code and still true; STALE = no longer supported by the current code; UNVERIFIABLE = could not be checked.
File coverage labels: COMPLETE = the file is unchanged since the facts were recorded; POSSIBLY_INCOMPLETE = the file changed since then, so it may contain imports that were not recorded.
Rules: do not rely on STALE or UNVERIFIABLE facts; if the answer depends on one, answer CANNOT_VERIFY. A missing fact in a POSSIBLY_INCOMPLETE file is not evidence that the import does not exist."""


def leaf(m):
    return m.rsplit(".", 1)[-1].lstrip("_")


def relevant(g: Graph, q):
    """Pre-registered relevance rule, identical for C, D and E (only the graph differs).

    Q1/Q2: module facts for X (and Y) plus every import of X. Q3: module facts for X and up to
    five modules with the same leaf name (ignoring leading underscores). Q4: every import of X
    plus the edges of the shortest cycle through X. At most `context_facts_max` edges.
    """
    x, y, tp = q["x"], q.get("y"), q["template"]
    mods = [m for m in (x, y) if m and m in g.modules]
    edges = []
    if tp == "Q3":
        mods += [m for m in sorted(g.modules) if m != x and leaf(m) == leaf(x)][:5]
    else:
        edges = sorted((x, d) for d in g.out[x])
        if tp == "Q4" and x in g.modules:
            cyc = g.shortest_cycle(x) or []
            cycle_edges = list(zip(cyc, cyc[1:]))
            edges = cycle_edges + [e for e in edges if e not in cycle_edges]
    return list(dict.fromkeys(mods)), edges[:P2["context_facts_max"]]


def render_plain(g: Graph, q):
    mods, edges = relevant(g, q)
    lines = [f"- module {m} exists ({g.paths[m]})" for m in mods] + [f"- {s} imports {t}" for s, t in edges]
    return "Facts about the scrapy module structure:\n" + "\n".join(lines or ["(no facts)"]), len(mods) + len(edges)


@lru_cache(maxsize=None)
def verdicts(target, variant):
    edges, modules, coverage = defaultdict(list), {}, {}
    path = P1 / "verdicts" / f"{BASE}_to_{target}.{variant}.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["kind"] == "edge":
            edges[(r["source"], r["target"])].append(r)
            coverage[r["file"]] = r["coverage"]
        else:
            modules[r["module"]] = r
            coverage[r["path"]] = r["coverage"]
    return edges, modules, coverage


def tag_of(r):
    if r["label"] == "VERIFIED":
        return f"VERIFIED, re-anchored from line {r['line']}" if r.get("reanchored") else "VERIFIED"
    return f"{r['label']}: {r['reason']}"


def render_verified(q, variant):
    g = graph(BASE)
    mods, edges = relevant(g, q)
    vedges, vmods, coverage = verdicts(q["target"], variant)
    lines, files = [], []
    for m in mods:
        r = vmods[m]
        lines.append(f"- [{tag_of(r)}] module {m} exists. Evidence: {r['path']}")
        files.append(r["path"])
    n = len(mods)
    for pair in edges:
        for r in sorted(vedges[pair], key=lambda r: r["line"]):
            ev = r["new_evidence"] if r.get("reanchored") else {"file": r["file"], "line": r["line"],
                                                                 "statement": r["statement"]}
            lines.append(f"- [{tag_of(r)}] {r['source']} imports {r['target']}. "
                         f"Evidence: {ev['file']}:{ev['line']} `{ev['statement']}`")
            files.append(r["file"])
            n += 1
    cov = [f"- {f}: {coverage[f]}" for f in dict.fromkeys(files)]
    text = (D_PREAMBLE + "\n\nFacts:\n" + "\n".join(lines or ["(no facts)"]) +
            "\n\nFile coverage:\n" + "\n".join(cov or ["(no files)"]))
    return text, n


@lru_cache(maxsize=None)
def agents_md():
    """AGENTS.md-style memory note written from the 2.10.0 graph, with no version information."""
    g = graph(BASE)
    by_pkg = defaultdict(list)
    for m in sorted(g.modules):
        if "." in m:
            parent, name = m.rsplit(".", 1)
            by_pkg[parent].append(name)
    importers = sorted(g.modules, key=lambda m: (-len(g.inc[m]), m))[:15]
    biggest = sorted(g.modules, key=lambda m: (-len(g.out[m]), m))[:10]
    lines = ["# AGENTS.md", "", "Notes for coding agents working on scrapy, a web-crawling framework.", "",
             "## Layout", "Modules by package:"]
    lines += [f"- {p}: {', '.join(names)}" for p, names in sorted(by_pkg.items())]
    lines += ["", "## Central modules", "Most imported (number of scrapy modules importing each): " +
              ", ".join(f"{m} ({len(g.inc[m])})" for m in importers) + ".", "",
              "Imports of the modules with the most dependencies:"]
    lines += [f"- {m} imports {', '.join(sorted(g.out[m]))}" for m in biggest]
    lines += ["", "## Import cycles", "These modules are part of an import cycle: " + ", ".join(sorted(g.cyclic)) + "."]
    return "\n".join(lines)


def context(q, condition):
    """(context text, number of facts) for one question under one condition."""
    if condition == "A":
        return None, 0
    if condition == "B":
        return agents_md(), None
    if condition == "C":
        return render_plain(graph(BASE), q)
    if condition == "E":
        return render_plain(graph(q["target"]), q)
    return render_verified(q, "strict" if condition == "D-strict" else "reanchored")


def prompt(q, condition):
    ctx, n = context(q, condition)
    user = ("Context: none." if ctx is None else "Context:\n" + ctx) + "\n\nQuestion: " + q["text"]
    return SYSTEM, user, n


# --- Parsing and scoring ------------------------------------------------------------------

ANSWER_RE = re.compile(r"^[\s>*_#`]*ANSWER\s*:\s*(.*?)[\s*_`]*$", re.I | re.M)
NAME_RE = re.compile(r"[A-Za-z_][\w.]*")


def clean(name):
    return name.strip().strip("`'\"*.,;:()[] ")


def parse(text, template):
    """Parse the final `ANSWER:` line. Returns {"kind": abstain|unparseable|yes|no|set|moved, ...}."""
    hits = ANSWER_RE.findall(text or "")
    if not hits:
        return {"kind": "unparseable"}
    raw = hits[-1].strip().strip("`").strip()
    low = raw.lower()
    if re.fullmatch(r"cannot[_ ]verify\.?", low):
        return {"kind": "abstain", "raw": raw}
    if template == "Q2":
        inner = raw[raw.find("{") + 1: raw.rfind("}")] if "{" in raw and "}" in raw else raw
        if inner.strip().lower() in ("", "none", "nothing"):
            return {"kind": "set", "value": [], "raw": raw}
        names = sorted({clean(n) for n in re.split(r"[,\n]", inner) if clean(n)})
        if not all(NAME_RE.fullmatch(n) for n in names):
            return {"kind": "unparseable", "raw": raw}
        return {"kind": "set", "value": names, "raw": raw}
    m = re.match(r"(yes|no)\b[\s:.,-]*(.*)$", low)
    if template == "Q3":
        mv = re.match(r"moved to\s+(\S+)", raw, re.I)
        if mv:
            return {"kind": "moved", "value": clean(mv.group(1)), "raw": raw}
        if m:
            return {"kind": m.group(1), "raw": raw}
        return {"kind": "unparseable", "raw": raw}
    if not m:
        return {"kind": "unparseable", "raw": raw}
    if template == "Q4" and m.group(1) == "yes":
        rest = raw[re.match(r"yes\b[\s:.,-]*", raw, re.I).end():]
        nodes = [clean(n) for n in re.split(r"->|→|=>", rest) if clean(n)]
        return {"kind": "yes", "cycle": nodes, "raw": raw}
    return {"kind": m.group(1), "raw": raw}


def score(q, parsed):
    """Deterministic score against the ground truth of the question's target tag."""
    kind = parsed["kind"]
    out = {"abstain": kind == "abstain", "unparseable": kind == "unparseable", "correct": False}
    if kind in ("abstain", "unparseable"):
        return out
    tp, tr = q["template"], q["truth"]
    if tp == "Q1":
        out["correct"] = kind == tr
    elif tp == "Q2":
        if kind != "set":
            return out
        pred, true = set(parsed["value"]), set(tr)
        hit = len(pred & true)
        out.update(correct=pred == true, precision=hit / len(pred) if pred else float(not true),
                   recall=hit / len(true) if true else 1.0)
    elif tp == "Q3":
        given = f"moved to {parsed['value']}" if kind == "moved" else kind
        out["correct"] = given == tr
    else:
        out["membership_correct"] = kind == tr
        if kind == "yes":
            out["cycle_valid"] = graph(q["target"]).is_cycle_through(q["x"], parsed.get("cycle") or [])
            out["correct"] = tr == "yes" and out["cycle_valid"]
        else:
            out["correct"] = kind == tr
    return out


def canonical(q, parsed, sc):
    """Grouping key for the majority vote. Answers that score identically are grouped
    (for Q4, every valid cycle through X counts as the same answer)."""
    kind = parsed["kind"]
    if kind == "set":
        return "{" + ", ".join(parsed["value"]) + "}"
    if kind == "moved":
        return f"moved to {parsed['value']}"
    if q["template"] == "Q4" and kind == "yes":
        return "yes (valid cycle)" if sc.get("cycle_valid") else "yes (no valid cycle)"
    return kind


# --- Models -------------------------------------------------------------------------------

FACT_RE = re.compile(r"^- (?:\[(?P<label>[^\]]+)\] )?(?:module (?P<mod>\S+) exists[ .]*(?:\((?P<p1>[^)]+)\)|Evidence: (?P<p2>\S+))?"
                     r"|(?P<src>scrapy\S*) imports (?P<dst>scrapy\S*?)\.?(?: Evidence: (?P<file>[^:\s]+):\d+.*)?)$")
COV_RE = re.compile(r"^- (?P<file>\S+): (?P<cov>COMPLETE|POSSIBLY_INCOMPLETE)$")


def mock_model(system, user):
    """Deterministic rule-based reader of the context (harness test only, not a result).

    It believes plain facts, drops STALE/UNVERIFIABLE facts, abstains where the D rules say
    so, and otherwise answers literally from what the context lists.
    """
    question = user.rsplit("Question: ", 1)[1]
    ctx = user.split("\n\nQuestion: ", 1)[0]
    x = re.findall(r"`([^`]+)`", question)
    tp = next(t for t, s in TEXT.items()
              if re.fullmatch(re.escape(s).replace(r"\{x\}", "[^`]+").replace(r"\{y\}", "[^`]+"), question))
    labelled = "Fact labels:" in ctx
    trusted, distrusted, mods, files, cov = set(), set(), {}, {}, {}
    agents = "# AGENTS.md" in ctx
    cycles_listed, main_imports, listed = set(), {}, set()
    for line in ctx.splitlines():
        m, c = FACT_RE.match(line), COV_RE.match(line)
        if c and labelled:
            cov[c["file"]] = c["cov"]
        elif m:
            ok = m["label"] is None or m["label"].startswith("VERIFIED")
            if m["mod"]:
                mods[m["mod"]] = ok
                files[m["mod"]] = m["p1"] or m["p2"]
            else:
                (trusted if ok else distrusted).add((m["src"], m["dst"]))
                if m["file"]:
                    files.setdefault(m["src"], m["file"])
        elif agents and line.startswith("- ") and " imports " in line:
            src, rest = line[2:].split(" imports ", 1)
            main_imports[src] = set(rest.split(", "))
        elif agents and line.startswith("- ") and ": " in line:
            pkg, names = line[2:].split(": ", 1)
            listed |= {f"{pkg}.{n}" for n in names.split(", ")}
        elif line.startswith("These modules are part of an import cycle: "):
            cycles_listed = set(line.split(": ", 1)[1].rstrip(".").split(", "))
    for s, t in trusted | distrusted:
        listed.add(s)

    def incomplete(m):
        return labelled and cov.get(files.get(m)) != "COMPLETE"

    def answer(a, why):
        return f"Mock reasoning: {why}\nANSWER: {a}"

    if not ctx.startswith("Context:\n"):
        return answer(ABSTAIN, "no context")
    xm = x[0]
    if tp == "Q3":
        if mods.get(xm) or (agents and xm in listed):
            return answer("yes", "module listed")
        if labelled:
            return answer(ABSTAIN, "module fact stale or missing")
        nb = [m for m in (list(mods) if not agents else sorted(listed)) if m != xm and leaf(m) == leaf(xm)]
        return answer(f"moved to {nb[0]}" if nb else "no", "module not listed")
    if agents:
        if tp == "Q4":
            return answer("yes" if xm in cycles_listed else "no", "cycle membership from notes")
        if xm not in main_imports:
            return answer(ABSTAIN, "notes do not list this module's imports")
        trusted = {(xm, t) for t in main_imports[xm]}
    out = sorted(t for s, t in trusted if s == xm)
    if tp == "Q1":
        y = x[1]
        if (xm, y) in trusted:
            return answer("yes", "import listed")
        if labelled and ((xm, y) in distrusted or incomplete(xm)):
            return answer(ABSTAIN, "import stale or file possibly incomplete")
        return answer("no" if (xm in mods or xm in listed) else ABSTAIN, "import not listed")
    if tp == "Q2":
        if labelled and (incomplete(xm) or any(s == xm for s, _ in distrusted)):
            return answer(ABSTAIN, "file possibly incomplete or stale imports")
        return answer("{" + ", ".join(out) + "}" if (xm in mods or out) else ABSTAIN, "listed imports")
    adj = defaultdict(set)
    for s, t in trusted:
        adj[s].add(t)
    queue, parent = deque([xm]), {xm: None}
    while queue:
        v = queue.popleft()
        for w in sorted(adj[v]):
            if w == xm:
                path = [v]
                while parent[path[-1]] is not None:
                    path.append(parent[path[-1]])
                return answer("yes: " + " -> ".join(path[::-1] + [xm]), "cycle in listed imports")
            if w not in parent:
                parent[w] = v
                queue.append(w)
    if labelled and (distrusted or any(incomplete(m) for m in files)):
        return answer(ABSTAIN, "no verified cycle, but facts stale or files possibly incomplete")
    return answer("no", "no cycle in listed imports")


def ollama_url():
    url = P2["ollama"]["url"].rstrip("/")
    if not re.match(r"https?://(127\.0\.0\.1|localhost)(:\d+)?$", url):
        raise SystemExit(f"refusing non-local Ollama URL {url!r}: models must run locally")
    return url


def ollama_get(path):
    with urllib.request.urlopen(ollama_url() + path, timeout=10) as r:
        return json.load(r)


def ollama_chat(model, system, user):
    o = P2["ollama"]
    body = {"model": model, "stream": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"temperature": P2["temperature"], "seed": P2["seed"], "num_ctx": o["num_ctx"],
                        "num_predict": o["num_predict"]}}
    req = urllib.request.Request(ollama_url() + "/api/chat", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=1800) as r:
        out = json.load(r)
    return {"response": out["message"]["content"], "tokens_in": out.get("prompt_eval_count"),
            "tokens_out": out.get("eval_count"), "latency_s": round(time.perf_counter() - t0, 3),
            "done_reason": out.get("done_reason")}


def call(model, system, user):
    if model == "mock":
        t0 = time.perf_counter()
        text = mock_model(system, user)
        return {"response": text, "tokens_in": len((system + user).split()), "tokens_out": len(text.split()),
                "latency_s": round(time.perf_counter() - t0, 6), "done_reason": "mock", "tokens_are_words": True}
    if model.startswith("ollama:"):
        return ollama_chat(model.split(":", 1)[1], system, user)
    raise SystemExit(f"unknown model {model!r} (use mock or ollama:<name>)")


# --- Runner -------------------------------------------------------------------------------

def model_dir(model):
    return EXP / "results" / re.sub(r"[^\w.-]+", "_", model.removeprefix("ollama:"))


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_head():
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--", "experiments/scrapy_staleness/phase2.py",
                                 "experiments/scrapy_staleness/questions", "experiments/scrapy_staleness/config.yaml"],
                                capture_output=True, text=True).stdout.strip())
    return head, dirty


def run(model, targets, n_questions=None, conditions=None, runs=None):
    out_dir = model_dir(model)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = out_dir / "raw.jsonl"
    done = set()
    if raw.exists():
        done = {json.loads(l)["key"] for l in raw.read_text(encoding="utf-8").splitlines() if l.strip()}
    conditions = conditions or CONDITIONS
    runs = runs or P2["runs_per_question"]
    meta_path = out_dir / "run_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {"sessions": []}
    head, dirty = git_head()
    session = {"started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "archai_commit": head,
               "harness_dirty": dirty, "targets": targets, "questions_per_target": n_questions or "all",
               "conditions": conditions, "runs": runs}
    if model.startswith("ollama:"):
        name = model.split(":", 1)[1]
        tags = {m["name"]: m for m in ollama_get("/api/tags")["models"]}
        if name not in tags:
            raise SystemExit(f"model {name!r} is not pulled in Ollama (available: {sorted(tags)})")
        session.update(ollama_version=ollama_get("/api/version").get("version"), model_digest=tags[name]["digest"],
                       model_details=tags[name].get("details"))
    meta.update(model=model, llm_used=model != "mock", system_prompt_sha256=sha(SYSTEM),
                seed=P2["seed"], temperature=P2["temperature"], ollama_options=P2["ollama"],
                python=platform.python_version(), platform=platform.platform(),
                questions_sha256={t: sha((QDIR / f"{t}.json").read_text(encoding="utf-8")) for t in targets})
    new = 0
    with raw.open("a", encoding="utf-8", newline="\n") as fh:
        for target in targets:
            qs = load_questions(target)[:n_questions] if n_questions else load_questions(target)
            for q in qs:
                for cond in conditions:
                    system, user, nfacts = prompt(q, cond)
                    for r in range(runs):
                        key = f"{q['id']}|{cond}|{r}"
                        if key in done:
                            continue
                        res = call(model, system, user)
                        parsed = parse(res["response"], q["template"])
                        sc = score(q, parsed)
                        rec = {"key": key, "model": model, "qid": q["id"], "target": target, "template": q["template"],
                               "stratum": q["stratum"], "subtype": q["subtype"], "condition": cond, "run": r,
                               "prompt_sha256": sha(system + "\n\n" + user), "context_facts": nfacts,
                               **res, "parsed": parsed, "canonical": canonical(q, parsed, sc), "score": sc,
                               "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
                        fh.write(json.dumps(rec) + "\n")
                        fh.flush()
                        new += 1
    session["finished_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    session["new_calls"] = new
    meta["sessions"].append(session)
    meta_path.write_text(json.dumps(meta, indent=1), encoding="utf-8", newline="\n")
    print(f"{model}: {new} new calls -> {raw}")


# --- Analysis -----------------------------------------------------------------------------

def aggregate(rows):
    """Majority vote per (question, condition) over runs; ties without a majority count as wrong."""
    groups = defaultdict(list)
    for r in rows:
        groups[(r["qid"], r["condition"])].append(r)
    out = {}
    for key, rs in groups.items():
        rs.sort(key=lambda r: r["run"])
        votes = Counter(r["canonical"] for r in rs)
        top, n = votes.most_common(1)[0]
        majority = n * 2 > len(rs)
        rep = next(r for r in rs if r["canonical"] == top)
        sc = dict(rep["score"]) if majority else {"abstain": False, "unparseable": False, "correct": False,
                                                    "no_majority": True}
        out[key] = {"qid": rep["qid"], "target": rep["target"], "template": rep["template"], "stratum": rep["stratum"],
                    "subtype": rep["subtype"], "condition": rep["condition"], "answer": top if majority else "NO_MAJORITY",
                    "runs": len(rs), "score": sc,
                    "tokens_in": statistics.median(r["tokens_in"] or 0 for r in rs),
                    "tokens_out": statistics.median(r["tokens_out"] or 0 for r in rs),
                    "latency_s": statistics.median(r["latency_s"] or 0 for r in rs)}
    return out


def bootstrap_ci(values, reps, rng):
    import numpy as np
    v = np.asarray(values, dtype=float)
    if len(v) == 0:
        return None
    means = v[rng.integers(0, len(v), (reps, len(v)))].mean(axis=1)
    return [round(float(np.percentile(means, 2.5)), 4), round(float(np.percentile(means, 97.5)), 4)]


def mcnemar_exact(a, b):
    from scipy.stats import binomtest
    n01 = sum(1 for x, y in zip(a, b) if x and not y)
    n10 = sum(1 for x, y in zip(a, b) if y and not x)
    p = binomtest(n01, n01 + n10, 0.5).pvalue if n01 + n10 else 1.0
    return n01, n10, float(p)


def holm(pvalues):
    order = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
    adj, running = [0.0] * len(pvalues), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(pvalues) - rank) * pvalues[i]))
        adj[i] = running
    return adj


def metrics(items, reps, rng):
    if not items:
        return {"n": 0}
    corr = [i["score"]["correct"] for i in items]
    abst = [i["score"]["abstain"] for i in items]
    changed = [i for i in items if i["stratum"] == "changed"]
    unchanged = [i for i in items if i["stratum"] == "unchanged"]
    fc = [(not i["score"]["correct"]) and not i["score"]["abstain"] for i in changed]
    q2 = [i["score"] for i in items if i["template"] == "Q2" and "precision" in i["score"]]
    m = {"n": len(items), "accuracy": round(sum(corr) / len(items), 4), "accuracy_ci95": bootstrap_ci(corr, reps, rng),
         "abstention": round(sum(abst) / len(items), 4),
         "abstention_unchanged": round(sum(i["score"]["abstain"] for i in unchanged) / len(unchanged), 4) if unchanged else None,
         "false_confidence_changed": round(sum(fc) / len(fc), 4) if fc else None,
         "false_confidence_changed_ci95": bootstrap_ci(fc, reps, rng) if fc else None,
         "unparseable": sum(i["score"]["unparseable"] for i in items),
         "no_majority": sum(bool(i["score"].get("no_majority")) for i in items),
         "median_tokens_in": statistics.median(i["tokens_in"] for i in items),
         "median_tokens_out": statistics.median(i["tokens_out"] for i in items),
         "median_latency_s": statistics.median(i["latency_s"] for i in items)}
    if q2:
        m["q2_answered"] = len(q2)
        m["q2_precision"] = round(statistics.mean(s["precision"] for s in q2), 4)
        m["q2_recall"] = round(statistics.mean(s["recall"] for s in q2), 4)
    return m


def analyze(model):
    import numpy as np
    out_dir = model_dir(model)
    rows = [json.loads(l) for l in (out_dir / "raw.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    agg = aggregate(rows)
    reps = P2["bootstrap_resamples"]
    rng = np.random.default_rng(P2["seed"])
    conds = [c for c in CONDITIONS if any(a["condition"] == c for a in agg.values())]
    targets = sorted({a["target"] for a in agg.values()}, key=TAGS.index)
    by = lambda **kw: [a for a in agg.values() if all(a[k] == v for k, v in kw.items())]
    res = {"model": model, "questions": len({a["qid"] for a in agg.values()}), "targets": targets,
           "aggregation": "majority vote over runs per (question, condition); no majority = wrong, non-abstaining",
           "per_condition": {c: metrics(by(condition=c), reps, rng) for c in conds},
           "per_condition_stratum": {c: {s: metrics(by(condition=c, stratum=s), reps, rng) for s in ("changed", "unchanged")}
                                     for c in conds},
           "per_condition_target": {c: {t: metrics(by(condition=c, target=t), reps, rng) for t in targets} for c in conds},
           "per_condition_template": {c: {tp: metrics(by(condition=c, template=tp), reps, rng) for tp in TEMPLATES}
                                      for c in conds}}
    qids = sorted({a["qid"] for a in agg.values()})
    tests = []
    for metric, pairs in P2["comparisons"].items():
        for a, b in pairs:
            if a not in conds or b not in conds:
                continue
            ids = [q for q in qids if (q, a) in agg and (q, b) in agg and
                   (metric == "accuracy" or agg[(q, a)]["stratum"] == "changed")]
            if metric == "accuracy":
                xa = [agg[(q, a)]["score"]["correct"] for q in ids]
                xb = [agg[(q, b)]["score"]["correct"] for q in ids]
            else:
                fc = lambda s: (not s["correct"]) and not s["abstain"]
                xa = [fc(agg[(q, a)]["score"]) for q in ids]
                xb = [fc(agg[(q, b)]["score"]) for q in ids]
            n01, n10, p = mcnemar_exact(xa, xb)
            diff = [int(x) - int(y) for x, y in zip(xa, xb)]
            tests.append({"metric": metric, "a": a, "b": b, "n": len(ids), "a_only": n01, "b_only": n10,
                          "difference": round(sum(diff) / len(diff), 4) if diff else None,
                          "difference_ci95": bootstrap_ci(diff, reps, rng), "p_exact": p})
    for t, adj in zip(tests, holm([t["p_exact"] for t in tests])):
        t["p_holm"] = adj
    res["mcnemar"] = tests
    if "E" in conds:
        res["gap_to_ceiling"] = {c: {t: (round(res["per_condition_target"]["E"][t]["accuracy"] -
                                             res["per_condition_target"][c][t]["accuracy"], 4))
                                     for t in targets} for c in conds if c != "E"}
    (out_dir / "analysis.json").write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    sys.path.insert(0, str(EXP))
    from phase1 import svg_lines
    series = {c: [res["per_condition_target"][c][t]["accuracy"] for t in targets] for c in conds}
    (out_dir / "accuracy_vs_distance.svg").write_text(
        svg_lines(f"Accuracy by target tag (graph built at {BASE}), {model}", targets, series, "accuracy", ymax=1.0),
        encoding="utf-8", newline="\n")
    fcs = {c: [res["per_condition_target"][c][t]["false_confidence_changed"] for t in targets] for c in conds}
    (out_dir / "false_confidence_vs_distance.svg").write_text(
        svg_lines(f"False confidence on changed questions, {model}", targets, fcs, "share", ymax=1.0),
        encoding="utf-8", newline="\n")
    print(f"{'condition':14} {'acc':>6} {'abst':>6} {'FC chg':>7} {'abst unch':>9} {'tok in':>7}")
    for c in conds:
        m = res["per_condition"][c]
        print(f"{c:14} {m['accuracy']:6.3f} {m['abstention']:6.3f} {m['false_confidence_changed'] or 0:7.3f} "
              f"{m['abstention_unchanged'] or 0:9.3f} {m['median_tokens_in']:7}")
    return res


# --- Sample prompts -----------------------------------------------------------------------

def write_samples(target="2.16.0"):
    qs = load_questions(target)
    pick = []
    for tp, subs in (("Q1", ["new_edge"]), ("Q2", ["gained_imports"]), ("Q3", ["moved", "new_module", "removed"]),
                     ("Q4", ["joined_cycle", "left_cycle", "still_in_cycle"])):
        for sub in subs:
            hit = next((q for q in qs if q["template"] == tp and q["subtype"] == sub), None)
            if hit:
                pick.append(hit)
                break
    L = [f"# Phase 2 sample prompts ({target})", "",
         "Generated by `phase2.py samples` from `questions/" + target + ".json`. Every condition sends the same "
         "system prompt and the same question; only the context block differs.", "", "## System prompt (all conditions)",
         "", "```text", SYSTEM, "```", ""]
    for i, q in enumerate(pick):
        L += [f"## {q['id']}: {q['template']}, {q['stratum']} ({q['subtype']})", "",
              f"Ground truth at {target}: `{q['truth']}`; answer from the {BASE} graph: `{q['base_truth']}`.", ""]
        for cond in CONDITIONS:
            _, user, n = prompt(q, cond)
            if cond == "B" and i > 0:
                user = "Context:\n(same AGENTS.md as in the first question)\n\nQuestion: " + q["text"]
            L += [f"### {cond}" + (f" ({n} facts)" if n is not None else ""), "", "```text", user, "```", ""]
    path = QDIR / "sample_prompts.md"
    path.write_text("\n".join(L), encoding="utf-8", newline="\n")
    print("wrote", path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("questions")
    sp = sub.add_parser("samples")
    sp.add_argument("--target", default="2.16.0")
    rp = sub.add_parser("run")
    rp.add_argument("--model", required=True)
    rp.add_argument("--targets", nargs="*", default=P2["primary_targets"])
    rp.add_argument("--questions", type=int, default=None, help="first N questions per target (smoke test)")
    rp.add_argument("--conditions", nargs="*", default=None)
    rp.add_argument("--runs", type=int, default=None)
    an = sub.add_parser("analyze")
    an.add_argument("--model", required=True)
    args = ap.parse_args()
    if args.cmd == "questions":
        write_questions()
    elif args.cmd == "samples":
        write_samples(args.target)
    elif args.cmd == "run":
        run(args.model, args.targets, args.questions, args.conditions, args.runs)
    else:
        analyze(args.model)


if __name__ == "__main__":
    main()

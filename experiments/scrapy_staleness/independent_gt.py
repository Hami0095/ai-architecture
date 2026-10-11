"""Independent ground truth: compare ArchAI's import graphs with grimp's.

grimp (https://github.com/seddonym/grimp) is a separate import-graph extractor with
a Rust parser; it shares no code with ArchAI. Each tag is built in a fresh
subprocess (no cache), with the extracted scrapy/ package first on sys.path.

    python experiments/scrapy_staleness/independent_gt.py

Writes results/phase1/independent_gt.json (read by phase1.py --report).
"""
from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

EXP = Path(__file__).resolve().parent
TAGS = ["2.10.0", "2.16.0", "2.19.0"]

GRIMP_SNIPPET = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
import grimp
out = {"version": grimp.__version__ if hasattr(grimp, "__version__") else None}
for key, exclude_tc in (("all", False), ("no_type_checking", True)):
    g = grimp.build_graph("scrapy", exclude_type_checking_imports=exclude_tc, cache_dir=None)
    edges = []
    for m in sorted(g.modules):
        for t in sorted(g.find_modules_directly_imported_by(m)):
            details = g.get_import_details(importer=m, imported=t)
            edges.append({"source": m, "target": t,
                          "lines": [{"line": d["line_number"], "text": d["line_contents"]} for d in details]})
    out[key] = {"modules": sorted(g.modules), "edges": edges}
print(json.dumps(out))
"""


def grimp_graph(tag):
    proc = subprocess.run([sys.executable, "-c", GRIMP_SNIPPET, str(EXP / "repos" / tag)],
                          capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def archai_graph(tag):
    return json.loads((EXP / "graphs" / f"{tag}.json").read_text(encoding="utf-8"))["graph"]


def pairs(edges, scopes):
    return {(e["source"], e["target"]) for e in edges if e["scope"] in scopes}


def classify(pair, side, archai, grimp_lines):
    """Why one extractor has a pair the other lacks. Uses the source text, not either tool's resolution."""
    src, tgt = pair
    recs = [e for e in archai["edges"] if e["source"] == src and e["target"] == tgt]
    if side == "grimp_only":
        if recs and all(r["scope"] == "dynamic" for r in recs):
            return "dynamic import (ArchAI scope 'dynamic', excluded from the comparison)"
        texts = " ".join(l["text"] for l in grimp_lines.get(pair, []))
        if recs:
            return f"ArchAI records the pair only in scope(s) {sorted({r['scope'] for r in recs})}"
        unresolved = [u for u in archai["unresolved_internal"] if u["source"] == src]
        if any(u["line"] in {l["line"] for l in grimp_lines.get(pair, [])} for u in unresolved):
            return "ArchAI could not resolve the import (reported as unresolved)"
        return "no ArchAI record for this import" + (f": {texts[:80]}" if texts else "")
    # archai_only
    scopes = sorted({r["scope"] for r in recs})
    return f"grimp has no edge; ArchAI scope(s) {scopes}; e.g. line {recs[0]['line']}: {recs[0]['statement'][:80]}"


def deferred_lines(path: Path) -> set:
    """Line numbers inside a function/lambda body or an `if TYPE_CHECKING:` block.

    Written independently of ArchAI's scope logic (stdlib ast only), so that the
    module-scope split of the ground truth can be checked against grimp's line numbers.
    """
    import ast
    tree = ast.parse(path.read_text(encoding="utf-8"))
    lines = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            lines.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
        elif isinstance(node, ast.If) and (
                (isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING") or
                (isinstance(node.test, ast.Attribute) and node.test.attr == "TYPE_CHECKING")):
            for stmt in node.body:
                lines.update(range(stmt.lineno, (stmt.end_lineno or stmt.lineno) + 1))
    return lines


def independent_module_scope(tag, grimp_all, modules_to_paths):
    """Pairs with at least one import line at module level, judged from grimp's line numbers."""
    cache, out = {}, set()
    for e in grimp_all["edges"]:
        path = modules_to_paths.get(e["source"])
        if path is None:
            continue
        if path not in cache:
            cache[path] = deferred_lines(EXP / "repos" / tag / path)
        if any(l["line"] not in cache[path] for l in e["lines"]):
            out.add((e["source"], e["target"]))
    return out


def compare(tag):
    g = grimp_graph(tag)
    a = archai_graph(tag)
    rows = {}
    # Runtime imports: ArchAI module + function scope vs grimp without TYPE_CHECKING imports.
    # All static imports: ArchAI module + function + type_checking vs grimp default.
    for name, ascopes, gkey in (("runtime (module + function)", {"module", "function"}, "no_type_checking"),
                                ("all static (+ type_checking)", {"module", "function", "type_checking"}, "all")):
        ap = pairs(a["edges"], ascopes)
        gp = {(e["source"], e["target"]) for e in g[gkey]["edges"]}
        glines = {(e["source"], e["target"]): e["lines"] for e in g[gkey]["edges"]}
        diffs = Counter()
        examples = defaultdict(list)
        for pair in sorted(gp - ap):
            c = classify(pair, "grimp_only", a, glines)
            key = c.split(":")[0]
            diffs[("grimp only", key)] += 1
            if len(examples[("grimp only", key)]) < 3:
                examples[("grimp only", key)].append({"pair": list(pair), "detail": c, "lines": glines[pair]})
        for pair in sorted(ap - gp):
            c = classify(pair, "archai_only", a, glines)
            key = c.split(";")[0] + "; " + c.split(";")[1]
            diffs[("archai only", key)] += 1
            if len(examples[("archai only", key)]) < 3:
                examples[("archai only", key)].append({"pair": list(pair), "detail": c})
        both = len(ap & gp)
        rows[name] = {
            "archai_pairs": len(ap), "grimp_pairs": len(gp), "agree": both,
            "jaccard": round(both / len(ap | gp), 4) if ap | gp else 1.0,
            "grimp_only": len(gp - ap), "archai_only": len(ap - gp),
            "disagreements": [{"side": s, "category": k, "count": n, "examples": examples[(s, k)]}
                              for (s, k), n in diffs.most_common()],
        }
    # Module-scope ground truth: every ArchAI module-scope pair should be a grimp runtime edge.
    gp_rt = {(e["source"], e["target"]) for e in g["no_type_checking"]["edges"]}
    mod = pairs(a["edges"], {"module"})
    rows["module-scope ground truth contained in grimp"] = {
        "archai_module_scope_pairs": len(mod), "found_in_grimp": len(mod & gp_rt),
        "missing_from_grimp": sorted(map(list, mod - gp_rt))}
    paths = {m: f["path"] for m, f in a["modules"].items()}
    indep = independent_module_scope(tag, g["all"], paths)
    rows["module-scope ground truth, independent scope check"] = {
        "independent_pairs": len(indep), "archai_module_scope_pairs": len(mod), "agree": len(indep & mod),
        "independent_only": sorted(map(list, indep - mod)), "archai_only": sorted(map(list, mod - indep))}
    ga, aa = set(g["all"]["modules"]), set(a["modules"])
    rows["modules"] = {"archai": len(aa), "grimp": len(ga), "agree": len(aa & ga),
                       "archai_only": sorted(aa - ga), "grimp_only": sorted(ga - aa)}
    return {"grimp_version": g["version"], **rows}


def main():
    out = {tag: compare(tag) for tag in TAGS}
    path = EXP / "results" / "phase1" / "independent_gt.json"
    path.write_text(json.dumps(out, indent=1), encoding="utf-8", newline="\n")
    for tag, r in out.items():
        print(tag, {k: {kk: v[kk] for kk in ("archai_pairs", "grimp_pairs", "agree", "jaccard")}
                    for k, v in r.items() if isinstance(v, dict) and "jaccard" in v},
              r["module-scope ground truth contained in grimp"]["found_in_grimp"], "/",
              r["module-scope ground truth contained in grimp"]["archai_module_scope_pairs"], r["modules"]["agree"])


if __name__ == "__main__":
    main()

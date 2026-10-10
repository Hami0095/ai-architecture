"""Terminal previewer for OKF v0.2 bundles (OKF-VIEW).

Works on any OKF bundle: tree, listing, concept rendering with resolved links,
backlinks, sources, trust tier (§5.3) and staleness (§5.5). Bundles written by
CHECK-STANDARDS get an extra overview built from their ArchAI concepts.

Every view returns a list of lines, so it is testable without a terminal.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import textwrap
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

from .bundle import ARCHAI_BUNDLE_FORMAT, check_conformance
from .document import RESERVED_FILENAMES, OKFDocument, OKFDocumentError, trust_tier

_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_FOOTREF = re.compile(r"\[\^([^\]]+)\](?!:)")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")

STATUS_ORDER = ["VERIFIED_VIOLATION", "POTENTIAL_RISK", "INSUFFICIENT_GRAPH_EVIDENCE", "PASS"]
_STATUS_COLOR = {"VERIFIED_VIOLATION": "31", "POTENTIAL_RISK": "33",
                 "INSUFFICIENT_GRAPH_EVIDENCE": "35", "PASS": "32"}
_STATUS_SHORT = {"VERIFIED_VIOLATION": "VIOLATION", "POTENTIAL_RISK": "RISK",
                 "INSUFFICIENT_GRAPH_EVIDENCE": "NO-EVIDENCE", "PASS": "PASS"}


class Style:
    """ANSI styling, disabled when not a TTY, with NO_COLOR, or on request."""

    def __init__(self, enabled: Optional[bool] = None):
        if enabled is None:
            enabled = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
        self.enabled = enabled
        if enabled and os.name == "nt":
            os.system("")  # enables ANSI escape processing in legacy Windows consoles

    def _wrap(self, code: str, text: str) -> str:
        return f"\x1b[{code}m{text}\x1b[0m" if self.enabled else text

    def bold(self, t: str) -> str:
        return self._wrap("1", t)

    def dim(self, t: str) -> str:
        return self._wrap("2", t)

    def cyan(self, t: str) -> str:
        return self._wrap("36", t)

    def status(self, status: str, short: bool = False) -> str:
        label = _STATUS_SHORT.get(status, status) if short else status
        return self._wrap("1;" + _STATUS_COLOR.get(status, "0"), label)


@dataclass
class Concept:
    id: str  # path within the bundle without ".md" (OKF §2)
    path: Path
    frontmatter: Dict[str, Any] = field(default_factory=dict)
    body: str = ""
    error: Optional[str] = None
    links: List[Tuple[str, str, Optional[str]]] = field(default_factory=list)  # (text, href, target id)

    @property
    def type(self) -> str:
        return str(self.frontmatter.get("type") or "(no type)")

    @property
    def title(self) -> str:
        return str(self.frontmatter.get("title") or self.id.rsplit("/", 1)[-1])

    @property
    def description(self) -> str:
        return str(self.frontmatter.get("description") or "")


class BundleView:
    def __init__(self, root: str):
        self.root = Path(root)
        if not self.root.is_dir():
            raise FileNotFoundError(f"OKF bundle directory not found: {root}")
        self.concepts: Dict[str, Concept] = {}
        self.okf_version: Optional[str] = None
        for path in sorted(self.root.rglob("*.md")):
            rel = path.relative_to(self.root).as_posix()
            if path.name in RESERVED_FILENAMES:
                if rel == "index.md":
                    try:
                        self.okf_version = OKFDocument.parse(path.read_text(encoding="utf-8")).frontmatter.get("okf_version")
                    except OKFDocumentError:
                        pass
                continue
            concept = Concept(id=rel[:-3], path=path)
            try:
                doc = OKFDocument.parse(path.read_text(encoding="utf-8"))
                concept.frontmatter, concept.body = doc.frontmatter, doc.body
            except (OKFDocumentError, UnicodeDecodeError) as e:
                concept.error = str(e)
            self.concepts[concept.id] = concept
        self.backlinks: Dict[str, List[str]] = defaultdict(list)
        for concept in self.concepts.values():
            for text, href in _LINK.findall(concept.body):
                target = self.resolve(concept.id, href)
                concept.links.append((text, href, target))
                if target and concept.id not in self.backlinks[target]:
                    self.backlinks[target].append(concept.id)
        run = self.concepts.get("analysis/run")
        self.is_archai = bool(run and run.frontmatter.get("archai_bundle_format") == ARCHAI_BUNDLE_FORMAT)

    # --- Links and lookup -------------------------------------------------------

    def resolve(self, from_id: str, href: str) -> Optional[str]:
        """Concept id a link points at (OKF §6.1), or None for external/directory links."""
        if re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I) or href.startswith("#"):
            return None
        href = href.split("#", 1)[0]
        if not href.endswith(".md"):
            return None
        base = PurePosixPath("/") if href.startswith("/") else PurePosixPath("/" + from_id).parent
        parts: List[str] = []
        for part in (base / href.lstrip("/")).parts[1:]:
            if part == "..":
                if parts:
                    parts.pop()
            elif part != ".":
                parts.append(part)
        return "/".join(parts)[:-3]

    def find(self, query: str) -> Tuple[Optional[Concept], List[str]]:
        """Exact id, then unique exact title, id suffix, or substring. Returns (match, candidates)."""
        q = query.strip().strip("/")
        q = q[:-3] if q.endswith(".md") else q
        if q in self.concepts:
            return self.concepts[q], []
        for pick in (
            lambda c: c.title.lower() == q.lower(),
            lambda c: c.id.endswith("/" + q),
            lambda c: q.lower() in c.id.lower() or q.lower() in c.title.lower(),
        ):
            hits = sorted(c.id for c in self.concepts.values() if pick(c))
            if len(hits) == 1:
                return self.concepts[hits[0]], []
            if hits:
                return None, hits
        return None, []


# --- Helpers --------------------------------------------------------------------

def _width() -> int:
    return max(60, min(shutil.get_terminal_size((100, 24)).columns, 140))


def _clip(text: str, n: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: max(0, n - 3)] + "..."


def _pad(styled: str, plain: str, width: int) -> str:
    """Left-aligns a styled string by the width of its unstyled text."""
    return styled + " " * max(0, width - len(plain))


def _status_cell(s: Style, status: str, width: int = 12) -> str:
    return _pad(s.status(status, short=True), _STATUS_SHORT.get(status, status), width)


def _rule(s: Style, title: str = "") -> str:
    w = _width()
    return s.bold(f"== {title} " + "=" * max(0, w - len(title) - 4)) if title else "=" * w


def _is_stale(fm: Dict[str, Any]) -> bool:
    raw = str(fm.get("stale_after") or "")
    if "T" not in raw:
        return False
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    return moment.tzinfo is not None and datetime.now(timezone.utc) >= moment


def _cmd(bundle: BundleView, arg: str = "") -> str:
    try:
        where = bundle.root.resolve().relative_to(Path.cwd().resolve()).as_posix() or "."
    except ValueError:
        where = "<bundle>"
    return f"OKF-VIEW {where}" + (f" {arg}" if arg else "")


def _evidence_label(e: Dict[str, Any]) -> str:
    if e.get("kind") == "missing_file":
        return f"{e.get('file')} (missing)"
    return f"{e['file']}:{e['line']}" if e.get("line") else str(e.get("file"))


# --- Views ----------------------------------------------------------------------

def overview(b: BundleView, s: Style) -> List[str]:
    conf = check_conformance(str(b.root))
    out = [_rule(s, "OKF BUNDLE"), f" Path: {b.root}",
           f" OKF version: {b.okf_version or 'not declared'} | Concepts: {len(b.concepts)} | "
           f"Conformance (OKF v0.2 section 11): " + ("PASS" if conf["conformant"] else f"FAIL ({len(conf['errors'])} issue(s))")]
    for err in conf["errors"][:5]:
        out.append("   ! " + err)
    tiers = Counter(trust_tier(c.frontmatter) for c in b.concepts.values())
    stale = sum(1 for c in b.concepts.values() if _is_stale(c.frontmatter))
    out.append(" Trust tiers: " + ", ".join(f"{k} {v}" for k, v in sorted(tiers.items()))
               + (f" | Stale: {stale}" if stale else ""))
    types = Counter(c.type for c in b.concepts.values())
    out += ["", s.bold(" Concept types")]
    out += [f"   {n:>5}  {t}" for t, n in sorted(types.items(), key=lambda kv: (-kv[1], kv[0]))]

    if b.is_archai:
        out += [""] + archai_overview(b, s)
    out += ["", s.dim(f" Next: {_cmd(b, 'tree')} | {_cmd(b, 'list')} | {_cmd(b, '<concept>')}")]
    return out


def archai_overview(b: BundleView, s: Style) -> List[str]:
    run = b.concepts["analysis/run"].frontmatter
    prov, summary = run.get("archai_provenance", {}), run.get("archai_analysis", {})
    repo = prov.get("repository") or {}
    commit = repo.get("git_commit")
    out = [_rule(s, "ARCHAI STANDARDS CHECK"),
           f" Repository: {repo.get('name', '?')}"
           + (f" @ {commit[:12]}" + (" (dirty)" if repo.get("git_dirty") else "") if commit else " (no git commit)"),
           f" Analyzed: {prov.get('analyzed_at')} by ArchAI {prov.get('tool', {}).get('version')} "
           f"| facts: {prov.get('fact_source')} | LLM used: {'yes' if prov.get('llm_used') else 'no'}",
           f" Graph: {summary.get('python_modules', '?')} modules, {summary.get('import_edges', '?')} import edges"
           + (f", {len(summary.get('parse_failures', []))} parse failure(s)" if summary.get("parse_failures") else "")]
    unsupported = summary.get("unsupported_files") or {}
    if unsupported:
        out.append(" Not covered (unsupported languages): " + ", ".join(f"{n} {e}" for e, n in sorted(unsupported.items())))

    results = sorted((c for c in b.concepts.values() if c.type == "ArchAI Rule Result"),
                     key=lambda c: c.id)
    origins = {c.frontmatter.get("archai_rule", {}).get("id"): c.frontmatter.get("archai_rule", {}).get("origin", "?")
               for c in b.concepts.values() if c.type == "ArchAI Standard Rule"}
    out += ["", s.bold(f" {'OUTCOME':<13} {'RULE':<38} {'ORIGIN':<15} FINDINGS")]
    for c in results:
        r = c.frontmatter.get("archai_result", {})
        rule_id = r.get("rule_id", c.id)
        out.append(f" {_status_cell(s, r.get('outcome', '?'), 13)} {_clip(rule_id, 38):<38} "
                   f"{origins.get(rule_id, '?'):<15} {len(r.get('finding_ids', []))}")

    config = run.get("archai_config", {})
    if config.get("uses_defaults_only"):
        note = ("No standards config was supplied: only ArchAI default rules ran. A PASS here covers only "
                "those defaults, not your organization's standards. Add archai_standards.yaml "
                "(see examples/archai_standards.example.yaml) or pass --config.")
        lines = textwrap.wrap(note, _width() - 8)
        out += ["", " " + s._wrap("1;33", "NOTE") + " " + lines[0]] + ["      " + l for l in lines[1:]]
    limitations = [n for n in run.get("archai_limitations", []) if not n.startswith("No standards configuration")]
    if limitations:
        out += ["", s.bold(" Limitations")]
        for note in limitations:
            wrapped = textwrap.wrap(note, _width() - 6)
            out += [f"   - {wrapped[0]}"] + [f"     {l}" for l in wrapped[1:]]

    findings = _findings(b)
    counts = Counter(f["status"] for f in findings)
    out += ["", " Findings: " + " | ".join(f"{s.status(st, short=True)} {counts.get(st, 0)}" for st in STATUS_ORDER[:3])]
    shown = [f for f in findings if f["status"] != "INSUFFICIENT_GRAPH_EVIDENCE"][:10]
    for f in shown:
        out.append(f"   {_status_cell(s, f['status'])} {s.cyan(f['id'])}  {_clip(f['summary'], _width() - 34)}")
    if len(findings) > len(shown):
        out.append(s.dim(f"   ... see {_cmd(b, 'findings')}"))
    return out


def _findings(b: BundleView, status: Optional[str] = None) -> List[Dict[str, Any]]:
    items = [c.frontmatter.get("archai_finding", {}) for c in b.concepts.values() if c.type == "ArchAI Finding"]
    items = [f for f in items if f and (status is None or f.get("status") == status)]
    rank = {st: i for i, st in enumerate(STATUS_ORDER)}
    return sorted(items, key=lambda f: (rank.get(f.get("status"), 9), f.get("rule_id", ""), f.get("id", "")))


def findings_view(b: BundleView, s: Style, status: Optional[str] = None) -> List[str]:
    if status:
        status = next((st for st in STATUS_ORDER if status.upper() in (st, _STATUS_SHORT[st])), status.upper())
    items = _findings(b, status)
    out = [_rule(s, f"FINDINGS ({len(items)})" + (f" - {status}" if status else ""))]
    if not b.is_archai:
        return out + [" This bundle has no ArchAI findings."]
    current = None
    for f in items:
        if f["status"] != current:
            current = f["status"]
            out += ["", " " + s.status(current)]
        where = ", ".join(_evidence_label(e) for e in f.get("evidence", [])[:3])
        more = len(f.get("evidence", [])) - 3
        out.append(f"   {s.cyan(f['id'])}  [{f['rule_id']}]  {_clip(f['summary'], _width() - 40)}")
        if where:
            out.append(s.dim(f"      evidence: {where}" + (f" (+{more} more)" if more > 0 else "")))
    out += ["", s.dim(f" Details: {_cmd(b, '<finding-id>')}")]
    return out


def list_view(b: BundleView, s: Style, type_filter: Optional[str] = None) -> List[str]:
    items = [c for c in b.concepts.values() if not type_filter or type_filter.lower() in c.type.lower()]
    out = [_rule(s, f"CONCEPTS ({len(items)})" + (f" - type ~ '{type_filter}'" if type_filter else ""))]
    w = _width()
    for c in sorted(items, key=lambda c: (c.type, c.id)):
        kind = _clip(c.type, 22)
        out.append(f" {_clip(c.id, 40):<40} {_pad(s.dim(kind), kind, 22)}  {_clip(c.description or c.title, w - 66)}")
    return out


def tree_view(b: BundleView, s: Style) -> List[str]:
    out = [_rule(s, "TREE"), f" {b.root.name}/"]
    by_dir: Dict[str, List[Concept]] = defaultdict(list)
    for c in b.concepts.values():
        by_dir[c.id.rsplit("/", 1)[0] if "/" in c.id else ""].append(c)
    dirs = sorted(by_dir)
    for d in dirs:
        depth = d.count("/") + 1 if d else 0
        if d:
            out.append("   " * depth + s.bold(d.rsplit("/", 1)[-1] + "/") + s.dim(f"  ({len(by_dir[d])})"))
        for c in sorted(by_dir[d], key=lambda c: c.id)[:25]:
            out.append("   " * (depth + 1) + f"{c.id.rsplit('/', 1)[-1]}.md  " + s.dim(c.type))
        if len(by_dir[d]) > 25:
            out.append("   " * (depth + 1) + s.dim(f"... {len(by_dir[d]) - 25} more ({_cmd(b, 'list')})"))
    return out


def _render_body(b: BundleView, c: Concept, s: Style) -> List[str]:
    out = []
    for line in c.body.splitlines():
        if re.match(r"^\[\^[^\]]+\]:", line):
            continue  # footnote definitions are shown, resolved, under SOURCES
        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            out += ["", s.bold(heading.group(2).upper() if len(heading.group(1)) == 1 else heading.group(2))]
            continue

        def link(m):
            target = b.resolve(c.id, m.group(2))
            if target is None:
                return f"{m.group(1)} <{m.group(2)}>"
            mark = "" if target in b.concepts else " [missing]"
            return f"{m.group(1)} " + s.cyan(f"-> {target}") + mark

        line = _LINK.sub(link, line)
        line = _FOOTREF.sub(lambda m: s.dim(f" [{m.group(1)}]"), line)
        line = _BOLD.sub(lambda m: s.bold(m.group(1)), line)
        out.append(" " + line if line.strip() else "")
    collapsed: List[str] = []
    for line in out:
        if line or (collapsed and collapsed[-1]):
            collapsed.append(line)
    while collapsed and not collapsed[-1]:
        collapsed.pop()
    return [""] + collapsed if collapsed else []


def concept_view(b: BundleView, c: Concept, s: Style, raw: bool = False) -> List[str]:
    fm = c.frontmatter
    out = [_rule(s, c.id), f" {s.bold(c.title)}  " + s.dim(f"[{c.type}]")]
    if c.error:
        return out + [f" ! Could not parse: {c.error}"]
    if c.description:
        out.append(" " + c.description)
    gen = fm.get("generated") or {}
    meta = [f"trust: {trust_tier(fm)}", f"status: {fm.get('status', 'stable')}"]
    if gen:
        meta.append(f"generated by {gen.get('by')} at {gen.get('at')}")
    if fm.get("stale_after"):
        meta.append(("STALE since " if _is_stale(fm) else "fresh until ") + str(fm["stale_after"]))
    out.append(s.dim(" " + " | ".join(meta)))
    if fm.get("tags"):
        out.append(s.dim(" tags: " + ", ".join(map(str, fm["tags"]))))
    if fm.get("resource"):
        out.append(f" resource: {fm['resource']}")

    if c.type == "Attested Computation":  # OKF section 10 contract
        params = ", ".join(f"{p.get('name')}: {p.get('type')}" + ("" if p.get("required", True) else "?")
                           for p in fm.get("parameters") or [] if isinstance(p, dict))
        executor, attester = fm.get("executor") or {}, fm.get("attester") or {}
        out += ["", f" runtime: {fm.get('runtime', '(missing - required for this type)')}"
                    + (f" | parameters: {params}" if params else ""),
                f" computation: {fm.get('computation') or 'inline (# Computation section)'}"]
        if executor:
            out.append(f" executor: {executor.get('resource')} | receipt: {', '.join(map(str, executor.get('receipt') or []))}")
        if attester:
            out.append(f" attester: {attester.get('resource')}")

    finding = fm.get("archai_finding")
    if finding:
        out += ["", f" {s.status(finding['status'])}  rule {s.cyan(finding['rule_id'])}",
                f" verification: {finding['verification'].get('method')}, "
                f"evidence {finding['verification'].get('evidence_completeness')}, "
                f"LLM-assisted: {'yes' if finding['verification'].get('llm_assisted') else 'no'}"]
        if finding.get("observed"):
            out.append(s.dim(" observed: " + _clip(", ".join(f"{k}={v}" for k, v in finding["observed"].items()), _width() * 2)))

    out += _render_body(b, c, s)

    sources = fm.get("sources") or []
    if sources:
        out += ["", s.bold(f"SOURCES ({len(sources)}, OKF provenance)")]
        groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for src in sources:
            groups[str(src.get("resource", ""))].append(src)
        for resource, group in groups.items():
            target = b.resolve(c.id, resource)
            res = s.cyan(f"-> {target}") if target and target in b.concepts else resource
            if len(group) == 1:
                out.append(f" [{group[0].get('id', '-')}] {group[0].get('title', '')}  {res}")
            else:
                ids = [g.get("id", "-") for g in group]
                out.append(f" [{ids[0]}..{ids[-1]}] {len(group)} sources  {res}")

    if c.type == "Python Module" and fm.get("archai_imports") is not None:
        importers = sorted(i for i in b.backlinks.get(c.id, []) if b.concepts[i].type == "Python Module")
        out += ["", s.bold(f"IMPORTED BY ({len(importers)})")] + [f" {s.cyan(i)}" for i in importers[:40]]

    backlinks = [i for i in b.backlinks.get(c.id, []) if not (c.type == "Python Module" and b.concepts[i].type == "Python Module")]
    if backlinks:
        out += ["", s.bold(f"LINKED FROM ({len(backlinks)})")]
        out += [f" {s.cyan(i)}  " + s.dim(b.concepts[i].type) for i in sorted(backlinks)[:30]]

    extension = [k for k in fm if k.startswith("archai_")]
    if raw:
        import yaml
        out += ["", s.bold("FRONTMATTER")] + [" " + line for line in
                                               yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).splitlines()]
    elif extension:
        out += ["", s.dim(f" Extension keys: {', '.join(extension)} (use --raw to show the full frontmatter)")]
    return out


# --- Entry point ----------------------------------------------------------------

VIEWS = ("overview", "tree", "list", "findings", "rules", "results", "modules", "layers")


def render(bundle_dir: str, target: Optional[str] = None, status: Optional[str] = None,
           type_filter: Optional[str] = None, raw: bool = False, color: Optional[bool] = None) -> Tuple[int, str]:
    """Returns (exit code, text). Exit 2 when the bundle or concept is not found."""
    s = Style(color)
    try:
        b = BundleView(bundle_dir)
    except FileNotFoundError as e:
        return 2, str(e)
    if not b.concepts:
        return 2, f"No OKF concepts (*.md with frontmatter) found under {bundle_dir}"
    view = (target or "overview").lower()
    if view == "overview":
        lines = overview(b, s)
    elif view == "tree":
        lines = tree_view(b, s)
    elif view == "list":
        lines = list_view(b, s, type_filter)
    elif view == "findings":
        lines = findings_view(b, s, status)
    elif view in ("rules", "results", "modules", "layers"):
        type_name = {"rules": "Standard Rule", "results": "Rule Result", "modules": "Python Module",
                     "layers": "ArchAI Layer"}[view]
        lines = list_view(b, s, type_filter or type_name)
    else:
        concept, candidates = b.find(target)
        if concept is None:
            if candidates:
                return 2, "\n".join([f"'{target}' matches {len(candidates)} concepts; be more specific:"]
                                    + [f"  {c}" for c in candidates[:20]])
            return 2, f"No concept matches '{target}'. Try: {_cmd(b, 'list')}"
        lines = concept_view(b, concept, s, raw)
    return 0, "\n".join(lines)

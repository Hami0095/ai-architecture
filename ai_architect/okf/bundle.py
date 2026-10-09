"""Exports ArchAI repository knowledge as an OKF v0.2 bundle, loads it back,
and checks the bundle against the conformance rules of OKF v0.2 §11.

Bundle layout (all concept types are ArchAI-defined; OKF has no type registry):

    index.md                     bundle root; frontmatter carries only okf_version
    analysis/run.md              type: ArchAI Analysis Run  (provenance, scope, limitations)
    analysis/file-inventory.md   type: ArchAI File Inventory
    modules/<module>.md          type: Python Module        (import facts, line numbers)
    layers/<layer>.md            type: ArchAI Layer
    rules/<rule-id>.md           type: ArchAI Standard Rule
    results/<rule-id>.md         type: ArchAI Rule Result
    findings/<finding-id>.md     type: ArchAI Finding        (evidence via OKF `sources`)

Typed facts live in `archai_*` frontmatter keys (OKF §4.1 permits extension
keys); relationships are also written as markdown links (OKF §6.1) so generic
OKF consumers and graph viewers see the same graph.
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..standards.config import RuleSpec, StandardsConfig
from ..standards.model import RepoGraph
from ..version import ARCHAI_VERSION
from .document import OKF_VERSION, RESERVED_FILENAMES, OKFDocument, OKFDocumentError

ARCHAI_BUNDLE_FORMAT = "archai-okf-bundle/1"

_INDEX_LINE = re.compile(r"^\* \[[^\]]+\]\([^)]+\)( - .*)?$")
_LOG_DATE = re.compile(r"^#{1,6} \d{4}-\d{2}-\d{2}\s*$")


def _plain(value: Any) -> Any:
    """Tuples and dataclasses become plain YAML-safe structures."""
    return json.loads(json.dumps(value, default=str))


def _code(text: str) -> str:
    return "`" + text.replace("`", "'") + "`"


def _actor() -> str:
    return f"archai/{ARCHAI_VERSION}"  # OKF §7 actor convention


class _Writer:
    def __init__(self, root: Path, generated: Dict[str, str]):
        self.root = root
        self.generated = generated
        self.entries: Dict[str, List[Tuple[str, str, str]]] = {}

    def concept(self, rel: str, frontmatter: Dict[str, Any], body: str) -> None:
        fm = {"type": frontmatter.pop("type")}
        fm.update(frontmatter)
        fm.setdefault("generated", dict(self.generated))
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(OKFDocument(_plain(fm), body).serialize(), encoding="utf-8", newline="\n")
        directory, filename = rel.rsplit("/", 1) if "/" in rel else ("", rel)
        self.entries.setdefault(directory, []).append(
            (str(fm.get("title", filename[:-3])), filename, str(fm.get("description", ""))))

    def indexes(self, sections: Dict[str, str]) -> None:
        for directory, items in sorted(self.entries.items()):
            if not directory:
                continue
            lines = [f"# {sections.get(directory, directory)}", ""]
            for title, link, desc in sorted(items, key=lambda i: i[1]):
                lines.append(f"* [{title}]({link})" + (f" - {desc}" if desc else ""))
            (self.root / directory / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        root_lines = []
        for directory in sorted(d for d in self.entries if d):
            root_lines += [f"# {sections.get(directory, directory)}", "",
                           f"* [{directory}]({directory}/) - {len(self.entries[directory])} concept(s)", ""]
        doc = OKFDocument({"okf_version": OKF_VERSION}, "\n".join(root_lines).rstrip() + "\n")
        (self.root / "index.md").write_text(doc.serialize(), encoding="utf-8", newline="\n")


def export_bundle(report: Dict[str, Any], out_dir: str) -> Path:
    """Writes the knowledge behind a standards report as an OKF bundle."""
    graph: RepoGraph = report["_graph"]
    config: StandardsConfig = report["_config"]
    results = report["_results"]
    prov = report["provenance"]
    root = Path(out_dir)
    if root.exists():
        if not (root / "analysis" / "run.md").exists() and any(root.iterdir()):
            raise FileExistsError(f"{root} exists and is not an ArchAI OKF bundle; refusing to overwrite.")
        shutil.rmtree(root)
    root.mkdir(parents=True)
    repo = prov.get("repository") or {}
    commit = repo.get("git_commit")
    at_commit = f" at commit {commit}" if commit else " (no git commit recorded)"
    w = _Writer(root, {"by": _actor(), "at": prov["analyzed_at"]})

    # Analysis run (provenance + graph-level facts)
    w.concept("analysis/run.md", {
        "type": "ArchAI Analysis Run",
        "title": f"Standards analysis of {repo.get('name', 'repository')}",
        "description": "Provenance, scope and limitations of the analysis that produced this bundle.",
        "tags": ["archai", "provenance"],
        "archai_bundle_format": ARCHAI_BUNDLE_FORMAT,
        "archai_provenance": prov,
        "archai_rule_order": [r.id for r in config.rules],
        "archai_limitations": report["limitations"],
        "archai_analysis": report["analysis"],
        "archai_graph": {
            "unresolved_internal": graph.unresolved_internal,
            "opaque_dynamic_imports": graph.opaque_dynamic_imports,
            "unsupported_files": graph.unsupported_files,
            "excluded_modules": graph.excluded_modules,
            "diagnostics": graph.diagnostics,
        },
        "archai_config": {"path": config.path, "sha256": config.sha256,
                          "source_roots": config.source_roots, "exclude": config.exclude,
                          "uses_defaults_only": config.uses_defaults_only},
    }, "# Summary\n\n" + "\n".join(f"* {k}: {v}" for k, v in report["summary"].items()) +
       "\n\n# Limitations\n\n" + "\n".join(f"* {n}" for n in report["limitations"]) +
       "\n\n# Contents\n\n* [Rules](/rules/index.md)\n* [Results](/results/index.md)\n"
       "* [Findings](/findings/index.md)\n* [Modules](/modules/index.md)\n"
       "* [File inventory](/analysis/file-inventory.md)\n")

    w.concept("analysis/file-inventory.md", {
        "type": "ArchAI File Inventory",
        "title": "File inventory",
        "description": f"{len(graph.files)} repository file path(s) seen by the analysis (paths only, no contents).",
        "archai_files": graph.files,
    }, "Paths are repository-relative. Required-test checks are evaluated against this list.\n")

    # Modules
    by_source: Dict[str, list] = {}
    for e in graph.edges:
        by_source.setdefault(e.source, []).append(e)
    for name, fact in sorted(graph.modules.items()):
        edges = by_source.get(name, [])
        lines = [f"* [{e.target}](/modules/{e.target}.md) - line {e.line}, {e.scope} scope: {_code(e.statement)}"
                 for e in edges]
        body = "# Imports\n\n" + ("\n".join(lines) if lines else "No internal imports.") + "\n"
        if fact.parse_error:
            body += f"\n# Parse error\n\n{_code(fact.parse_error)}\n"
        w.concept(f"modules/{name}.md", {
            "type": "Python Module",
            "title": name,
            "description": f"{'Package' if fact.is_package else 'Module'} at {fact.path} with "
                           f"{len(edges)} internal import edge(s).",
            "tags": ["python-module"] + (["parse-error"] if fact.parse_error else []),
            "sources": [{"id": "source-file", "resource": f"repository file {fact.path}{at_commit}",
                         "title": fact.path}],
            "archai_module": asdict(fact),
            "archai_imports": [{"target": e.target, "line": e.line, "scope": e.scope,
                                "statement": e.statement} for e in edges],
        }, body)

    # Layers and rules
    for layer, patterns in sorted(config.layers.items()):
        w.concept(f"layers/{layer}.md", {
            "type": "ArchAI Layer", "title": layer,
            "description": f"Modules matching: {', '.join(patterns)}",
            "archai_patterns": patterns,
        }, "# Patterns\n\n" + "\n".join(f"* {_code(p)}" for p in patterns) + "\n")

    for rule in config.rules:
        origin_note = ("Supplied in the repository's standards configuration."
                       if rule.origin == "user-config" else
                       "ArchAI default heuristic; not an organization-mandated standard.")
        sources = [{"id": "config", "resource": f"standards configuration {config.path} (sha256 {config.sha256})",
                    "title": config.path}] if rule.origin == "user-config" and config.path else []
        w.concept(f"rules/{rule.id}.md", {
            "type": "ArchAI Standard Rule", "title": rule.id, "description": rule.description,
            "tags": ["standard", rule.kind, rule.origin],
            **({"sources": sources} if sources else {}),
            "archai_rule": {"id": rule.id, "kind": rule.kind, "origin": rule.origin, "params": rule.params,
                            "description": rule.description, "rationale": rule.rationale},
        }, f"# Rationale\n\n{rule.rationale}\n\n# Origin\n\n{origin_note}"
           f"{'[^config]' if sources else ''}\n\n# Result\n\nSee [result](/results/{rule.id}.md).\n"
           + (f"\n[^config]: {config.path}\n" if sources else ""))

    # Results and findings
    module_by_path = {m.path: m for m in graph.modules.values()}
    for result in results:
        finding_links = [f"* [{f.id}](/findings/{f.id}.md) - {f.status}: {f.summary}" for f in result.findings]
        w.concept(f"results/{result.rule_id}.md", {
            "type": "ArchAI Rule Result", "title": f"{result.rule_id}: {result.outcome}",
            "description": f"{len(result.findings)} finding(s); outcome {result.outcome}.",
            "tags": ["result", result.outcome],
            "archai_result": {"rule_id": result.rule_id, "outcome": result.outcome,
                              "scope_stats": result.scope_stats, "limitations": result.limitations,
                              "finding_ids": [f.id for f in result.findings]},
        }, f"Rule: [{result.rule_id}](/rules/{result.rule_id}.md)\n\n# Findings\n\n" +
           ("\n".join(finding_links) if finding_links else "None.") + "\n")

        for f in result.findings:
            sources, refs, notes = [], [], []
            for i, ev in enumerate(f.evidence, 1):
                sid = f"ev{i}"
                if ev.kind == "missing_file":
                    resource = f"absent repository path {ev.file}{at_commit}"
                elif ev.file in module_by_path:
                    resource = f"/modules/{module_by_path[ev.file].name}.md"
                else:
                    resource = f"repository file {ev.file}{at_commit}" if ev.file else "analysis run"
                location = f"{ev.file}:{ev.line}" if ev.line else (ev.file or "n/a")
                sources.append({"id": sid, "resource": resource, "title": location})
                refs.append(f"* {location} ({ev.kind}): {_code(ev.detail) if ev.detail else ''}[^{sid}]")
                notes.append(f"[^{sid}]: {location}")
            body = (f"Rule: [{f.rule_id}](/rules/{f.rule_id}.md) - status **{f.status}**\n\n"
                    f"{f.summary}\n\n# Expected\n\n{f.expected}\n\n# Evaluation\n\n{f.evaluation}\n\n"
                    "# Evidence\n\n" + ("\n".join(refs) if refs else "No source evidence applies.") + "\n")
            if f.limitations:
                body += "\n# Limitations\n\n" + "\n".join(f"* {n}" for n in f.limitations) + "\n"
            if f.next_steps:
                body += "\n# Next steps\n\n" + "\n".join(f"* {n}" for n in f.next_steps) + "\n"
            body += "\n# Modules\n\n" + ("\n".join(f"* [{m}](/modules/{m}.md)" for m in f.modules) or "None.") + "\n"
            if notes:
                body += "\n" + "\n".join(notes) + "\n"
            w.concept(f"findings/{f.id}.md", {
                "type": "ArchAI Finding", "title": f"{f.id} ({f.status})", "description": f.summary,
                "tags": ["finding", f.status, f.category],
                **({"sources": sources} if sources else {}),
                "archai_finding": asdict(f),
            }, body)

    w.indexes({"analysis": "Analysis", "modules": "Python Modules", "layers": "Layers",
               "rules": "Standard Rules", "results": "Rule Results", "findings": "Findings"})
    return root


# --- Loading --------------------------------------------------------------------

def _read(path: Path) -> OKFDocument:
    return OKFDocument.parse(path.read_text(encoding="utf-8"))


def load_bundle(bundle_dir: str) -> Dict[str, Any]:
    """Reconstructs the graph, configuration and findings from an ArchAI OKF bundle."""
    root = Path(bundle_dir)
    run_path = root / "analysis" / "run.md"
    if not run_path.exists():
        raise OKFDocumentError(f"{root} is not an ArchAI OKF bundle (missing analysis/run.md).")
    run = _read(run_path).frontmatter
    if run.get("archai_bundle_format") != ARCHAI_BUNDLE_FORMAT:
        raise OKFDocumentError(f"Unsupported bundle format: {run.get('archai_bundle_format')!r}")
    inventory = _read(root / "analysis" / "file-inventory.md").frontmatter

    modules, edges = {}, []
    for path in sorted((root / "modules").glob("*.md")):
        if path.name in RESERVED_FILENAMES:
            continue
        fm = _read(path).frontmatter
        fact = fm["archai_module"]
        modules[fact["name"]] = fact
        edges += [{"source": fact["name"], **e} for e in fm.get("archai_imports", [])]
    g = run["archai_graph"]
    graph = RepoGraph.from_dict({
        "modules": modules,
        "edges": sorted(edges, key=lambda e: (e["source"], e["line"], e["target"], e["scope"], e["statement"])),
        "files": inventory.get("archai_files", []), **g})

    layers = {}
    if (root / "layers").is_dir():
        for path in sorted((root / "layers").glob("*.md")):
            if path.name not in RESERVED_FILENAMES:
                fm = _read(path).frontmatter
                layers[fm["title"]] = fm["archai_patterns"]
    cfg = run.get("archai_config", {})
    rules = []
    for path in sorted((root / "rules").glob("*.md")):
        if path.name in RESERVED_FILENAMES:
            continue
        r = _read(path).frontmatter["archai_rule"]
        rules.append(RuleSpec(id=r["id"], kind=r["kind"], description=r["description"],
                              rationale=r["rationale"], origin=r["origin"], params=r["params"]))
    position = {rid: i for i, rid in enumerate(run.get("archai_rule_order", []))}
    rules.sort(key=lambda r: (position.get(r.id, len(position)), r.id))
    config = StandardsConfig(rules=rules, layers=layers, source_roots=cfg.get("source_roots", []),
                             exclude=cfg.get("exclude", []), path=cfg.get("path"), sha256=cfg.get("sha256"),
                             uses_defaults_only=cfg.get("uses_defaults_only", False))

    findings = {}
    if (root / "findings").is_dir():
        for path in sorted((root / "findings").glob("*.md")):
            if path.name not in RESERVED_FILENAMES:
                f = _read(path).frontmatter["archai_finding"]
                findings[f["id"]] = f
    return {"graph": graph, "config": config, "findings": findings,
            "provenance": run["archai_provenance"]}


# --- Conformance (OKF v0.2 §11) -------------------------------------------------

def check_conformance(bundle_dir: str) -> Dict[str, Any]:
    """Checks the three conformance conditions of OKF v0.2 §11.

    This is ArchAI's reading of the spec, not an official validator (none is
    published with the spec as of v0.2).
    """
    root = Path(bundle_dir)
    errors: List[str] = []
    concepts = 0
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        try:
            doc = OKFDocument.parse(text)
        except OKFDocumentError as e:
            errors.append(f"{rel}: {e}")
            continue
        if path.name == "index.md":
            if doc.has_frontmatter and (rel != "index.md" or set(doc.frontmatter) - {"okf_version"}):
                errors.append(f"{rel}: index.md may carry frontmatter only at the bundle root, "
                              "and only the okf_version key (§8, §12).")
            for line in doc.body.splitlines():
                if line.strip() and not line.startswith("#") and not _INDEX_LINE.match(line):
                    errors.append(f"{rel}: index line does not follow §8 structure: {line!r}")
        elif path.name == "log.md":
            for line in doc.body.splitlines():
                if line.startswith("## ") and not _LOG_DATE.match(line):
                    errors.append(f"{rel}: log date heading must be ISO 8601 YYYY-MM-DD (§9): {line!r}")
        else:
            concepts += 1
            if not doc.has_frontmatter:
                errors.append(f"{rel}: concept has no YAML frontmatter block (§11.1).")
            elif not isinstance(doc.frontmatter.get("type"), str) or not doc.frontmatter["type"].strip():
                errors.append(f"{rel}: frontmatter lacks a non-empty 'type' (§11.2).")
    return {"okf_version": OKF_VERSION, "conformant": not errors, "concepts": concepts, "errors": errors}

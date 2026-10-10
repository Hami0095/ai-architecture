"""ArchAI tools for AI agents (Claude Code, Codex and other MCP clients).

Plain functions returning JSON-serializable dicts, so they can be tested without
an MCP runtime. ai_architect/agents/mcp_server.py exposes them over MCP.

Every tool here is deterministic: no LLM and no network. The AI-assisted Insight
agents (Surveyor, Seismograph's verdict, Draftsman, Interpreter) are not exposed;
an AI agent calling ArchAI is already a language model, so ArchAI hands it
verified facts and lets it do the reasoning.

Nothing in this module may print to stdout: in an MCP stdio server, stdout is
the protocol channel.
"""
from __future__ import annotations

import difflib
import json
import os
import subprocess
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from ..okf import check_conformance, export_bundle
from ..okf.document import trust_tier
from ..okf.viewer import BundleView, render
from ..standards.config import RULE_KINDS, StandardsConfigError, load_config, parse_config
from ..standards.engine import exit_code, public, run_check
from ..standards.extract import build_repo_graph
from ..standards.model import RUNTIME_SCOPES, SCOPE_MODULE, RepoGraph
from ..utils.license import LicenseManager


class ToolError(ValueError):
    """A problem the calling agent can fix (bad path, unknown module, invalid config)."""


# --- Guards and shared helpers ---------------------------------------------------

def require_license() -> None:
    """Same rule as the CLI: a valid ARCHAI_LICENSE token, or ARCHAI_DEV_MODE for local use."""
    if os.environ.get("ARCHAI_DEV_MODE"):
        return
    info = LicenseManager.inspect_token(os.environ.get("ARCHAI_LICENSE"))
    if info["state"] != "VALID":
        raise ToolError(f"ArchAI license {info['state']}: {info['reason']} Set ARCHAI_LICENSE in the MCP "
                        "server's environment (or ARCHAI_DEV_MODE=1 for local development).")


def _repo(repo_path: str) -> Path:
    root = Path(repo_path).expanduser().resolve()
    if not root.is_dir():
        raise ToolError(f"repo_path is not a directory: {repo_path}")
    return root


def _config(root: Path, config_path: Optional[str], include_defaults: bool = True):
    try:
        return load_config(root, Path(config_path).expanduser() if config_path else None, include_defaults)
    except StandardsConfigError as e:
        raise ToolError(f"Invalid standards config: {e}") from e


def _graph(repo_path: str, config_path: Optional[str] = None) -> RepoGraph:
    root = _repo(repo_path)
    config = _config(root, config_path)
    return build_repo_graph(root, config.source_roots, config.exclude)


def _module(graph: RepoGraph, module: str) -> str:
    if module in graph.modules:
        return module
    by_path = {m.path: m.name for m in graph.modules.values()}
    candidate = module.replace("\\", "/")
    if candidate in by_path:
        return by_path[candidate]
    close = difflib.get_close_matches(module, list(graph.modules), n=5, cutoff=0.5)
    raise ToolError(f"Unknown module '{module}'." + (f" Did you mean: {', '.join(close)}?" if close else
                    " Use atlas_graph_overview to list modules."))


def _edge(graph: RepoGraph, e, direction: str) -> Dict[str, Any]:
    out = {"module": e.target if direction == "out" else e.source,
           "file": graph.modules[e.source].path, "line": e.line, "scope": e.scope, "statement": e.statement}
    return out


# --- Plumb (CHECK-STANDARDS) -------------------------------------------------------

def plumb_check_standards(repo_path: str, config_path: Optional[str] = None, include_defaults: bool = True,
                          statuses: Optional[List[str]] = None, max_findings: int = 50,
                          max_evidence: int = 5) -> Dict[str, Any]:
    root = _repo(repo_path)
    config = _config(root, config_path, include_defaults)
    report = public(run_check(str(root), config=config))
    wanted = {s.upper() for s in statuses} if statuses else None
    shown = 0
    truncated = False
    rule_results = []
    for r in report["rule_results"]:
        findings = []
        for f in r["findings"]:
            if wanted and f["status"] not in wanted:
                continue
            if shown >= max_findings:
                truncated = True
                continue
            shown += 1
            evidence = f["evidence"]
            findings.append({**{k: f[k] for k in ("id", "status", "summary", "modules", "files", "expected",
                                                    "evaluation", "verification", "limitations", "next_steps",
                                                    "observed")},
                             "evidence": evidence[:max_evidence], "evidence_total": len(evidence)})
        rule_results.append({k: r[k] for k in ("rule_id", "kind", "origin", "description", "outcome",
                                               "scope_stats", "limitations")} | {"findings": findings})
    return {
        "schema_version": report["schema_version"],
        "exit_code": exit_code(report),
        "provenance": report["provenance"],
        "config": {k: report["config"][k] for k in ("path", "sha256", "uses_defaults_only")},
        "analysis": report["analysis"],
        "summary": report["summary"],
        "rule_results": rule_results,
        "limitations": report["limitations"],
        "truncated": truncated,
        "how_to_read": "A finding is VERIFIED_VIOLATION only when every fact is cited (file:line). "
                       "POTENTIAL_RISK and INSUFFICIENT_GRAPH_EVIDENCE are not violations. A PASS covers only "
                       "the rule's declared scope. Quote the evidence when reporting findings.",
    }


def plumb_validate_config(config_yaml: Optional[str] = None, config_path: Optional[str] = None) -> Dict[str, Any]:
    if bool(config_yaml) == bool(config_path):
        raise ToolError("Pass exactly one of config_yaml or config_path.")
    try:
        text = config_yaml if config_yaml else Path(config_path).expanduser().read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        cfg = parse_config(data, include_defaults=False)
    except (StandardsConfigError, yaml.YAMLError, OSError) as e:
        return {"valid": False, "error": str(e)}
    return {"valid": True, "error": None, "layers": cfg.layers, "source_roots": cfg.source_roots,
            "exclude": cfg.exclude,
            "rules": [{"id": r.id, "kind": r.kind, "params": r.params} for r in cfg.rules],
            "note": None if cfg.rules else "No rules: CHECK-STANDARDS would run only ArchAI defaults."}


RULE_REFERENCE: Dict[str, Any] = {
    "file": "archai_standards.yaml in the repository root (or pass config_path)",
    "top_level": {
        "version": "1 (optional)",
        "source_roots": "import roots, e.g. ['src']; a src/ folder without __init__.py is detected automatically",
        "exclude": "repo-relative path globs (fnmatch; * crosses /), e.g. ['tests/*', 'migrations/*']",
        "defaults": "auto (default: add ArchAI default rules only when no rules are configured) | true | false",
        "layers": "map of layer name -> module patterns",
        "rules": "list of rules (below)",
    },
    "patterns": "A plain dotted name (myapp.domain) matches that module and everything beneath it; "
                "patterns with * ? [ use fnmatch on the full dotted module name; '*' matches every module.",
    "every_rule": {"id": "required; letters, digits, . _ -", "kind": "required", "description": "optional",
                   "rationale": "optional"},
    "kinds": {
        "forbidden_dependency": {"fields": {"from": "required patterns", "to": "required patterns"},
                                 "example": "- id: api-not-db\n  kind: forbidden_dependency\n  from: [myapp.api]\n  to: [myapp.db]"},
        "layer_boundary": {"fields": {"layer": "required, declared under layers",
                                      "forbidden_layers | allowed_layers": "exactly one of the two"},
                           "example": "- id: domain-is-pure\n  kind: layer_boundary\n  layer: domain\n  forbidden_layers: [infrastructure]"},
        "circular_dependency": {"fields": {"scope": "patterns, default ['*']"},
                                "example": "- id: no-cycles\n  kind: circular_dependency\n  scope: [myapp]"},
        "coupling_threshold": {"fields": {"max": "required non-negative integer", "metric": "fan_out (default) | fan_in",
                                          "scope": "patterns, default ['*']"},
                               "example": "- id: bounded-fan-out\n  kind: coupling_threshold\n  metric: fan_out\n  max: 12"},
        "required_tests": {"fields": {"scope": "required patterns",
                                      "test_paths": "required templates using {leaf} {module} {module_path} {parent_path}",
                                      "include_packages": "bool, default false"},
                           "example": "- id: services-have-tests\n  kind: required_tests\n  scope: [myapp.services]\n  test_paths: ['tests/test_{leaf}.py']"},
    },
    "statuses": {
        "VERIFIED_VIOLATION": "The rule is broken and every supporting fact is cited from source.",
        "POTENTIAL_RISK": "Facts match the rule's pattern, but static analysis cannot settle whether it is a breach.",
        "INSUFFICIENT_GRAPH_EVIDENCE": "Part of the scope could not be checked; silence there is not compliance.",
        "PASS": "Rule outcome only: nothing found within the declared scope.",
    },
}
assert set(RULE_REFERENCE["kinds"]) == RULE_KINDS, "RULE_REFERENCE is out of date with standards.config.RULE_KINDS"


def plumb_rule_reference() -> Dict[str, Any]:
    return RULE_REFERENCE


# --- Atlas (OKF-VIEW) and the code map -------------------------------------------

def atlas_export_bundle(repo_path: str, out_dir: str, config_path: Optional[str] = None,
                        include_defaults: bool = True) -> Dict[str, Any]:
    root = _repo(repo_path)
    config = _config(root, config_path, include_defaults)
    report = run_check(str(root), config=config)
    try:
        bundle = export_bundle(report, str(Path(out_dir).expanduser()))
    except FileExistsError as e:
        raise ToolError(str(e)) from e
    conformance = check_conformance(str(bundle))
    return {"bundle_dir": str(bundle), "concepts": conformance["concepts"],
            "conformant_okf_v0_2": conformance["conformant"], "conformance_errors": conformance["errors"],
            "summary": report["summary"]}


def atlas_view(bundle_dir: str, target: Optional[str] = None, status: Optional[str] = None,
               type_filter: Optional[str] = None, raw: bool = False) -> Dict[str, Any]:
    code, text = render(bundle_dir, target, status=status, type_filter=type_filter, raw=raw, color=False)
    if code:
        raise ToolError(text)
    return {"text": text}


def atlas_concept(bundle_dir: str, concept: str) -> Dict[str, Any]:
    try:
        view = BundleView(bundle_dir)
    except FileNotFoundError as e:
        raise ToolError(str(e)) from e
    found, candidates = view.find(concept)
    if not found:
        raise ToolError(f"'{concept}' matches {len(candidates)} concepts: {', '.join(candidates[:20])}"
                        if candidates else f"No concept matches '{concept}'.")
    return {"id": found.id, "type": found.type, "title": found.title, "description": found.description,
            "trust_tier": trust_tier(found.frontmatter), "frontmatter": found.frontmatter, "body": found.body,
            "links": [{"text": t, "href": h, "target": tgt, "exists": bool(tgt and tgt in view.concepts)}
                      for t, h, tgt in found.links],
            "linked_from": sorted(view.backlinks.get(found.id, []))}


def atlas_graph_overview(repo_path: str, config_path: Optional[str] = None, top: int = 10) -> Dict[str, Any]:
    graph = _graph(repo_path, config_path)
    runtime = [e for e in graph.edges if e.scope in RUNTIME_SCOPES]
    fan_out = Counter({m: len({e.target for e in runtime if e.source == m}) for m in graph.modules})
    fan_in = Counter({m: len({e.source for e in runtime if e.target == m}) for m in graph.modules})
    packages = Counter(m.split(".")[0] for m in graph.modules)
    return {
        "modules": len(graph.modules), "import_edges": len(graph.edges),
        "packages": dict(packages.most_common()),
        "top_fan_out": [{"module": m, "imports": n} for m, n in fan_out.most_common(top) if n],
        "top_fan_in": [{"module": m, "imported_by": n} for m, n in fan_in.most_common(top) if n],
        "parse_failures": sorted(m for m, f in graph.modules.items() if f.parse_error),
        "unresolved_internal_imports": len(graph.unresolved_internal),
        "unsupported_files": graph.unsupported_files,
        "excluded_modules": len(graph.excluded_modules),
        "diagnostics": graph.diagnostics,
        "note": "Static Python imports only; fan-in/out count distinct internal modules (module- and function-level).",
    }


def atlas_module(repo_path: str, module: str, config_path: Optional[str] = None) -> Dict[str, Any]:
    graph = _graph(repo_path, config_path)
    name = _module(graph, module)
    fact = graph.modules[name]
    return {"module": name, "file": fact.path, "is_package": fact.is_package, "parse_error": fact.parse_error,
            "imports": [_edge(graph, e, "out") for e in graph.edges if e.source == name],
            "imported_by": [_edge(graph, e, "in") for e in graph.edges if e.target == name],
            "unresolved_imports": [u for u in graph.unresolved_internal if u["source"] == name]}


def atlas_import_path(repo_path: str, source: str, target: str, include_deferred: bool = True,
                      config_path: Optional[str] = None) -> Dict[str, Any]:
    """Shortest import chain source -> ... -> target, each hop cited."""
    graph = _graph(repo_path, config_path)
    src, dst = _module(graph, source), _module(graph, target)
    # Deferred = function-level, type-checking-only and dynamic imports; without them, only
    # imports that run when the module is loaded count.
    allowed = {e.scope for e in graph.edges} if include_deferred else {SCOPE_MODULE}
    first: Dict[tuple, Any] = {}
    adj = defaultdict(set)
    for e in graph.edges:
        if e.scope in allowed:
            adj[e.source].add(e.target)
            first.setdefault((e.source, e.target), e)
    prev = {src: None}
    queue = deque([src])
    while queue:
        node = queue.popleft()
        if node == dst:
            break
        for nxt in sorted(adj[node]):
            if nxt not in prev:
                prev[nxt] = node
                queue.append(nxt)
    if dst not in prev:
        return {"source": src, "target": dst, "path": None,
                "answer": f"No {'import' if include_deferred else 'module-level import'} chain from {src} to {dst} "
                          "in the static import graph."}
    chain = [dst]
    while prev[chain[-1]] is not None:
        chain.append(prev[chain[-1]])
    chain.reverse()
    hops = [_edge(graph, first[(a, b)], "out") | {"from": a} for a, b in zip(chain, chain[1:])]
    return {"source": src, "target": dst, "path": chain, "hops": hops,
            "answer": f"{src} reaches {dst} in {len(hops)} import hop(s)."}


# --- Seismograph (deterministic part of IMPACT) ------------------------------------

def seismograph_dependents(repo_path: str, module: str, max_depth: int = 3, include_deferred: bool = True,
                           config_path: Optional[str] = None) -> Dict[str, Any]:
    """Modules that (transitively) import `module`: what a change to it can reach."""
    graph = _graph(repo_path, config_path)
    name = _module(graph, module)
    return {"module": name, **_dependents(graph, [name], max_depth, include_deferred),
            "note": "Module-level static imports only; no AI risk verdict. Runtime wiring is not visible."}


def _dependents(graph: RepoGraph, start: List[str], max_depth: int, include_deferred: bool) -> Dict[str, Any]:
    reverse = defaultdict(list)
    for e in graph.edges:
        if include_deferred or e.scope == SCOPE_MODULE:
            reverse[e.target].append(e)
    seen = {m: 0 for m in start}
    out = []
    queue = deque(start)
    while queue:
        node = queue.popleft()
        if seen[node] >= max_depth:
            continue
        for e in sorted(reverse[node], key=lambda e: (e.source, e.line)):
            if e.source not in seen:
                seen[e.source] = seen[node] + 1
                out.append({"module": e.source, "depth": seen[e.source], "via": node,
                            "file": graph.modules[e.source].path, "line": e.line, "statement": e.statement})
                queue.append(e.source)
    return {"dependents": out, "count": len(out), "max_depth": max_depth}


# --- Foreman (deterministic part of GITHUB) -----------------------------------------

def foreman_changed_modules(repo_path: str, base: str = "main", max_depth: int = 2,
                            config_path: Optional[str] = None) -> Dict[str, Any]:
    """Python files changed against `base` (committed, staged, unstaged and untracked) and what imports them."""
    root = _repo(repo_path)

    def git(*args):
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
        if r.returncode:
            raise ToolError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
        return r.stdout.split()

    changed = sorted(set(git("diff", "--name-only", base)) | set(git("ls-files", "--others", "--exclude-standard")))
    graph = _graph(repo_path, config_path)
    by_path = {m.path: m.name for m in graph.modules.values()}
    py = [f for f in changed if f.endswith(".py")]
    modules = sorted(by_path[f] for f in py if f in by_path)
    return {"base": base, "changed_files": changed, "changed_modules": modules,
            "changed_python_files_not_in_graph": [f for f in py if f not in by_path],
            **_dependents(graph, modules, max_depth, include_deferred=True),
            "next_step": "Run plumb_check_standards to prove the rules still hold after these changes."}


# --- Ledger (TRACE) -----------------------------------------------------------------

def ledger_trace(ticket_id: str, report_path: str = "archai_report.json") -> Dict[str, Any]:
    path = Path(report_path).expanduser()
    if not path.is_file():
        raise ToolError(f"No Surveyor (AUDIT) report at {path}. Ledger only reads evidence an AUDIT run recorded.")
    report = json.loads(path.read_text(encoding="utf-8"))
    ticket = next((t for t in report.get("tasks", []) if t.get("ticket_id") == ticket_id), None)
    if not ticket:
        raise ToolError(f"Ticket {ticket_id} not found. Known: {', '.join(t.get('ticket_id', '?') for t in report.get('tasks', []))}")
    return {"ticket_id": ticket_id, "title": ticket.get("title"), "evidence": ticket.get("evidence"),
            "confidence_level": ticket.get("confidence_level"), "confidence_score": ticket.get("confidence_score"),
            "uncertainty_drivers": ticket.get("uncertainty_drivers"), "description": ticket.get("description"),
            "note": "This evidence was recorded by the AI-assisted Surveyor pipeline and is not verified. "
                    "Check it against the source, or express it as a rule for plumb_check_standards."}

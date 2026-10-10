"""Runs a standards check end to end and records provenance for reproducibility."""
from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..version import ARCHAI_VERSION
from .config import StandardsConfig, load_config
from .extract import build_repo_graph
from .model import (
    INSUFFICIENT_GRAPH_EVIDENCE, PASS, POTENTIAL_RISK, REPORT_SCHEMA_VERSION, STATUS_ORDER,
    VERIFIED_VIOLATION, RepoGraph, RuleResult,
)
from .rules import evaluate_rule

_PACKAGE_DIR = Path(__file__).resolve().parent.parent
_ENGINE_FILES = [
    "analysis/graph_engine.py", "standards/model.py", "standards/extract.py",
    "standards/config.py", "standards/rules.py", "standards/engine.py",
    "okf/document.py", "okf/bundle.py",
]


def engine_hash() -> str:
    """Hash of the deterministic engine's source, so results can be tied to code."""
    hasher = hashlib.sha256()
    for rel in _ENGINE_FILES:
        path = _PACKAGE_DIR / rel
        if path.exists():
            hasher.update(rel.encode())
            hasher.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return hasher.hexdigest()[:16]


def analysis_timestamp() -> str:
    """UTC timestamp; honours SOURCE_DATE_EPOCH so research runs can be byte-reproducible."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    moment = datetime.fromtimestamp(int(epoch), timezone.utc) if epoch and epoch.isdigit() \
        else datetime.now(timezone.utc).replace(microsecond=0)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _git(root: Path, *args: str) -> Optional[str]:
    try:
        out = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                             timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def repository_identity(root: Path) -> Dict[str, Any]:
    """Local git facts only. The remote URL is deliberately not recorded: clone
    URLs can embed access tokens."""
    top = _git(root, "rev-parse", "--show-toplevel")
    commit = _git(root, "rev-parse", "HEAD") if top else None
    dirty = None
    if commit:
        status = _git(root, "status", "--porcelain")
        dirty = bool(status) if status is not None else None
    return {"name": root.name, "git_commit": commit, "git_dirty": dirty,
            "is_git_repository": bool(top)}


def evaluate(graph: RepoGraph, config: StandardsConfig) -> List[RuleResult]:
    return [evaluate_rule(rule, config.layers, graph) for rule in config.rules]


def summarize(results: List[RuleResult]) -> Dict[str, Any]:
    findings = [f for r in results for f in r.findings]
    return {
        "rules_evaluated": len(results),
        "rule_outcomes": {s: sum(1 for r in results if r.outcome == s) for s in STATUS_ORDER},
        "findings": {s: sum(1 for f in findings if f.status == s) for s in STATUS_ORDER if s != PASS},
        "findings_with_line_evidence": sum(1 for f in findings if any(e.line for e in f.evidence)),
        "findings_total": len(findings),
    }


def global_limitations(graph: RepoGraph, config: StandardsConfig) -> List[str]:
    notes = ["Only Python is analyzed. Dependencies are static import statements; runtime wiring "
             "(dependency injection, plugins, reflection) is not visible.",
             "A PASS means the rule found nothing within its declared scope; it does not certify "
             "the architecture as a whole."]
    if config.uses_defaults_only:
        notes.insert(0, "No standards configuration was supplied: only ArchAI default rules were evaluated. "
                        "These are ArchAI heuristics, not your organization's standards.")
    if graph.unsupported_files:
        listing = ", ".join(f"{n} {ext}" for ext, n in sorted(graph.unsupported_files.items()))
        notes.append(f"Unsupported source files were skipped and are NOT covered by any rule: {listing}.")
    parse_failures = sorted(m for m, f in graph.modules.items() if f.parse_error)
    if parse_failures:
        notes.append(f"{len(parse_failures)} Python file(s) failed to parse and contribute no dependency facts.")
    if graph.excluded_modules:
        notes.append(f"{len(graph.excluded_modules)} module(s) were excluded by configuration.")
    notes.extend(graph.diagnostics)
    return notes


def build_report(graph: RepoGraph, config: StandardsConfig, results: List[RuleResult],
                 provenance: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "provenance": provenance,
        "config": config.to_dict(),
        "analysis": {
            "python_modules": len(graph.modules),
            "parse_failures": sorted(m for m, f in graph.modules.items() if f.parse_error),
            "import_edges": len(graph.edges),
            "unresolved_internal_imports": len(graph.unresolved_internal),
            "opaque_dynamic_imports": len(graph.opaque_dynamic_imports),
            "files_inventoried": len(graph.files),
            "unsupported_files": dict(sorted(graph.unsupported_files.items())),
            "excluded_modules": graph.excluded_modules,
        },
        "summary": summarize(results),
        "rule_results": [asdict(r) for r in results],
        "limitations": global_limitations(graph, config),
    }


def run_check(repo_path: str, config_path: Optional[str] = None, include_defaults: bool = True,
              graph: Optional[RepoGraph] = None, config: Optional[StandardsConfig] = None,
              fact_source: str = "source-extraction") -> Dict[str, Any]:
    """Checks a repository (or a pre-built graph, e.g. one loaded from OKF) against standards."""
    started = time.perf_counter()
    timestamp = analysis_timestamp()
    root = Path(repo_path).resolve() if repo_path else None
    if config is None:
        config = load_config(root, Path(config_path) if config_path else None, include_defaults)
    if graph is None:
        if root is None or not root.is_dir():
            raise FileNotFoundError(f"Repository path is not a directory: {repo_path}")
        graph = build_repo_graph(root, config.source_roots, config.exclude)
    results = evaluate(graph, config)
    provenance = {
        "tool": {"name": "ArchAI", "version": ARCHAI_VERSION, "engine_sha256": engine_hash()},
        "repository": repository_identity(root) if root and root.is_dir() else None,
        "analyzed_at": timestamp,
        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        "python_version": platform.python_version(),
        "fact_source": fact_source,
        "llm_used": False,
        "network_used": False,
    }
    report = build_report(graph, config, results, provenance)
    report["_graph"] = graph  # not serialized; used for OKF export
    report["_config"] = config
    report["_results"] = results
    return report


def exit_code(report: Dict[str, Any]) -> int:
    """0: no verified violations. 1: at least one verified violation."""
    return 1 if report["summary"]["findings"].get(VERIFIED_VIOLATION) else 0


def public(report: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in report.items() if not k.startswith("_")}


def deterministic_view(report: Dict[str, Any]) -> Dict[str, Any]:
    """The report minus run-specific fields (timing, timestamp); identical across reruns."""
    view = public(report)
    view = dict(view)
    view["provenance"] = {k: v for k, v in view["provenance"].items()
                          if k not in ("analyzed_at", "duration_ms")}
    return view


__all__ = ["run_check", "exit_code", "public", "deterministic_view", "VERIFIED_VIOLATION",
           "POTENTIAL_RISK", "INSUFFICIENT_GRAPH_EVIDENCE", "PASS"]

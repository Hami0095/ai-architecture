"""Renders a standards report as Markdown (for people) or JSON (for machines)."""
from __future__ import annotations

import json
from typing import Any, Dict, List

from .engine import public
from .model import INSUFFICIENT_GRAPH_EVIDENCE, PASS, POTENTIAL_RISK, VERIFIED_VIOLATION

_LABEL = {
    VERIFIED_VIOLATION: "VERIFIED VIOLATION",
    POTENTIAL_RISK: "POTENTIAL RISK",
    INSUFFICIENT_GRAPH_EVIDENCE: "INSUFFICIENT EVIDENCE",
    PASS: "PASS",
}

STATUS_LEGEND = [
    f"- **{VERIFIED_VIOLATION}**: the rule is broken; every supporting fact is cited from source.",
    f"- **{POTENTIAL_RISK}**: the facts match the rule's pattern, but static analysis cannot settle "
    "whether it is a breach (e.g. type-checking-only or deferred imports).",
    f"- **{INSUFFICIENT_GRAPH_EVIDENCE}**: part of the scope could not be evaluated; silence there is not compliance.",
    f"- **{PASS}**: nothing found within the rule's declared scope. Not a certificate for the whole codebase.",
]


def to_json(report: Dict[str, Any]) -> str:
    return json.dumps(public(report), indent=2, sort_keys=False, default=str)


def _evidence_line(ev: Dict[str, Any]) -> str:
    where = f"{ev['file']}:{ev['line']}" if ev.get("line") else (ev.get("file") or "(no file)")
    detail = f" `{ev['detail']}`" if ev.get("detail") else ""
    return f"  - `{where}` ({ev['kind']}){detail}"


def to_markdown(report: Dict[str, Any], verbose: bool = False) -> str:
    prov, analysis, summary = report["provenance"], report["analysis"], report["summary"]
    repo = prov.get("repository") or {}
    out: List[str] = ["# ArchAI Standards Report", ""]
    commit = repo.get("git_commit")
    out.append(f"Repository **{repo.get('name', '?')}**"
               + (f" at `{commit[:12]}`" + (" (uncommitted changes present)" if repo.get("git_dirty") else "")
                  if commit else " (not a git commit; results are not pinned to a revision)")
               + f" | ArchAI {prov['tool']['version']} (engine `{prov['tool']['engine_sha256']}`)"
               + f" | {prov['analyzed_at']} | facts from {prov['fact_source']} | LLM used: "
               + ("yes" if prov["llm_used"] else "no"))
    out += ["", "## 1. What was checked", ""]
    out.append(f"{analysis['python_modules']} Python module(s), {analysis['import_edges']} internal import edge(s), "
               f"{summary['rules_evaluated']} rule(s).")
    out += ["", "| Rule | Kind | Origin | Outcome | Scope |", "|---|---|---|---|---|"]
    for r in report["rule_results"]:
        scope = ", ".join(f"{k}={v}" for k, v in r["scope_stats"].items())
        out.append(f"| `{r['rule_id']}` | {r['kind']} | {r['origin']} | **{_LABEL[r['outcome']]}** | {scope} |")

    findings = [f for r in report["rule_results"] for f in r["findings"]]
    counts = summary["findings"]
    out += ["", "## 2. What was found", ""]
    out.append(f"{counts.get(VERIFIED_VIOLATION, 0)} verified violation(s), {counts.get(POTENTIAL_RISK, 0)} "
               f"potential risk(s), {counts.get(INSUFFICIENT_GRAPH_EVIDENCE, 0)} evidence gap(s).")
    out += ["", "## 3. Evidence for each finding", ""]
    if not findings:
        out.append("No findings.")
    for f in findings:
        if f["status"] == INSUFFICIENT_GRAPH_EVIDENCE:
            continue
        out.append(f"### {_LABEL[f['status']]}: {f['summary']}")
        out.append(f"`{f['id']}` | rule `{f['rule_id']}` | expected: {f['expected']}")
        out.append("")
        out.append(f"- Evaluation: {f['evaluation']}")
        out.append("- Evidence:")
        out += [_evidence_line(ev) for ev in f["evidence"]]
        if verbose:
            out.append(f"- Observed facts: `{json.dumps(f['observed'], sort_keys=True)}`")
            out.append(f"- Verification: `{json.dumps(f['verification'], sort_keys=True)}`")
        for note in f["limitations"]:
            out.append(f"- Limitation: {note}")
        out.append("")

    out += ["## 4. What could not be verified", ""]
    gaps = [f for f in findings if f["status"] == INSUFFICIENT_GRAPH_EVIDENCE]
    for f in gaps:
        out.append(f"- `{f['rule_id']}`: {f['summary']}")
        shown = f["evidence"] if verbose else f["evidence"][:5]
        out += ["  " + _evidence_line(ev) for ev in shown]
        if len(shown) < len(f["evidence"]):
            out.append(f"    - ... {len(f['evidence']) - len(shown)} more (use --verbose)")
    for r in report["rule_results"]:
        for note in r["limitations"]:
            out.append(f"- `{r['rule_id']}`: {note}")
    for note in report["limitations"]:
        out.append(f"- {note}")

    out += ["", "## 5. What to investigate next", ""]
    steps = []
    for f in findings:
        for step in f["next_steps"]:
            if step not in steps:
                steps.append(step)
    out += [f"- {s}" for s in steps[:15]] or ["- Nothing flagged. Consider adding repository-specific rules."]
    out += ["", "## Status legend", ""] + STATUS_LEGEND + [""]
    return "\n".join(out)

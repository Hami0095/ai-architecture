"""ArchAI MCP server: exposes ArchAI's deterministic agents to AI coding agents.

Run with `ai-architect-mcp` (stdio). Register it with:

    claude mcp add archai --env ARCHAI_LICENSE=<token> -- ai-architect-mcp
    codex mcp add archai --env ARCHAI_LICENSE=<token> -- ai-architect-mcp

Requires the optional dependency: pip install "ai_architect[agents]".
"""
from __future__ import annotations

import functools
import sys
from typing import Any, Callable, Dict, List, Optional

from ..version import ARCHAI_VERSION
from . import tools

INSTRUCTIONS = """ArchAI checks a Python codebase against engineering rules and proves every finding with a
file-and-line receipt. Every tool here is deterministic: no LLM, no network.

Recommended workflow:
1. atlas_graph_overview to orient yourself (modules, most-coupled modules).
2. Write or read archai_standards.yaml; use plumb_rule_reference and plumb_validate_config.
3. plumb_check_standards to prove the rules hold. Report VERIFIED_VIOLATION findings with their
   file:line evidence; POTENTIAL_RISK and INSUFFICIENT_GRAPH_EVIDENCE are not violations, and a PASS
   covers only the rule's declared scope.
4. atlas_module, atlas_import_path and seismograph_dependents answer structural questions with cited
   import statements. foreman_changed_modules maps your branch's changes to affected modules.
Never claim a rule passed or failed without a plumb_check_standards result."""


def _wrap(fn: Callable[..., Dict[str, Any]], mcp_tool_error: type) -> Callable[..., Dict[str, Any]]:
    """License check for every tool. Problems the agent can fix become MCP tool errors carrying
    the message; anything else is left to the SDK, which reports it as an unexpected failure."""
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        try:
            tools.require_license()
            return fn(*args, **kwargs)
        except tools.ToolError as e:
            raise mcp_tool_error(str(e)) from e
    return inner


def build_server():
    try:
        from mcp.server.mcpserver import MCPServer
        from mcp.server.mcpserver.exceptions import ToolError as MCPToolError
        from mcp.types import ToolAnnotations
    except ImportError as e:  # pragma: no cover - exercised manually
        raise SystemExit('The ArchAI MCP server needs the MCP SDK: pip install "ai_architect[agents]"') from e

    server = MCPServer(name="archai", title="ArchAI", version=ARCHAI_VERSION, instructions=INSTRUCTIONS,
                       website_url="https://github.com/Hami0095/ai-architecture")
    read_only = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
    writes = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)

    def add(fn, title, description, annotations=read_only):
        server.tool(name=fn.__name__, title=title, description=description, annotations=annotations)(_wrap(fn, MCPToolError))

    add(tools.plumb_check_standards, "Plumb: check standards",
        "Check a Python repository against its engineering rules (archai_standards.yaml, or config_path) and "
        "return evidence-backed findings. Statuses: VERIFIED_VIOLATION (cited from source), POTENTIAL_RISK, "
        "INSUFFICIENT_GRAPH_EVIDENCE, PASS (within declared scope only). Without a config only the ArchAI "
        "default rule (no import cycles) runs. Filter with statuses=['VERIFIED_VIOLATION']. Deterministic.")
    add(tools.plumb_validate_config, "Plumb: validate a standards config",
        "Validate archai_standards.yaml content (config_yaml) or a file (config_path) before running a check. "
        "Returns the parsed rules, or the exact error.")
    add(tools.plumb_rule_reference, "Plumb: rule reference",
        "The archai_standards.yaml format: top-level keys, module pattern syntax, the five rule kinds "
        "(forbidden_dependency, layer_boundary, circular_dependency, coupling_threshold, required_tests) with "
        "fields and YAML examples, and the meaning of each finding status.")
    add(tools.atlas_graph_overview, "Atlas: code map overview",
        "Overview of a Python repository's import graph: module and edge counts, packages, the most coupled "
        "modules (fan-out and fan-in), parse failures, unresolved imports and unsupported files.")
    add(tools.atlas_module, "Atlas: one module",
        "A module's internal imports and its importers, each with file, line, scope and the import statement. "
        "Accepts a dotted module name or a repo-relative .py path.")
    add(tools.atlas_import_path, "Atlas: import path between modules",
        "Shortest import chain from source to target with every hop cited (file:line). Answers 'does X depend "
        "on Y?'. include_deferred=False counts only imports that run at module load.")
    add(tools.seismograph_dependents, "Seismograph: what depends on a module",
        "Modules that transitively import the given module, up to max_depth, with the import that links each. "
        "Use before changing a module. Deterministic; no AI risk verdict.")
    add(tools.foreman_changed_modules, "Foreman: changed modules",
        "Python files changed against a git base (committed, staged, unstaged, untracked), mapped to modules, "
        "plus the modules that import them. Uses local git only.")
    add(tools.atlas_view, "Atlas: view an OKF bundle",
        "Text view of an exported ArchAI/OKF bundle: target may be overview (default), tree, list, findings, "
        "rules, results, modules, layers or a concept id/title. status filters findings (VIOLATION, RISK, NO-EVIDENCE).")
    add(tools.atlas_concept, "Atlas: one OKF concept",
        "One concept from an OKF bundle as structured data: frontmatter, body, resolved links, backlinks, trust tier.")
    add(tools.ledger_trace, "Ledger: evidence behind a Surveyor ticket",
        "The evidence a previous AUDIT (Surveyor) run recorded for a ticket. That evidence is AI-generated and "
        "unverified; treat it as a lead, not a fact.")
    add(tools.atlas_export_bundle, "Atlas: export an OKF bundle",
        "Run the standards check and write an Open Knowledge Format v0.2 bundle (findings, rules, module map) "
        "to out_dir. Replaces an existing ArchAI bundle there; refuses other non-empty folders.",
        annotations=writes)

    @server.prompt(name="archai_review", title="ArchAI architecture review",
                   description="Review a repository's architecture with ArchAI and report findings with receipts.")
    def archai_review(repo_path: str = ".") -> str:
        return (f"Review the architecture of the Python repository at {repo_path} with the ArchAI tools.\n\n"
                + INSTRUCTIONS + "\n\nIf the repository has no archai_standards.yaml, propose one from what "
                "atlas_graph_overview shows (layers, forbidden dependencies, a coupling limit), validate it with "
                "plumb_validate_config, and ask before writing it to disk. End with: what was checked, verified "
                "violations with file:line receipts, what could not be verified, and suggested next steps.")

    @server.resource("archai://reference/rules", name="rule-reference", title="ArchAI rule reference",
                     description="archai_standards.yaml format and finding statuses.", mime_type="application/json")
    def rule_reference() -> str:
        import json
        return json.dumps(tools.RULE_REFERENCE, indent=2)

    return server


def main() -> None:
    build_server().run("stdio")


if __name__ == "__main__":
    main()

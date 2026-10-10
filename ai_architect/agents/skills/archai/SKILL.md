---
name: archai
description: Check and explain the architecture of a Python codebase with ArchAI, reporting every finding with a file:line receipt. Use when asked to enforce or review architecture rules (layers, forbidden imports, import cycles, coupling limits, required test files), to find what depends on a module before changing it, to explain how two modules are connected, or to see which modules a branch's changes affect. Do not use for non-Python code, runtime or performance questions, or general code review.
---

# ArchAI: proven architecture findings

ArchAI checks a Python repository against explicit engineering rules and proves every
finding with a file-and-line receipt. Its principle is **Receipts or Silence**: if
something cannot be proven from the code, say it could not be verified instead of
guessing.

## Use the MCP tools when they are available

If the `archai` MCP server is connected (tool names start with `plumb_`, `atlas_`,
`seismograph_`, `foreman_`, `ledger_`), prefer the tools. All of them are
deterministic: no LLM, no network.

| Need | Tool |
|---|---|
| Orient in an unfamiliar repo | `atlas_graph_overview` |
| Write or fix `archai_standards.yaml` | `plumb_rule_reference`, then `plumb_validate_config` |
| Prove the rules hold | `plumb_check_standards` |
| A module's imports and importers | `atlas_module` |
| "Does X depend on Y?" | `atlas_import_path` |
| What a change to a module can reach | `seismograph_dependents` |
| What this branch's changes affect | `foreman_changed_modules` |
| Share or browse results | `atlas_export_bundle`, `atlas_view`, `atlas_concept` |
| Evidence behind an earlier AUDIT ticket | `ledger_trace` (AI-recorded, unverified) |

## Workflow

1. **Orient.** Run `atlas_graph_overview` on the repository root.
2. **Get the rules.** If `archai_standards.yaml` exists, use it. If not, propose rules
   that match the codebase (layers, forbidden dependencies, a coupling limit), check
   them with `plumb_validate_config`, and **ask the user before writing the file**.
   Rules belong to the user's team; do not invent their standards.
3. **Prove.** Run `plumb_check_standards`. To focus on what is broken, pass
   `statuses: ["VERIFIED_VIOLATION"]`.
4. **Investigate.** Use `atlas_module`, `atlas_import_path` and `seismograph_dependents`
   to explain findings or answer structural questions.
5. **After editing code,** run `plumb_check_standards` again before saying the
   problem is fixed.

## Reporting rules

- Quote the receipt for every violation: rule id, `file:line` and the import
  statement from `evidence`.
- **VERIFIED_VIOLATION** is the only status that means "broken".
  **POTENTIAL_RISK** means the facts match the rule's pattern but static analysis
  cannot settle it. **INSUFFICIENT_GRAPH_EVIDENCE** means part of the scope was not
  checked. Report these as such, never as violations or passes.
- A rule's **PASS** covers only its declared scope. Never say "the architecture is
  correct."
- If only ArchAI's default rule ran (`uses_defaults_only: true`), say that no team
  standards were checked.
- State limitations ArchAI reports: Python only, static imports only, and
  `required_tests` checks file names, not coverage.

## Without the MCP server: the CLI

```bash
ai-architect CHECK-STANDARDS <repo> --json                 # machine-readable report
ai-architect CHECK-STANDARDS <repo> --config rules.yaml --json
ai-architect OKF-VIEW <bundle> findings --status violation --no-color
```

`CHECK-STANDARDS` exits 0 (no verified violations), 1 (verified violations) or
2 (usage or config error). The CLI needs `ARCHAI_LICENSE`, or `ARCHAI_DEV_MODE=1` for
local development.

## Do not

- Run `AUDIT`, `G-REASON`, `EXPLAIN` or `IMPACT` unless the user asks. They call a
  language model (by default a cloud model), so code leaves the machine, and their
  output is not verified. You can reason over the facts the tools return instead.
- Edit `archai_standards.yaml` without the user's agreement.
- Present results from a non-Python codebase as clean; ArchAI reports other
  languages as not covered.

The full rule format is in [reference.md](reference.md).

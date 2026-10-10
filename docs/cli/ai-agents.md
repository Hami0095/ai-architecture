# AI Agents: Claude Code and Codex

ArchAI's deterministic agents can be used directly by AI coding agents through
the **ArchAI MCP server** and the **ArchAI skill**:

- The **MCP server** (`ai-architect-mcp`) gives the agent twelve tools: Plumb's
  standards check, Atlas's code map and knowledge bundles, Seismograph's
  dependents, Foreman's changed modules and Ledger's evidence trail. None of
  them uses an LLM or the network.
- The **skill** (`SKILL.md`, open agent-skills format) teaches the agent when to
  use ArchAI, the workflow, and how to report findings: receipts for every
  violation, and no overclaimed PASS.

The AI-assisted Insight agents (Surveyor, Draftsman, Interpreter, and
Seismograph's risk verdict) are not exposed to agents. The calling agent is
already a language model, so ArchAI gives it verified facts and lets it do the
reasoning, instead of calling a second model and sending code to it.

## Setup

```bash
pip install -e ".[agents]"          # from the ArchAI checkout: adds the MCP SDK
export ARCHAI_LICENSE=<token>       # or ARCHAI_DEV_MODE=1 for local development

ai-architect AGENT-SETUP                    # print the exact commands for this machine
ai-architect AGENT-SETUP --install-skill    # copy the skill for Claude Code and Codex
ai-architect AGENT-SETUP --register         # run `claude mcp add` and `codex mcp add`
```

`AGENT-SETUP` writes nothing unless you pass `--install-skill` or `--register`,
and it never prints your license token.

### Manual registration

=== "Claude Code"

    ```bash
    claude mcp add archai --scope user -e ARCHAI_LICENSE=YOUR_TOKEN -- ai-architect-mcp
    claude mcp list        # archai: ... ✓ Connected
    ```

    Skill: copy `ai_architect/agents/skills/archai/` to `~/.claude/skills/archai/`
    (all projects) or `.claude/skills/archai/` (one project).

=== "Codex"

    ```bash
    codex mcp add archai --env ARCHAI_LICENSE=YOUR_TOKEN -- ai-architect-mcp
    ```

    or in `~/.codex/config.toml` (or a trusted project's `.codex/config.toml`):

    ```toml
    [mcp_servers.archai]
    command = "ai-architect-mcp"
    env = { ARCHAI_LICENSE = "YOUR_TOKEN" }
    ```

    Skill: copy `ai_architect/agents/skills/archai/` to `~/.agents/skills/archai/`
    (all projects) or `.agents/skills/archai/` (one repository).

If `ai-architect-mcp` is not on `PATH` (common on Windows), use the Python
interpreter that has ArchAI installed instead:
`python -m ai_architect.agents.mcp_server`. `AGENT-SETUP` picks whichever works on
your machine.

## Tools

| Tool | Agent | Returns |
|---|---|---|
| `plumb_check_standards` | Plumb | Findings with status, file:line evidence, limitations and next steps. Filter with `statuses`; output is capped by `max_findings` and `max_evidence`. |
| `plumb_validate_config` | Plumb | Whether `archai_standards.yaml` content is valid, with the parsed rules or the exact error. |
| `plumb_rule_reference` | Plumb | The rule format, every rule kind with a YAML example, and the finding statuses. |
| `atlas_graph_overview` | Atlas | Module and edge counts, packages, most-coupled modules, parse failures, unsupported files. |
| `atlas_module` | Atlas | A module's imports and importers, each with file, line, scope and statement. |
| `atlas_import_path` | Atlas | The shortest import chain between two modules, each hop cited. |
| `atlas_export_bundle` | Atlas | Writes an OKF v0.2 bundle (the only tool that writes files). |
| `atlas_view` / `atlas_concept` | Atlas | Text views and structured concepts from a bundle. |
| `seismograph_dependents` | Seismograph | Modules that transitively import a module, with the linking imports. |
| `foreman_changed_modules` | Foreman | Changed Python files against a git base, mapped to modules and their importers. |
| `ledger_trace` | Ledger | Evidence a previous AUDIT run recorded (AI-generated, unverified). |

The server also provides an `archai_review` prompt (Claude Code lists MCP
prompts as slash commands) and an `archai://reference/rules` resource. Codex
documents MCP tools only; the skill covers the workflow there.

## How agents should report

The skill tells agents to:

- quote the rule id, `file:line` and import statement for every
  `VERIFIED_VIOLATION`;
- report `POTENTIAL_RISK` and `INSUFFICIENT_GRAPH_EVIDENCE` as what they are,
  never as violations or passes;
- treat a PASS as covering only the rule's declared scope;
- say so when only ArchAI's default rule ran;
- ask before writing or changing `archai_standards.yaml`;
- not run the LLM-backed commands unless the user asks.

## License and privacy

Tools follow the CLI's license rule: `ARCHAI_LICENSE` must be valid, or
`ARCHAI_DEV_MODE` set, in the MCP server's environment. Otherwise each call
returns a tool error explaining what to set. The tools read the repository
locally and send nothing anywhere.

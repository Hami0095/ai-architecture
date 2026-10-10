# CLI Command Reference

Every command `ai-architect` accepts, with all of its arguments and every way
to run it. This page describes what the code in `ai_architect/cli.py` does
today; where a command has a quirk or limitation, it is called out.

!!! info "Deterministic vs LLM-assisted"
    Only `CHECK-STANDARDS` and `OKF-VIEW` are fully deterministic: no LLM, no
    network. `AUDIT`, `G-REASON`, `EXPLAIN`, `IMPACT` and the `GITHUB`
    analysis subcommands send repository information to the configured LLM
    (by default the Ollama model `glm-4.6:cloud`, a **cloud** model). Treat
    their output as assistance, not verified fact.

## At a glance

| Command | Purpose | LLM | Network | Writes files |
|---|---|---|---|---|
| [`CHECK-STANDARDS`](#check-standards) | Check configured standards; cite evidence; export OKF | no | no | only what you ask for |
| [`OKF-VIEW`](#okf-view) | Browse an OKF bundle in the terminal | no | no | no |
| [`AUDIT`](#audit) | Broad architectural audit producing work items | yes | via LLM | `archai_report.json`, `archai_feedback.json` |
| [`IMPACT`](#impact) | Who depends on a symbol/file, plus a risk verdict | yes | via LLM | no |
| [`G-REASON`](#g-reason) | Ask a question about the dependency graph | yes | via LLM | no |
| [`EXPLAIN`](#explain) | Explain an item from the last AUDIT report | yes | via LLM | no |
| [`TRACE`](#trace) | Show recorded evidence for an AUDIT ticket | no | no | no |
| [`GITHUB …`](#github) | Repositories, PRs, remote audits, diff validation | mostly | GitHub (+LLM) | see below |
| [`SET-GITHUB-TOKEN`](#set-github-token) | GitHub token for this session | no | no | no |
| [`SET-PM-TOKEN`](#set-pm-token) | Jira/Trello credentials for this session | no | no | no |
| [`CONFIG`](#config) | Identity, mode, license, model, credentials | no | no | no |
| [`HELP`](#help) | Command table | no | no | no |
| [`EXIT`](#exit) | Leave the console | no | no | no |
| [`PLAN` / `SIMULATE` / `RELEASE-CONFIDENCE`](#legacy-planning-commands) | Deferred sprint planning | yes | via LLM | no |

## Ways to run a command

### 1. Interactive console

```bash
ai-architect
```

Prints the banner (identity, mode, license; see [Configuration &
Environment](configuration.md#modes)) and the command table, then reads
commands at the `ArchAI>` prompt.

```text
ArchAI> CHECK-STANDARDS . --verbose
ArchAI> OKF-VIEW bundle findings
ArchAI> exit
```

- Commands are case-insensitive (`check-standards` works); flags are not.
- Quote arguments containing spaces: `IMPACT "C:\My Repo" PaymentService`.
- On Windows, backslashes in paths are kept as typed.
- `Ctrl+C` does not exit; it prints a reminder. Use `exit`.

### 2. One-shot mode

Put the command after `ai-architect`; it runs once and returns an exit code.

```bash
ai-architect CHECK-STANDARDS . --json report.json
ai-architect OKF-VIEW bundle tree
ai-architect CONFIG
```

The process exit code is the command's return code (see each command). Commands
that do not define one exit `0`, **even when they print an error**; only
`CHECK-STANDARDS` and `OKF-VIEW` have exit codes you can rely on in scripts and CI.

### 3. Other entry points

```bash
python -m ai_architect.cli CHECK-STANDARDS .   # same as ai-architect, without the installed script
python archai.py CHECK-STANDARDS .             # from the repository root
```

### Global flags

These go **before** any command and are handled before the license check
unless noted.

| Flag | Effect |
|---|---|
| `--version` | Print the ArchAI version and the graph-core integrity hash, then exit. No license needed. |
| `--check-token <TOKEN>` | Print whether a license token is valid, its holder and expiry, then exit. No license needed. |
| `--license <TOKEN>` | Validate the token and use it **for this run only** (it is not saved). Invalid → error, exit. |
| `--test-mode` | Set the DEMO flag (`ARCHAI_TEST_MODE=1`). Nothing reads this flag yet; no mock data is loaded. Requires a license or dev mode. |

```bash
ai-architect --version
ai-architect --check-token eyJ1Ijoi...
ai-architect --license eyJ1Ijoi...                       # console
ai-architect --license eyJ1Ijoi... CHECK-STANDARDS .     # one-shot
```

### License gate

Every command except `--version` and `--check-token` requires either a valid
license token (`--license` or the `ARCHAI_LICENSE` environment variable) or
`ARCHAI_DEV_MODE` set. A missing, invalid or **expired** token stops the program
with the reason and exit code `3`. Details: [Configuration & Environment](configuration.md#license).

---

## CHECK-STANDARDS

Deterministically checks a Python repository against standards you configure,
and cites the source evidence for every finding. No LLM, no network.

```text
CHECK-STANDARDS [path] [--config FILE] [--no-defaults]
                [--json [FILE]] [--markdown FILE] [--verbose]
                [--okf-out DIR [--preview]] [--from-okf DIR]
```

| Argument | Default | Meaning |
|---|---|---|
| `path` | current directory | Repository to analyze. |
| `--config FILE` | `<path>/archai_standards.yaml` if it exists | Standards configuration. See [Standards & Rules](check-standards.md). |
| `--no-defaults` | off | Do not add ArchAI default rules. With no config and this flag, nothing is evaluated. |
| `--json` | off | Print the JSON report to stdout **instead of** the Markdown report. |
| `--json FILE` | off | Write the JSON report to `FILE`; Markdown still prints. |
| `--markdown FILE` | off | Also write the Markdown report to `FILE`. |
| `--verbose` | off | Markdown includes observed facts, verification details and every evidence line. |
| `--okf-out DIR` | off | Export the OKF v0.2 knowledge bundle to `DIR` and check its conformance. |
| `--preview` | off | After exporting, print the `OKF-VIEW` overview instead of the Markdown report. Needs `--okf-out`; cannot be combined with `--json` to stdout. |
| `--from-okf DIR` | off | Re-check using facts loaded from an existing bundle instead of reading source. Uses the bundle's rules unless `--config` is given; `path` is then ignored. |

**Every way to use it**

```bash
# Quick look: ArchAI default rule only (import cycles), Markdown to the terminal
ai-architect CHECK-STANDARDS .

# Your standards (picked up automatically from ./archai_standards.yaml)
ai-architect CHECK-STANDARDS path/to/repo

# Explicit config file, e.g. a shared company standard
ai-architect CHECK-STANDARDS path/to/repo --config standards/backend.yaml

# Only your rules, never the ArchAI defaults
ai-architect CHECK-STANDARDS . --config standards.yaml --no-defaults

# Full evidence in the terminal
ai-architect CHECK-STANDARDS . --verbose

# Machine-readable: JSON to stdout (Markdown suppressed), e.g. for jq or CI
ai-architect CHECK-STANDARDS . --json > report.json

# Save JSON and Markdown files, still print Markdown
ai-architect CHECK-STANDARDS . --json report.json --markdown report.md

# Export the OKF knowledge bundle
ai-architect CHECK-STANDARDS . --okf-out bundle

# Export and preview the bundle instead of the Markdown report
ai-architect CHECK-STANDARDS . --okf-out bundle --preview

# Everything at once
ai-architect CHECK-STANDARDS . --config standards.yaml --json r.json --markdown r.md --okf-out bundle --preview

# Re-check from a bundle alone (no source code needed), with the bundle's rules
ai-architect CHECK-STANDARDS --from-okf bundle

# Re-check a bundle against different rules
ai-architect CHECK-STANDARDS --from-okf bundle --config stricter.yaml --json
```

**Output**

- Markdown report (default) in five sections: what was checked, what was found,
  the evidence for each finding, what could not be verified, what to investigate next.
- Status lines (`OKF bundle written…`, `JSON report written…`) go to **stderr**,
  so stdout stays clean for `--json`.
- The meaning of `VERIFIED_VIOLATION`, `POTENTIAL_RISK`,
  `INSUFFICIENT_GRAPH_EVIDENCE` and `PASS` is defined in
  [Standards & Rules](check-standards.md#finding-statuses).

**Exit codes**

| Code | Meaning |
|---|---|
| `0` | No verified violations (there may still be risks or evidence gaps). |
| `1` | At least one `VERIFIED_VIOLATION`. |
| `2` | Usage error, invalid/missing config, missing path, unreadable bundle, or export refused. |
| `3` | License gate failed; the command never ran. |

!!! warning "Common surprises"
    - **No config → only one rule.** Without `archai_standards.yaml` only
      `archai.default.no-import-cycles` runs; the report and preview say so. A
      `PASS` then covers only that rule.
    - **Tests count too.** Nothing is excluded by default, so `tests/` and
      `scripts/` are part of the graph. Use `exclude:` in the config.
    - **`--okf-out` replaces the directory.** It refuses to touch a non-empty
      directory that is not an ArchAI bundle, but an existing bundle is overwritten.
    - Exporting inside the repository leaves a `bundle/` folder in `git status`.

---

## OKF-VIEW

Browse any OKF v0.2 bundle in the terminal, whether ArchAI wrote it or not
(Google's sample bundles work too). Read-only, no LLM, no network.

```text
OKF-VIEW <bundle-dir> [view | concept] [--status S] [--type T] [--raw] [--no-color]
```

| View | Shows |
|---|---|
| *(none)* / `overview` | Conformance (OKF §11), concept count, trust tiers, stale count, concept types. ArchAI bundles add repository/commit, analysis time, rule outcomes with each rule's origin, a defaults-only warning, limitations and top findings. |
| `tree` | Directory tree with each concept's type (25 per folder; then use `list`). |
| `list` | Every concept: id, type, description. Filter with `--type`. |
| `findings` | ArchAI findings grouped by status, with evidence locations; missing files are marked `(missing)`. Filter with `--status`. |
| `rules` / `results` / `modules` / `layers` | `list` pre-filtered to that ArchAI concept type. |
| `<concept>` | One concept rendered in full (see below). |

| Option | Meaning |
|---|---|
| `--status S` | For `findings`: `VIOLATION`, `RISK`, `NO-EVIDENCE` (or the full status name). |
| `--type T` | For `list` (and the shortcut views): case-insensitive substring of the concept type. |
| `--raw` | For a concept: also print the full YAML frontmatter. |
| `--no-color` | Plain text. Color is also off when output is not a terminal or `NO_COLOR` is set. |

**Finding a concept.** The argument is matched in this order: exact concept id
(path without `.md`, e.g. `findings/F-2b20e2df65e7`), exact title
(`app.domain`, `Revenue`), unique id ending (`F-2b20e2df65e7`), unique substring.
If several concepts match, they are listed and the exit code is `2`.

**A concept page shows** title, type, description, trust tier
(unverified / machine-confirmed / human-reviewed), lifecycle status, who
generated it and when, freshness against `stale_after`, tags; the body with every
link resolved to a concept id (`[missing]` for broken links, URLs kept);
sources grouped by target; backlinks ("linked from", and "imported by" for
modules). Findings add status, rule and verification method; Attested
Computations add `runtime`, `parameters`, `executor` and `attester`.

**Every way to use it**

```bash
ai-architect OKF-VIEW bundle                              # overview
ai-architect OKF-VIEW bundle tree
ai-architect OKF-VIEW bundle list
ai-architect OKF-VIEW bundle list --type "Python Module"
ai-architect OKF-VIEW bundle findings
ai-architect OKF-VIEW bundle findings --status violation
ai-architect OKF-VIEW bundle findings --status no-evidence
ai-architect OKF-VIEW bundle rules
ai-architect OKF-VIEW bundle results
ai-architect OKF-VIEW bundle modules
ai-architect OKF-VIEW bundle layers
ai-architect OKF-VIEW bundle F-2b20e2df65e7               # a finding
ai-architect OKF-VIEW bundle app.domain.order             # a module
ai-architect OKF-VIEW bundle rules/no-cycles --raw        # with full frontmatter
ai-architect OKF-VIEW bundle analysis/run                 # provenance of the analysis
ai-architect OKF-VIEW bundle findings --no-color > findings.txt
```

**Exit codes:** `0` shown; `2` bundle not found, no concepts, concept not found
or ambiguous, or usage error.

---

## AUDIT

LLM-assisted architectural audit. Builds the dependency graph from the AST,
then runs a pipeline of LLM agents (discovery, context, gap analysis, ticket
generation, verification) that produces a list of work items.

```text
AUDIT [path] [--goal TEXT] [--verbose] [--diagnostics]
```

| Argument | Default | Meaning |
|---|---|---|
| `path` | current directory | Repository to audit. |
| `--goal TEXT` | "Improve reliability and architectural integrity" | Steers the audit toward an outcome. |
| `--verbose` | off | Show agent logs and latencies. |
| `--diagnostics` | off | Only print the directory structure and (truncated) file contents ArchAI would read; no agents run (the Ollama check still runs first). |

```bash
ai-architect AUDIT .
ai-architect AUDIT path/to/repo --goal "Separate the persistence layer"
ai-architect AUDIT . --verbose
ai-architect AUDIT . --diagnostics      # what would be read, without running agents
```

- Checks Ollama first (see [LLM runtime](configuration.md#llm-runtime)); exits
  if it is not installed or not running, and may **pull a model** or ask you to pick one.
- Writes `archai_report.json` in the **current directory**, used by `TRACE` and `EXPLAIN`.
- In an interactive terminal it asks "Was this audit helpful?" and appends the
  answer to `archai_feedback.json`.
- Findings, ticket evidence and line references are written by the LLM and are
  not verified. For verified findings, use `CHECK-STANDARDS`.
- The pipeline still builds a sprint plan internally; it is only printed when
  `ARCHAI_ENABLE_LEGACY_PLANNING=1`.

---

## IMPACT

Lists the functions and modules that call or import a target symbol or file,
with graph metrics, then asks the LLM for a risk verdict.

```text
IMPACT <path> <target> [--verbose]
```

| Argument | Meaning |
|---|---|
| `path` | Repository root. |
| `target` | A symbol (`PaymentService`, `GraphEngine.analyze_project`) or a file (`utils.py`). |
| `--verbose` | Show the analysis logs. |

```bash
ai-architect IMPACT . PaymentService
ai-architect IMPACT . ai_architect.core_ai.auditor
ai-architect IMPACT . utils.py --verbose
```

- The caller trace is deterministic but **name-based**: any call to a function
  with the same name matches, so unrelated functions can appear. Trace depth is fixed at 3.
- Risk level, score, confidence and rationale come from the LLM. If the LLM
  fails, the result is `UNKNOWN` with "insufficient data".

---

## G-REASON

Sends the full dependency-graph summary (modules, classes, functions,
imports, call edges, metrics) to the LLM together with your question.

```text
G-REASON <path> <question>
```

```bash
ai-architect G-REASON . "Which modules couple the API layer to the database?"
ai-architect G-REASON path/to/repo "Is there a cycle between core and infrastructure?"
```

- Quote the question. Only the first two arguments are used.
- The answer is free text from the LLM. For questions with a definite answer
  (cycles, forbidden imports, coupling), `CHECK-STANDARDS` gives a verified one.
- The whole graph summary leaves the machine when the model is a cloud model.

---

## EXPLAIN

Asks the LLM to justify an item from the most recent `AUDIT` report.

```text
EXPLAIN <intent> <target> [--json]
```

| Argument | Meaning |
|---|---|
| `intent` | `PRIORITY`, `EFFORT`, `RISK` or `DEPENDENCIES` (free text is passed through). |
| `target` | A ticket id (`T001`) or a module/file named in the report. |
| `--json` | Print the structured explanation as JSON instead of the narrative. |

```bash
ai-architect EXPLAIN RISK "ai_architect/cli.py"
ai-architect EXPLAIN EFFORT T001
ai-architect EXPLAIN PRIORITY T005 --json
ai-architect EXPLAIN DEPENDENCIES T002
```

Reads these files from the **current directory** when present:
`archai_report.json`, `risk-map.json`, `dependency-graph.json`,
`historical-metrics.json`. Run it in the folder where you ran `AUDIT`. With none
of them present the LLM has nothing to cite and should answer
`INSUFFICIENT_EVIDENCE`.

---

## TRACE

Shows what the `AUDIT` pipeline recorded as evidence for a ticket.

```text
TRACE <ticket_id>
```

```bash
ai-architect TRACE T001
```

Reads `archai_report.json` from the current directory ("No active report
found. Run AUDIT first." otherwise). Prints the responsible agent, file, line
range, confidence and description. These were produced by the LLM; check
them against the source.

---

## GITHUB

```text
GITHUB CONNECT <owner/repo>
GITHUB PRS <owner/repo>
GITHUB ANALYZE <owner/repo> <pr_number> <local_path> [--publish]
GITHUB AUDIT <owner/repo> [--goal TEXT]
GITHUB VALIDATE-LOCAL <path> [base_branch]
```

`owner/repo` may also be a full `https://github.com/owner/repo` URL. A token
(see [`SET-GITHUB-TOKEN`](#set-github-token)) is needed for private
repositories and higher rate limits.

| Subcommand | What it does | LLM | Side effects |
|---|---|---|---|
| `CONNECT` | Fetch repository metadata (name, stars, forks, description). | no | none |
| `PRS` | List open pull requests. | no | none |
| `ANALYZE` | For the PR's first added/modified file, run `IMPACT` against your local checkout, plus legacy task generation and a sprint-confidence estimate. | yes | `--publish` **posts a comment on the PR** |
| `AUDIT` | Shallow-clone the repository into a temp folder and run `AUDIT` on it. | yes | clone is left in the temp folder; writes `archai_report.json` |
| `VALIDATE-LOCAL` | For each `.py` file changed versus `base_branch` (default `main`), run `IMPACT`. GitHub is not contacted. | yes | none |

```bash
ai-architect GITHUB CONNECT Hami0095/ai-architecture
ai-architect GITHUB PRS https://github.com/Hami0095/ai-architecture
ai-architect GITHUB ANALYZE Hami0095/ai-architecture 42 .
ai-architect GITHUB ANALYZE Hami0095/ai-architecture 42 . --publish
ai-architect GITHUB AUDIT Hami0095/ai-architecture --goal "Find layering problems"
ai-architect GITHUB VALIDATE-LOCAL .
ai-architect GITHUB VALIDATE-LOCAL . develop
```

!!! warning
    `GITHUB ANALYZE --publish` writes to the pull request on GitHub as the
    token's owner. Run without `--publish` first to see what would be posted.
    The comment includes a "Sprint Confidence" section from the deferred
    planning engine.

---

## SET-GITHUB-TOKEN

```text
SET-GITHUB-TOKEN <token>
```

Sets `ARCHAI_GITHUB_TOKEN` for the **current console session only**; it is
gone when ArchAI exits. To keep a token, set the environment variable in your
shell or `github.token` in `archai_config.yaml`.

## SET-PM-TOKEN

```text
SET-PM-TOKEN JIRA <token>
SET-PM-TOKEN TRELLO <token> [api_key]
```

Sets `ARCHAI_JIRA_TOKEN`, or `ARCHAI_TRELLO_TOKEN` (and
`ARCHAI_TRELLO_API_KEY`) for the current session only. No current command
pushes work to Jira or Trello; the credentials are used by the connector
library code only.

## CONFIG

```text
CONFIG
```

Prints identity and its source, access mode and flags, config profile, license
state, LLM provider and model, and which credentials are present. Credentials
are reported as `configured`, `placeholder value` (for example the
`your-github-token` placeholder shipped in `archai_config.yaml`) or
`not configured`; **nothing is contacted**, so "configured" does not mean the
credential works.

## HELP

```text
HELP
```

Prints the command table that is also shown at startup.

## EXIT

```text
exit | quit | phir-milty-hain | phir milty hain
```

Leaves the interactive console. Case-insensitive.

---

## Legacy planning commands

Sprint planning and estimation are no longer part of ArchAI's product direction.
These commands print a deferral notice and return exit code `2`, unless
`ARCHAI_ENABLE_LEGACY_PLANNING=1` is set. Their code is unchanged and LLM-based.

```text
PLAN <path> <goal> [--team-size N] [--days N] [--velocity F]
SIMULATE <path> <goal> [--team-size N] [--days N] [--velocity F]
SIMULATE <ticket_id> [--team-size N] [--days N] [--velocity F]
RELEASE-CONFIDENCE <path> <goal> [--team-size N] [--days N] [--velocity F]
```

| Option | Default |
|---|---|
| `--team-size` | 3 |
| `--days` | 5 |
| `--velocity` | 0.8 |

```bash
ARCHAI_ENABLE_LEGACY_PLANNING=1 ai-architect PLAN . "Add OAuth2 support" --team-size 4 --days 10
ARCHAI_ENABLE_LEGACY_PLANNING=1 ai-architect SIMULATE T001 --team-size 2
```

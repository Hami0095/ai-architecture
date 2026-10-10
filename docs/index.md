# ArchAI

**Understand the code. Check the rules. Prove the findings.**

ArchAI checks a Python repository against engineering standards you configure,
and cites the source evidence (file and line) for every finding. The
repository knowledge, rules and findings can be exported as an
[Open Knowledge Format](https://github.com/GoogleCloudPlatform/open-knowledge-format)
(OKF) v0.2 bundle and browsed or re-checked from that bundle alone.

Its rule is **Receipts or Silence**: a finding is a *verified violation* only
when every supporting fact is cited from source. When static analysis cannot
settle a question, ArchAI says so instead of guessing.

## Install

```bash
git clone https://github.com/Hami0095/ai-architecture.git
cd ai-architecture
pip install -e .
```

Python 3.10+. A license token (or `ARCHAI_DEV_MODE=1` for local development)
is required; see [License](cli/configuration.md#license). Ollama is only
needed for the LLM-assisted commands.

## First commands

```bash
ai-architect CHECK-STANDARDS path/to/repo --okf-out bundle --preview
ai-architect OKF-VIEW bundle findings
```

## Commands

| | Command | |
|---|---|---|
| **Deterministic** | [`CHECK-STANDARDS`](cli/commands.md#check-standards) | Check standards with cited evidence; JSON, Markdown and OKF output |
| | [`OKF-VIEW`](cli/commands.md#okf-view) | Browse any OKF bundle in the terminal |
| **LLM-assisted** | [`AUDIT`](cli/commands.md#audit), [`IMPACT`](cli/commands.md#impact), [`G-REASON`](cli/commands.md#g-reason), [`EXPLAIN`](cli/commands.md#explain) | Exploration and explanation; not verified |
| **Integrations** | [`GITHUB`](cli/commands.md#github) | Repositories, pull requests, diff validation |
| **Session** | [`CONFIG`](cli/commands.md#config), [`SET-GITHUB-TOKEN`](cli/commands.md#set-github-token), [`SET-PM-TOKEN`](cli/commands.md#set-pm-token), [`TRACE`](cli/commands.md#trace), [`HELP`](cli/commands.md#help) | |

Sprint planning (`PLAN`, `SIMULATE`, `RELEASE-CONFIDENCE`) comes from ArchAI's
sprint-planning case study; see [Sprint-planning commands](cli/commands.md#sprint-planning-commands-case-study).

## Documentation

- [CLI Command Reference](cli/commands.md): every command, argument and exit code.
- [Standards & Rules](cli/check-standards.md): configuration, the five rule kinds, finding statuses, JSON and OKF output.
- [Configuration & Environment](cli/configuration.md): license, modes, config files, environment variables, LLM runtime.
- [Recipes](cli/examples.md): CI gating, investigating findings, sharing bundles, reproducibility.

## What ArchAI does not do

- Analyze languages other than Python (they are reported as not covered).
- See runtime wiring such as dependency injection or plugins.
- Measure test coverage.
- Verify anything produced by the LLM-assisted commands.

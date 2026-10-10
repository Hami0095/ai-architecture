# Configuration & Environment

Everything that changes how `ai-architect` behaves besides command
arguments: license, modes, configuration files, environment variables, and
the files ArchAI reads and writes.

## License

Every command except `--version` and `--check-token` needs a valid license
token or dev mode.

| Way | Lasts |
|---|---|
| `ai-architect --license <TOKEN> …` | This run only. |
| `ARCHAI_LICENSE=<TOKEN>` environment variable | As long as the variable is set. |

```powershell
# Windows: persist for new terminals
setx ARCHAI_LICENSE "<TOKEN>"
```

```bash
# macOS / Linux: add to your shell profile
export ARCHAI_LICENSE="<TOKEN>"
```

```bash
ai-architect --check-token <TOKEN>   # VALID / EXPIRED / INVALID, holder and expiry
```

Tokens are signed records of a holder name, a start time and an expiry. All
valid tokens grant the same access; there are no roles. A token is checked on
every start: missing, tampered and **expired** tokens stop the program with the
reason and exit code `3`. Maintainers create tokens with
`python scripts/generate_token.py <holder> [days]`.

!!! warning
    The signing key is in the source code (`ai_architect/utils/license.py`),
    so anyone with the source can create tokens. The license is not an
    access-control boundary in its current form.

## Modes

The startup banner and `CONFIG` show:

```text
 IDENTITY: Hami0095 (license holder)
 MODE: LICENSED | PROFILE: dev | VERSION: 0.2.1-pilot
 LICENSE: VALID - Hami0095, expires 2026-11-08 (30 days left)
```

| Mode / flag | Set by | Effect |
|---|---|---|
| `LICENSED` | a valid token | Normal use. IDENTITY is the token holder. |
| `DEV` | `ARCHAI_DEV_MODE` (any non-empty value) without a valid token | License check skipped for local development. IDENTITY is `user_id` from config, labelled unlicensed. |
| `BLOCKED` | neither | The program stops before any command runs. |
| `+ DEMO` | `--test-mode` | Sets `ARCHAI_TEST_MODE=1`. Nothing reads it yet; no mock data is loaded. |
| `+ LEGACY-PLANNING` | `ARCHAI_ENABLE_LEGACY_PLANNING=1` | Re-enables `PLAN`, `SIMULATE`, `RELEASE-CONFIDENCE` and the sprint plan in `AUDIT` output. |
| `PROFILE` | `ARCHAI_ENV` (default `dev`) | Also loads `config.<profile>.yaml` / `.json`. |

## Configuration files

At startup ArchAI first loads a `.env` file into the environment (found by
`python-dotenv`; it never overrides variables that are already set). It then
reads these files from the **current directory**, in order; later files add
or overwrite top-level keys:

1. `config.<profile>.yaml`, then `config.<profile>.json` (profile from `ARCHAI_ENV`)
2. `archai_config.yaml`, then `archai_config.json`
3. `~/.archai/config.yaml`

`archai_config.yaml` keys used by the CLI:

| Key | Default | Used for |
|---|---|---|
| `model` | `glm-4.6:cloud` | LLM model name |
| `ai.provider` | `ollama` | LLM provider (only `ollama` is implemented) |
| `user_id` | `Anonymous-Engineer` | IDENTITY when unlicensed; encryption seed for usage tracking |
| `github.token` | | GitHub API access |
| `jira.server`, `jira.email`, `jira.token` | | Jira connector |
| `trello.api_key`, `trello.token` | | Trello connector |
| `google_drive_token` | | Google Drive connector |

**Environment variables override config keys**: the variable name is
`ARCHAI_` plus the key in upper case with dots as underscores. For example
`ARCHAI_MODEL=qwen2.5-coder` overrides `model`, and `ARCHAI_GITHUB_TOKEN`
overrides `github.token`.

!!! note
    Standards rules live in a separate file, `archai_standards.yaml`, in the
    analyzed repository. See [Standards & Rules](check-standards.md).

## Environment variables

| Variable | Effect |
|---|---|
| `ARCHAI_LICENSE` | License token. |
| `ARCHAI_DEV_MODE` | Skip the license check (local development). |
| `ARCHAI_ENV` | Config profile (default `dev`). |
| `ARCHAI_ENABLE_LEGACY_PLANNING` | `1` re-enables the deferred planning commands. |
| `ARCHAI_TEST_MODE` | Set by `--test-mode`; currently unused. |
| `ARCHAI_MODEL`, `ARCHAI_AI_PROVIDER` | Override the LLM model / provider. |
| `ARCHAI_GITHUB_TOKEN` | GitHub token (also set by `SET-GITHUB-TOKEN`). |
| `ARCHAI_JIRA_TOKEN`, `ARCHAI_TRELLO_TOKEN`, `ARCHAI_TRELLO_API_KEY` | PM credentials (also set by `SET-PM-TOKEN`). |
| `ARCHAI_<KEY>` | Overrides any config key (see above). |
| `SOURCE_DATE_EPOCH` | Fixes the `CHECK-STANDARDS` timestamp for reproducible output. |
| `NO_COLOR` | Disables color in `OKF-VIEW`. |
| `ARCHAI_RUN_LLM_TESTS` | `1` runs the test-suite tests that call a real LLM. |
| `OKF_REFERENCE_SRC` | Path to the OKF repository's `src/`; enables the reference-parser cross-check test. |

## LLM runtime

Commands that use an LLM (`AUDIT`, `IMPACT`, `G-REASON`, `EXPLAIN`, `GITHUB
ANALYZE/AUDIT/VALIDATE-LOCAL`, legacy planning) first check Ollama:

- Ollama not installed → exits with installation instructions.
- Ollama not running → exits asking you to run `ollama serve`.
- No models installed → **pulls** the configured model (can be large).
- Configured model missing but others installed → falls back to the first
  installed model whose name contains `qwen`, `coder`, `gemma`, `llama` or
  `glm`, otherwise asks you to choose.

The default model `glm-4.6:cloud` runs in the cloud: prompts, which contain
repository structure, file excerpts and the dependency graph, leave your
machine. Set `model` to a local model to keep everything on your machine.
`CHECK-STANDARDS` and `OKF-VIEW` never use the LLM.

## Files ArchAI writes

| File | Written by | Where |
|---|---|---|
| `archai.log` | every run (skipped if the folder is not writable) | current directory |
| `archai_report.json` | `AUDIT`, `GITHUB AUDIT` | current directory |
| `archai_feedback.json` | `AUDIT` feedback prompt | current directory |
| report / bundle files | `CHECK-STANDARDS --json FILE`, `--markdown FILE`, `--okf-out DIR` | where you say |
| temporary clone | `GITHUB AUDIT` | system temp folder (not cleaned up) |

`TRACE` and `EXPLAIN` read `archai_report.json` from the current directory, so
run them in the folder where you ran `AUDIT`.

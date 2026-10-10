# Standards & Rules

How to configure `CHECK-STANDARDS`, what each rule checks, how findings are
classified, and what the JSON report and OKF bundle contain. For the command
line itself see [CLI Command Reference](commands.md#check-standards).

## The configuration file

`CHECK-STANDARDS` reads `archai_standards.yaml` from the repository root, or
the file given with `--config`. An annotated example ships in
`examples/archai_standards.example.yaml`.

```yaml
version: 1                      # optional; only 1 is supported
source_roots: ["src"]           # optional; import roots
exclude: ["migrations/*"]       # optional; paths removed from the analysis
defaults: auto                  # optional; auto | true | false
layers:                         # optional; named groups of modules
  domain: ["myapp.domain"]
  infrastructure: ["myapp.db", "myapp.adapters"]
rules:                          # the standards to check
  - id: domain-is-pure
    kind: layer_boundary
    layer: domain
    forbidden_layers: [infrastructure]
    description: Domain modules must not import infrastructure.
    rationale: The domain model should be testable without I/O.
```

### Top-level keys

| Key | Type | Default | Meaning |
|---|---|---|---|
| `version` | integer | `1` | Config format version. Anything else is rejected. |
| `source_roots` | list of paths | `[]` | Directories that are import roots. If empty and the repository has a `src/` folder without `__init__.py`, `src` is used automatically (the report says so). |
| `exclude` | list of globs | `[]` | Repository-relative paths (forward slashes) matched with `fnmatch`; `*` also matches `/`, so `tests/*` excludes everything under `tests/`. Excluded modules are removed from the analyzed system entirely. |
| `defaults` | `auto` / `true` / `false` | `auto` | ArchAI default rules: `auto` adds them only when `rules` is empty; `true` always (unless a rule of the same kind is configured); `false` never. `--no-defaults` forces `false`. |
| `layers` | map of name → patterns | `{}` | Named module groups used by `layer_boundary`. |
| `rules` | list | `[]` | The rules. Unknown top-level keys are rejected. |

### Module patterns

Used in `layers`, `from`, `to` and `scope`, and matched against importable
dotted module names (`myapp.domain.order`, not file paths).

| Pattern | Matches |
|---|---|
| `myapp.domain` | `myapp.domain` and everything beneath it (`myapp.domain.order`, …). |
| `myapp.*.models` | `fnmatch` on the full name, used when the pattern contains `*`, `?` or `[`. `*` also crosses dots. |
| `*` | Every module. |

Note that `myapp.domain` does **not** match `myapp.domainx` or `myapp.domain_helpers`.

### Fields every rule has

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Stable identifier: 1–100 letters, digits, `.`, `_`, `-`. Must be unique. Finding IDs are derived from it. |
| `kind` | yes | One of the five kinds below. |
| `description` | no | One line shown in reports. |
| `rationale` | no | Why the rule exists; stored with the rule in the OKF bundle. |

## The five rule kinds

### `forbidden_dependency`

Modules matching `from` must not import modules matching `to`.

| Field | Required | Meaning |
|---|---|---|
| `from` | yes | Patterns for the importing modules (the rule's scope). |
| `to` | yes | Patterns for the forbidden targets. Targets that also match `from` are ignored. |

```yaml
- id: api-not-db
  kind: forbidden_dependency
  from: ["myapp.api"]
  to: ["myapp.db", "sqlalchemy_models"]
```

Reports one finding per (importer, target) pair, citing every import line.
Module- and function-level imports are `VERIFIED_VIOLATION`; imports that exist
only under `if TYPE_CHECKING:` or as a literal `importlib.import_module("…")`
are `POTENTIAL_RISK`. If `from` or `to` matches no module, the rule reports
`INSUFFICIENT_GRAPH_EVIDENCE` rather than passing, because a typo would look identical.

### `layer_boundary`

A named layer must not depend on certain other layers, or may depend only on
an allowed set.

| Field | Required | Meaning |
|---|---|---|
| `layer` | yes | A layer declared under `layers`. |
| `forbidden_layers` | one of the two | Layers this layer must not import. |
| `allowed_layers` | one of the two | The only other layers it may import (`[]` = none). |

```yaml
- id: domain-forbids-infra
  kind: layer_boundary
  layer: domain
  forbidden_layers: [infrastructure, interface]

- id: domain-is-pure
  kind: layer_boundary
  layer: domain
  allowed_layers: []
```

Imports from the layer into modules that belong to **no** layer are outside
the rule; their count appears in the result's limitations. Modules matching
more than one layer are reported as `INSUFFICIENT_GRAPH_EVIDENCE` and skipped,
never assigned by guesswork.

### `circular_dependency`

No import cycles among modules in scope.

| Field | Required | Default |
|---|---|---|
| `scope` | no | `["*"]` |

```yaml
- id: no-cycles
  kind: circular_dependency
  scope: ["myapp"]
```

Each cycle is reported once per strongly connected group, with a concrete
path (`a -> b -> c -> a`) and the import line for every step. Cycles made
only of module-level imports are `VERIFIED_VIOLATION`. A cycle that closes
only through a function-level, `TYPE_CHECKING` or dynamic import is
`POTENTIAL_RISK`, since deferring an import is a common way to break cycles deliberately.

### `coupling_threshold`

A module must not depend on (or be depended on by) more than `max` internal modules.

| Field | Required | Default | Meaning |
|---|---|---|---|
| `max` | yes | | Non-negative integer. Values above it are violations; equal passes. |
| `metric` | no | `fan_out` | `fan_out`: distinct internal modules imported. `fan_in`: distinct internal modules importing it. |
| `scope` | no | `["*"]` | Which modules are measured. |

```yaml
- id: bounded-fan-out
  kind: coupling_threshold
  metric: fan_out
  max: 12
  scope: ["myapp"]
```

Findings report the measured value, the threshold and every counted module
with an import line. Only runtime imports (module- and function-level) are
counted; standard-library and third-party imports never are. If the runtime
count is within the limit but adding type-checking/dynamic imports would exceed
it, the finding is `POTENTIAL_RISK`. The rule result includes the maximum and
median measured values.

### `required_tests`

Each module in scope has a test file at a conventional path.

| Field | Required | Default | Meaning |
|---|---|---|---|
| `scope` | yes | | Modules that need tests. |
| `test_paths` | yes | | One or more path templates; any existing one satisfies the rule. |
| `include_packages` | no | `false` | Also require tests for `__init__.py` packages. |

Template placeholders (each template must use at least one):

| Placeholder | For `myapp.services.billing` |
|---|---|
| `{leaf}` | `billing` |
| `{module}` | `myapp.services.billing` |
| `{module_path}` | `myapp/services/billing` |
| `{parent_path}` | `myapp/services` |

```yaml
- id: services-have-tests
  kind: required_tests
  scope: ["myapp.services"]
  test_paths:
    - "tests/test_{leaf}.py"
    - "tests/{parent_path}/test_{leaf}.py"
```

Test modules are never required to have tests themselves (names starting
`test_` or ending `_test`, or files under a `tests/` or `test/` folder). If no
conventional file exists but some test module imports the module, the
finding is `POTENTIAL_RISK`; otherwise `VERIFIED_VIOLATION`. This checks file
existence only, **not coverage**.

## ArchAI default rules

When no rules are configured (and `defaults` is not `false`), ArchAI evaluates:

| ID | Kind | Note |
|---|---|---|
| `archai.default.no-import-cycles` | `circular_dependency` over all modules | An ArchAI heuristic, not your organization's standard. |

Reports, JSON and the OKF preview label it `archai-default` and warn that only
defaults ran.

## Finding statuses

| Status | Meaning |
|---|---|
| `VERIFIED_VIOLATION` | The rule is broken and every supporting fact was extracted deterministically from source and is cited. |
| `POTENTIAL_RISK` | The facts match the rule's pattern, but whether it is a breach depends on something static analysis cannot settle. |
| `INSUFFICIENT_GRAPH_EVIDENCE` | Part of the scope could not be evaluated: syntax errors, scopes that match nothing, internal imports that resolve to no module, non-literal dynamic imports, overlapping layers, or no Python files. Silence there is **not** compliance. |
| `PASS` | Rule outcome only: evaluated over its declared scope with no findings. Says nothing outside that scope. |

A rule's outcome is its most severe finding status, in the order above.
Each finding's `verification` states `method: deterministic-static-analysis`,
`llm_assisted: false`, and `evidence_completeness` (`complete` or `partial`).
No numeric confidence scores are produced.

### What counts as an import

| Code | Recorded as | Counts for |
|---|---|---|
| `import a.b` / `from a import b` at module level (incl. inside `try`, `if`, class bodies) | `module` scope | all rules |
| The same inside a function or lambda | `function` scope | all rules; cycles only as `POTENTIAL_RISK` |
| Inside `if TYPE_CHECKING:` | `type_checking` scope | `POTENTIAL_RISK` only |
| `importlib.import_module("a.b")` / `__import__("a.b")` with a literal | `dynamic` scope | `POTENTIAL_RISK` only |
| The same with a non-literal argument | not resolvable | `INSUFFICIENT_GRAPH_EVIDENCE` |
| Text in comments, docstrings or strings | nothing | nothing |

`from pkg import name` points at `pkg.name` when that is a module, otherwise at
`pkg`. Relative imports are resolved against the importing module's package.
Imports naming an internal top-level package that resolve to nothing are
reported, not dropped.

## JSON report

`--json` produces one object with these top-level keys (schema
`archai.standards/1`):

| Key | Contents |
|---|---|
| `schema_version` | `"archai.standards/1"` |
| `provenance` | `tool` (name, version, `engine_sha256`), `repository` (name, `git_commit`, `git_dirty`), `analyzed_at`, `duration_ms`, `python_version`, `fact_source` (`source-extraction` / `okf-bundle`), `llm_used`, `network_used` |
| `config` | Config file name and SHA-256, `uses_defaults_only`, `source_roots`, `exclude`, `layers`, rules with `origin` |
| `analysis` | Module and edge counts, `parse_failures`, unresolved/dynamic import counts, `unsupported_files` by extension, `excluded_modules` |
| `summary` | Rule outcome counts, finding counts by status, `findings_with_line_evidence` |
| `rule_results` | Per rule: `rule_id`, `kind`, `origin`, `params`, `outcome`, `scope_stats`, `limitations`, `findings` |
| `limitations` | Run-wide caveats (defaults-only, unsupported languages, parse failures, exclusions) |

Each finding: `id`, `rule_id`, `rule_description`, `category`, `status`,
`summary`, `modules`, `files`, `evidence` (each `{kind, file, line, detail}`;
`line` is `null` when the fact concerns a whole file), `observed`, `expected`,
`evaluation`, `verification`, `limitations`, `next_steps`.

```bash
# Verified violations only
ai-architect CHECK-STANDARDS . --json | jq '.rule_results[].findings[] | select(.status=="VERIFIED_VIOLATION") | .summary'
```

## OKF knowledge bundle

`--okf-out DIR` writes an [Open Knowledge Format](https://github.com/GoogleCloudPlatform/open-knowledge-format)
v0.2 bundle: markdown files with YAML frontmatter that any OKF consumer can read.

```text
index.md                    okf_version: "0.2"
analysis/run.md             ArchAI Analysis Run   provenance, scope, limitations
analysis/file-inventory.md  ArchAI File Inventory file paths only, no contents
modules/<module>.md         Python Module         imports with line and scope; links to targets
layers/<layer>.md           ArchAI Layer
rules/<rule-id>.md          ArchAI Standard Rule  origin, params, rationale
results/<rule-id>.md        ArchAI Rule Result    outcome, scope stats, links to findings
findings/<finding-id>.md    ArchAI Finding        evidence as OKF sources + footnotes
```

- No source code is copied beyond the text of import statements.
- Every concept's trust tier is *unverified*: extraction is not independent
  confirmation, so ArchAI never writes `verified`.
- `--from-okf DIR` rebuilds the graph and rules from the bundle and re-checks;
  the test suite asserts the results equal the from-source run.
- Browse it with [`OKF-VIEW`](commands.md#okf-view).

## Reproducing a result

```bash
git -C path/to/repo checkout <commit>
SOURCE_DATE_EPOCH=1790000000 ai-architect CHECK-STANDARDS path/to/repo \
    --config standards.yaml --json run.json --okf-out bundle
```

With the same commit, config, ArchAI engine hash and `SOURCE_DATE_EPOCH`,
findings and bundle files are identical apart from `duration_ms`. The git
remote URL is never recorded, because clone URLs can contain tokens.

## Configuration errors

Rejected with a message naming the problem and exit code `2`: unknown
top-level keys or rule kinds; missing `id`, `kind` or required fields; invalid
or duplicate ids; undeclared layers; both or neither of
`forbidden_layers`/`allowed_layers`; non-integer or negative `max`; test path
templates without a placeholder; unsupported `version`; YAML that does not
parse; a `--config` file that does not exist.

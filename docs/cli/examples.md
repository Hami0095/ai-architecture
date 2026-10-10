# Recipes

Task-oriented workflows. Every command here is documented in the
[CLI Command Reference](commands.md). The examples use one-shot mode; inside
the console, type the same thing without `ai-architect`.

## First run on an unfamiliar repository

```bash
cd path/to/repo
ai-architect CHECK-STANDARDS .                       # ArchAI default rule: import cycles
ai-architect CHECK-STANDARDS . --okf-out ../repo-bundle --preview
ai-architect OKF-VIEW ../repo-bundle modules         # what modules exist
ai-architect OKF-VIEW ../repo-bundle myapp.core      # what one module imports, and who imports it
```

Exporting outside the repository keeps `git status` clean.

## Adopt your team's standards

1. Copy the example and edit the patterns to your module names:

    ```bash
    cp path/to/ai-architecture/examples/archai_standards.example.yaml archai_standards.yaml
    ```

2. Check that every rule's scope matches something. A rule with an empty
   scope reports `INSUFFICIENT_GRAPH_EVIDENCE`, never `PASS`:

    ```bash
    ai-architect CHECK-STANDARDS . --verbose
    ```

3. Exclude code that should not be judged:

    ```yaml
    exclude: ["tests/*", "scripts/*", "migrations/*"]
    ```

4. Commit `archai_standards.yaml` so everyone checks the same rules.

## Gate a CI pipeline

`CHECK-STANDARDS` exits `1` on any verified violation and `2` on a broken
config, so it can fail a build directly.

```yaml
# .github/workflows/standards.yml (sketch)
- run: pip install -e path/to/ai-architecture
- run: ai-architect CHECK-STANDARDS . --json standards.json --markdown standards.md
  env:
    ARCHAI_LICENSE: ${{ secrets.ARCHAI_LICENSE }}
- uses: actions/upload-artifact@v4
  if: always()
  with: { name: standards-report, path: "standards.*" }
```

Potential risks and evidence gaps do not fail the build. To fail on them too:

```bash
ai-architect CHECK-STANDARDS . --json report.json
python -c "import json,sys; s=json.load(open('report.json'))['summary']['findings']; sys.exit(1 if s['POTENTIAL_RISK'] or s['INSUFFICIENT_GRAPH_EVIDENCE'] else 0)"
```

## Investigate a violation

```bash
ai-architect OKF-VIEW bundle findings --status violation   # pick an ID
ai-architect OKF-VIEW bundle F-2b20e2df65e7                # evidence with file:line
ai-architect OKF-VIEW bundle ai_architect.cli              # the module's imports and importers
```

Or in the Markdown report: `ai-architect CHECK-STANDARDS . --verbose`.

## Share results without sharing code

The OKF bundle contains module names, file paths and import statements, but
no other source code:

```bash
ai-architect CHECK-STANDARDS . --okf-out standards-bundle
zip -r standards-bundle.zip standards-bundle
```

The recipient can browse it, or re-check it against their own rules:

```bash
ai-architect OKF-VIEW standards-bundle
ai-architect CHECK-STANDARDS --from-okf standards-bundle --config their-rules.yaml
```

## Reproduce an analysis exactly

```bash
git -C repo checkout 1cb2d372aac2
SOURCE_DATE_EPOCH=1790000000 ai-architect CHECK-STANDARDS repo \
    --config standards.yaml --json run.json --okf-out bundle
```

Compare `provenance.tool.engine_sha256` and `config.sha256` in `run.json`
between runs: equal inputs give equal findings.

## Ask the LLM, then verify

```bash
ai-architect G-REASON . "Does the API layer reach the database directly?"
```

Turn the answer into a rule and check it deterministically:

```yaml
- id: api-not-db
  kind: forbidden_dependency
  from: ["myapp.api"]
  to: ["myapp.db"]
```

```bash
ai-architect CHECK-STANDARDS . --config archai_standards.yaml
```

## LLM-assisted audit

```bash
ai-architect AUDIT . --goal "Separate persistence from domain logic"
ai-architect TRACE T001                 # what the pipeline recorded for a ticket
ai-architect EXPLAIN RISK T001          # LLM justification
ai-architect IMPACT . PaymentService    # who calls it, before you change it
```

Run `TRACE` and `EXPLAIN` in the same folder as `AUDIT`; they read
`archai_report.json` from there.

## Pull requests

```bash
ai-architect GITHUB PRS owner/repo
ai-architect GITHUB ANALYZE owner/repo 42 .            # preview the assessment
ai-architect GITHUB ANALYZE owner/repo 42 . --publish  # post it as a PR comment
ai-architect GITHUB VALIDATE-LOCAL . main              # your uncommitted/branch changes vs main
```

## Browse someone else's OKF bundle

`OKF-VIEW` reads any OKF v0.2 bundle, for example the samples in Google's
[open-knowledge-format](https://github.com/GoogleCloudPlatform/open-knowledge-format) repository:

```bash
git clone --depth 1 https://github.com/GoogleCloudPlatform/open-knowledge-format
ai-architect OKF-VIEW open-knowledge-format/bundles/acme_retail
ai-architect OKF-VIEW open-knowledge-format/bundles/acme_retail gross-margin-period
```

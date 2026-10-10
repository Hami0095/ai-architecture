# Tutorial: Getting Started

From installation to your first verified finding in about ten minutes.

## Step 1: Install and unlock

```bash
git clone https://github.com/Hami0095/ai-architecture.git
cd ai-architecture
pip install -e .
ai-architect --version
```

Set your license token (see [License](../cli/configuration.md#license)), or
for local experiments:

```bash
export ARCHAI_DEV_MODE=1          # PowerShell: $env:ARCHAI_DEV_MODE=1
```

## Step 2: Run the default check

```bash
ai-architect CHECK-STANDARDS path/to/your/repo
```

With no configuration, ArchAI runs one default rule: no import cycles. The
report starts by saying so. **Look for:** section 2 ("What was found") and,
for each finding, the `file:line` evidence in section 3.

## Step 3: Write your first rule

Create `archai_standards.yaml` in the repository you are checking:

```yaml
version: 1
exclude: ["tests/*"]
layers:
  domain: ["myapp.domain"]
  infrastructure: ["myapp.db"]
rules:
  - id: domain-is-pure
    kind: layer_boundary
    layer: domain
    forbidden_layers: [infrastructure]
  - id: no-cycles
    kind: circular_dependency
```

Replace `myapp.domain` and `myapp.db` with real module names. Run the check again:

```bash
ai-architect CHECK-STANDARDS path/to/your/repo
```

If a rule's patterns match nothing, it reports `INSUFFICIENT_GRAPH_EVIDENCE`
instead of `PASS`; fix the pattern and rerun. All rule kinds are in
[Standards & Rules](../cli/check-standards.md).

## Step 4: Explore the results

```bash
ai-architect CHECK-STANDARDS path/to/your/repo --okf-out ../bundle --preview
ai-architect OKF-VIEW ../bundle findings
ai-architect OKF-VIEW ../bundle <finding-id>
```

**Look for:** the status of each finding (`VIOLATION`, `RISK`,
`NO-EVIDENCE`) and its evidence lines. A `PASS` covers only the rule's
declared scope.

## Next steps

- [Recipes](../cli/examples.md): CI gating, sharing bundles, reproducible runs.
- [CLI Command Reference](../cli/commands.md): every command, including the
  LLM-assisted `AUDIT`, `IMPACT`, `G-REASON` and `EXPLAIN`.

# archai_standards.yaml reference

Generated from `ai_architect/agents/tools.py` (`RULE_REFERENCE`), the same data the
`plumb_rule_reference` MCP tool returns.

File: archai_standards.yaml in the repository root (or pass config_path).

## Top-level keys

- `version`: 1 (optional)
- `source_roots`: import roots, e.g. ['src']; a src/ folder without __init__.py is detected automatically
- `exclude`: repo-relative path globs (fnmatch; * crosses /), e.g. ['tests/*', 'migrations/*']
- `defaults`: auto (default: add ArchAI default rules only when no rules are configured) | true | false
- `layers`: map of layer name -> module patterns
- `rules`: list of rules (below)

## Module patterns

A plain dotted name (myapp.domain) matches that module and everything beneath it; patterns with * ? [ use fnmatch on the full dotted module name; '*' matches every module.

## Every rule

- `id`: required; letters, digits, . _ -
- `kind`: required
- `description`: optional
- `rationale`: optional

## Rule kinds

### `forbidden_dependency`

- `from`: required patterns
- `to`: required patterns

```yaml
- id: api-not-db
  kind: forbidden_dependency
  from: [myapp.api]
  to: [myapp.db]
```

### `layer_boundary`

- `layer`: required, declared under layers
- `forbidden_layers | allowed_layers`: exactly one of the two

```yaml
- id: domain-is-pure
  kind: layer_boundary
  layer: domain
  forbidden_layers: [infrastructure]
```

### `circular_dependency`

- `scope`: patterns, default ['*']

```yaml
- id: no-cycles
  kind: circular_dependency
  scope: [myapp]
```

### `coupling_threshold`

- `max`: required non-negative integer
- `metric`: fan_out (default) | fan_in
- `scope`: patterns, default ['*']

```yaml
- id: bounded-fan-out
  kind: coupling_threshold
  metric: fan_out
  max: 12
```

### `required_tests`

- `scope`: required patterns
- `test_paths`: required templates using {leaf} {module} {module_path} {parent_path}
- `include_packages`: bool, default false

```yaml
- id: services-have-tests
  kind: required_tests
  scope: [myapp.services]
  test_paths: ['tests/test_{leaf}.py']
```

## Finding statuses

- **VERIFIED_VIOLATION**: The rule is broken and every supporting fact is cited from source.
- **POTENTIAL_RISK**: Facts match the rule's pattern, but static analysis cannot settle whether it is a breach.
- **INSUFFICIENT_GRAPH_EVIDENCE**: Part of the scope could not be checked; silence there is not compliance.
- **PASS**: Rule outcome only: nothing found within the declared scope.

# CLI Command Reference

ArchAI provide a powerful command-line interface to interact with its agents.

## `ai-architect impact`
**Agent: CIRAS**
Evaluates the impact of a change at the file or symbol level.

- `target`: File path or symbol name (e.g., `ai_architect.core_ai.auditor.ArchitecturalAuditor`).
- `--depth <int>`: (Default: 3) Maximum depth for call graph tracing.
- `--explain`: Include detailed rationale for the risk score.
- `--json`: Output result in machine-readable format.
- `--strict`: Fail with exit code 1 if risk is HIGH.
- `--verbose`: Show full signal data used for analysis.

## `ai-architect plan`
**Agent: WDP-TG**
Generates a prioritized work breakdown for a high-level goal.

- `goal`: A description of the feature or refactor (e.g., "Implement Redis caching").
- `--team-size <int>`: (Default: 3) Number of developers in the sprint.
- `--days <int>`: (Default: 10) Duration of the sprint.
- `--json`: Output hierarchical task list as JSON.
- `--strict`: Block plan if capacity is exceeded.
- `--verbose`: Show effort estimates and dependencies for every task.

## `ai-architect simulate-sprint`
**Agent: SRC-RS**
Simulates the execution of a sprint plan and predicts success.

- `goal`: The feature/goal to simulate.
- `--team-size <int>`: Number of developers.
- `--days <int>`: Sprint duration.
- `--strict`: Treat UNKNOWN CIRAS results as Critical Risk.
- `--verbose`: Show per-task completion probabilities and rationality.
- `--json`: Machine-readable simulation results.

## `ai-architect release-confidence`
**Agent: SRC-RS**
Identical to `simulate-sprint`, but optimized for evaluating a final release target.

## `ai-architect audit`
Orchestrates a full architectural discovery and gap analysis.

- `--explain`: Show architectural summary.
- `--verbose`: Show agent discovery logs.
- `--trace <ID>`: Show evidence for a specific ticket identified during the audit.

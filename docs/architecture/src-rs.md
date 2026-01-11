# SRC-RS: Sprint & Release Confidence Engine

SRC-RS is the simulation layer of ArchAI. It predicts the *outcome* of a sprint before the team begins working.

## Simulation Pipeline

### Step 1: Probability Aggregation
For every task in a WDP-TG plan, a completion probability is calculated:
$P(task) = f(Effort, Risk, Dependencies, Experience)$
- High `risk_level` lowers probability.
- Unresolved `dependencies` halt progress in the simulation until the parent task is "completed."

### Step 2: Cumulative Simulation
The engine sequentially "runs" the sprint:
- It respects team size and daily capacity.
- It calculates an **Epic Forecast** based on the success rates of its child tasks.
- It identifies **Bottlenecks** (tasks that block significant downstream work).

### Step 3: Confidence Score
The final `confidence_score` (0-1) represents the mathematical probability that the entire release goals will be met.

## Rationale & Recommendations
Every SRC-RS report includes **Actionable Safety Recommendations** linked to codebase evidence.
- *Example*: "Task T001 has 40% probability due to missing tests in Module X. Add tests before sprint start."

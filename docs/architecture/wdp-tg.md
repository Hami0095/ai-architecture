# WDP-TG: Work Decomposition & Task Generation

WDP-TG acts as the Senior Engineering Planner. It takes a high-level goal and transforms it into a structured engineering plan.

## Task Decomposition Engine

### Hierarchical Breakdown
The engine decomposes work into three layers:
1. **Epics**: Large thematic containers for related work.
2. **Tasks (AuditTickets)**: Primary units of work that can be assigned and tracked.
3. **Subtasks**: Granular technical steps required for a single task.

### Risk-Aware Prioritization
Unlike traditional planners, WDP-TG is awareness of architectural risk from CIRAS. Its rules include:
- **Safety First**: Tasks affecting high-risk modules are sequenced at the start of the sprint.
- **Dependency Mapping**: Automatically detects cross-module dependencies to prevent context-switching.
- **Capacity Filtering**: Compares total estimated `effort_hours` against the `SprintPlanConfig`.

## Data Model: `WDPOutput`
Integrates directly with project management tools like Jira or ClickUp via the JSON schema.

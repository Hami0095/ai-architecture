# CIRAS: Change Impact & Risk Assessment

CIRAS is the safety-first agent of ArchAI. It evaluates code changes using deterministic evidence before any code is actually modified.

## How it Works

### 1. Deterministic Call Graph Tracing
CIRAS uses the `GraphEngine` to build a real-time map of the codebase. When a `target` is provided, it:
- Locates the symbol in the AST.
- Traces all callers (backward impact) up to the specified `--depth`.
- Identifies "blast radius" components that might be affected by side effects.

### 2. Signal Aggregation
The risk score is calculated by combining three primary signal types:

| Signal Type | Examples | Source |
| :--- | :--- | :--- |
| **Structural** | Fan-in/out, Dependency Depth, Complexity | AST Parsing |
| **Historical** | Commit count (Churn), Bug history | Git Analysis |
| **Quality** | Test coverage gaps, Documentation status | Static Analysis |

### 3. Trust Ethics
CIRAS adheres to a strict "Refusal Protocol":
- **UNKNOWN Status**: If the call graph is incomplete, it refuses to classify risk as LOW.
- **Dynamic Dispatch**: Lower confidence is assigned to modules using heavy reflection or dynamic dispatch.
- **Insufficient Data**: Flags cases where Git history is too shallow for reliable prediction.

## Data Model: `ImpactAssessment`
The output includes a numerical `risk_score` (0-100) and a `confidence_score` (0-1).

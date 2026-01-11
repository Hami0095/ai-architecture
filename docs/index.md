# ArchAI: The Autonomous Architectural Guardian

ArchAI is a comprehensive suite of AI-driven agents designed to bridge the gap between architectural insight and engineering action. It replaces manual risk assessment and gut-instinct planning with deterministic, evidence-backed decision making.

## Core Mission
To empower engineering teams to build, refactor, and release software with 100% confidence by providing auditable insights and actionable plans derived directly from the codebase.

## The ArchAI Trifecta

### 🛡️ CIRAS (Change Impact & Risk Assessment)
**"Is it safe to change?"**
Identifies high-risk modules, traces call graph impact, and evaluates historical instability (churn) to predict the safety of a proposed change.

### 📋 WDP-TG (Work Decomposition & Prioritized Task Generation)
**"What exactly should we do?"**
Decomposes high-level goals into hierarchical Epics, Tasks, and Subtasks. It automatically maps dependencies and sequences work to mitigate architectural risk first.

### 🎯 SRC-RS (Sprint & Release Confidence Engine)
**"Will we succeed?"**
Simulates sprint execution using probabilistic modeling. It highlights bottlenecks, predicts task completion likelihood, and provides an overall confidence score for your release.

### 🔗 GitHub Integration
**"Workflow-Native Intelligence"**
ArchAI connects directly to your GitHub repositories, providing automated PR risk assessments and posting actionable advice directly into your code review process.

### 📅 PM Tool Integration
**"Actionable Roadmaps"**
Automatically push decomposed tasks and epics to Jira and Trello. ArchAI ensures that every ticket is risk-aware and fully traceable to the codebase.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- Git
- Local LLM (Ollama) or API access (OpenAI/etc.)

### Installation
```bash
pip install ai-architect
```

### First Command
Run a quick risk assessment on a core module:
```bash
ai-architect impact GraphEngine --explain
```

## Documentation Structure
- [CLI Reference](cli/commands.md): Full command-line guide.
- [API Reference](api/endpoints.md): Integration guide for CI/CD and internal tools.
- [Architecture Deep Dive](architecture/ciras.md): How the agents work under the hood.
- [Tutorials](tutorials/getting_started.md): Step-by-step guides for common workflows.
- [Proper Flow](tutorials/proper_flow.md): The analysis-to-action pipeline.

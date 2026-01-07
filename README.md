# AI Architect 🏗️

**Autonomous Iterative AI Improvement System & Architectural Auditor**

AI Architect is an autonomous system that iteratively improves AI task performance (starting with Python unit test generation) and provides deep architectural auditing of project structures.

[GitHub Repository](https://github.com/Hami0095/ai-architecture.git)

## Key Features
- **Core AI**: Generates comprehensive `pytest` unit tests for Python functions.
- **Autonomous Feedback Loop**: Iteratively improves code based on coverage and pass/fail metrics.
- **Architectural Auditor**: Scans project directories to identify flaws in structure, logic, and DB schema.
- **XAI Integration**: Provides explainable AI justifications for every improvement strategy and decision.
- **Ollama Manager**: Automatically handles LLM detection and model pulling (`gemma3:1b` by default).

## Installation

Install directly from the source:
```bash
git clone https://github.com/Hami0095/ai-architecture.git
cd ai-architecture
pip install .
```

## Quick Start (CLI)

Once installed, you can launch the interactive wizard from anywhere:

```bash
ai-architect
```

### Usage Modes
1. **Interactive Mode**: Run `ai-architect` and follow the on-screen prompts.
2. **Library Mode**: Import components like `ArchitecturalAuditor` into your own scripts.

## Prerequisites
- **Python**: 3.10+
- **Ollama**: [Installed and running](https://ollama.com/) (`ollama serve`).

## License
MIT


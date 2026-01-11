# ArchAI: Autonomous Architect 

**SaaS-Ready AI Agent Orchestration for Codebase Mapping & Sprint Planning**

ArchAI is a professional-grade architectural auditing system that transforms raw codebases into actionable, high-fidelity development roadmaps. Using a chained workflow of seven specialized AI agents, it provides deep structural insight and prioritized task management.

[GitHub Repository](https://github.com/Hami0095/ai-architecture.git)

---

## The 6-Agent Orchestration Pipeline


ArchAI operates on a rigorous, sequential chain of seven specialized intelligence agents:


1. **Discovery Agent**: Maps project structure and detects tech-stack metadata (Languages, Frameworks, Architecture Patterns).
2. **Context Builder**: Analyzes discovery data to build a dependency graph and identify critical execution paths.
3. **Gap Analyzer**: Compares the current codebase against your "Target State" goals to identify technical debt and missing features.
4. **Ticket Generator**: Converts gaps into detailed, machine-parsable development tickets with severity and effort estimations.
5. **Sprint Planner**: Uses a balanced scheduling algorithm to build a prioritized 5-day sprint plan.
6. **Auditor & Verifier**: Performs a final risk assessment, ensuring task feasibility and merging quality notes into the roadmap.


---

## Usage (Professional CLI)

ArchAI supports both a guided interactive wizard and a headless CLI for CI/CD integration.

### Orchestrated Audit Command
Run a full 7-agent audit on any project:
```bash
ai-architect audit /path/to/project --context "Modernizing legacy API" --goal "Production-ready REST API"
```

> **⚠️ Path Navigation Note:**
> Users on **macOS/Ubuntu** should provide full absolute paths starting with `/Users/<username>/` (macOS) or `/home/<username>/` (Linux) to ensure the Path Navigator agent correctly resolves the target directory.

### Options & Observability
- `--verbose`: Show real-time agent execution logs and latency metrics.
- `--diagnostics`: Run a filesystem scan only (no AI) to verify path readability.
- `--model`: Specify your preferred Ollama model (Default: `qwen3-coder:480b-cloud`).

### Iterative Test Loop
Improve test coverage autonomously:
```bash
ai-architect test
```

---


## Premium Features
- **Cross-Platform Stability**: Native support for Windows, Mac, and Ubuntu/Linux.

- **Machine-Parsable Output**: Produces a `sprint-plan.json` ready for consumption by Web UIs or external APIs.
- **Explainable AI (XAI)**: Context-aware reasoning for every architectural decision.
- **Self-Monitoring**: The orchestrator tracks agent performance and latency for stability analysis.

---

## Installation

```bash
git clone https://github.com/Hami0095/ai-architecture.git
cd ai-architecture
pip install -e .
```

## Prerequisites
- **Python**: 3.10+
- **Ollama**: [Installed and running](https://ollama.com/) (`ollama serve`).

## License
ArchAI is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. This license ensures that improvements to the core orchestration engine are shared back with the community, protecting the project's commercial viability while supporting open innovation.

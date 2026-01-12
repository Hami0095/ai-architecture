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

## 🛰️ ArchAI Orientation

Welcome to the bridge of your software project. ArchAI is a deterministic architectural intelligence system designed to help you navigate complex codebases with safety and precision.

### 1. The Command Dictionary

| Command | Summary | How to Use It |
| :--- | :--- | :--- |
| **AUDIT** | The "Satellite Scan". Scans the entire project to find every risk and build a full sprint plan. | Run it once at the start of a week to see your project's health. |
| **PLAN** | The "Blueprint Maker". Takes a single goal and breaks it down into small, safe tasks. | Use it when you have a new feature request. Give it the path and your goal in quotes. |
| **IMPACT** | The "Safety Check". Calculates if changing a specific file or class will break something else. | Use it before touching "scary" code. Just give it the class name like `BillingEngine`. |
| **SIMULATE** | The "Time Traveler". Predicts the future to see if your team will actually finish the work on time. | Run it after a PLAN to check if your deadline is realistic before you start. |
| **TRACE** | The "Evidence Finder". Shows exactly why the AI made a certain decision or created a task. | If you don't trust a ticket, TRACE its ID to see the file and line numbers the AI found. |
| **CONFIG** | The "Dashboard". Shows who you are and which external tools (GitHub/Jira) are connected. | Check this when you first start to make sure your tokens are set correctly. |

### 2. The Golden Workflow (Order of Operations)

To get the most out of ArchAI, follow this "Detective to Architect" sequence:

1.  **AUDIT**: Use this first to understand the current "mess" or status of the project.
2.  **PLAN**: Once you know the project, tell ArchAI your goal. It will give you tickets.
3.  **IMPACT**: For each ticket, run an impact check on the specific files mentioned.
4.  **SIMULATE**: Before starting the sprint, check the confidence score to see if it's safe to proceed.
5.  **TRACE**: If any task looks weird, trace it to see the evidence.

### 3. Explaining to a "Newbie" (Junior Dev)

> "Think of ArchAI as a **Static Analysis tool with a brain**. While a normal linter tells you about a missing semicolon, ArchAI tells you about a missing **future**. It looks at the calls and imports in your code to build a 'Dependency Graph'. Then, it uses an LLM to look at that graph and say: 'Hey, if you change this, you'll break the payment system' or 'This goal will take your team 3 weeks, not 1'."

### 4. Explaining to a Kid (The Lego City)

> "Imagine you have a **giant Lego City** that's so big you can't see the whole thing at once. ArchAI is like a **Magic Map** and a **Robot Helper**. **AUDIT** is like flying a drone over the city to find where the blocks are loose. **PLAN** is when you say 'I want to build a space station!', and the Robot tells you exactly which bricks you need. **IMPACT** is like checking if pulling out one brick will make the whole building fall down!"

---

## Usage (Professional CLI)

ArchAI features a **Persistent Interactive Console** for session-based reasoning, as well as one-shot commands for CI/CD integration.

### Interactive Mode
Launch the persistent console for iterative planning:
```bash
ai-architect
```
*Note: Type `PHIR-MILTY-HAIN` to exit the session.*

### One-Shot Audit Command
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

## 🔗 Workflow Automation & GitHub Integration
ArchAI is designed to live where your code lives. It provides native integration for GitHub projects:

- **Automated PR Analysis**: Runs CIRAS and WDP-TG on every Pull Request to evaluate architectural impact before merging.
- **GitHub-Native Reporting**: Posts risk assessments and task breakdowns directly as PR comments.
- **Workflow Simulation**: Predicts release confidence for proposed changes based on team capacity and codebase health.

### GitHub CLI Commands:
```bash
# Analyze a PR and post feedback
ai-architect github analyze-pr owner/repo 123 --comment
```

- **Project Management Integration**: Automatically push generated engineering tasks to Jira or Trello boards, preserving hierarchical relationships and risk metadata.

### PM CLI Commands:
```bash
# Push a generated plan to Jira
ai-architect pm push "Modernize API" --tool jira --project "PROJ-KEY"
```

## 🏗️ Master Planner Dashboard
ArchAI features a futuristic, interactive dashboard that visualizes your codebase as a living architectural project:

- **Structural Integrity Lab**: Real-time risk assessment and module stability tracking.
- **Blueprint Decomposer**: Visualizes engineering goals as construction phases and task beams.
- **Load & Stress Simulator**: Predictive models for sprint success and release confidence.
- **Dynamic Alert Towers**: Actionable notifications via Slack, Email, and the web UI.


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

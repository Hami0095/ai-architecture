# AI Architect 🏗️

**Autonomous Iterative AI Development & Architectural Auditing System**

AI Architect is a professional-grade tool designed to automate the software development lifecycle. It combines an **Autonomous Improvement Loop** for code generation with **ArchAI**, a multi-stage architectural auditor that transforms raw codebases into actionable development roadmaps.

[GitHub Repository](https://github.com/Hami0095/ai-architecture.git)

---

## 🚀 ArchAI: The Roadmap Assistant

ArchAI is the flagship feature of AI Architect. It scans your codebase and uses a sophisticated 4-stage pipeline to help you reach your production goals.

### 1. Discovery 🔍
Automatically maps your project structure, detecting:
- **Languages & Frameworks**: Python, JavaScript, React, Django, etc.
- **Architecture Patterns**: Monolithic, Microservices, Layered, and more.
- **Module Summaries**: AI-generated descriptions of every core component.

### 2. Gap Analysis 📋
Compares your current "Alpha" or "Prototype" code against your "Perfect State" goal. It identifies missing features, integration risks, and architectural technical debt.

### 3. Ticket Generation 🎫
Converts identified gaps into **high-fidelity development tickets**. Each ticket includes:
- **Priority & Severity**: Standardized Critical-to-Low ratings.
- **Effort Estimations**: Realistic hour-based estimates.
- **Suggested Fixes**: Step-by-step implementation instructions.

### 4. Sprint Planning 📅
Uses a greedy scheduling algorithm to build a **5-day prioritized sprint plan**, ensuring high-impact tasks are addressed first while staying within realistic daily developer capacity.

---

## 🛠️ Usage (Professional CLI)

AI Architect now supports both a guided interactive wizard and a full headless CLI for integration into CI/CD pipelines.

### Professional Audit Command
Run a full architectural audit without interactive prompts:
```bash
ai-architect audit /path/to/project --context "Biological pathway mapping" --status "Alpha" --goal "Production"
```

### Iterative Test Loop
Launch the autonomous loop to improve test coverage iteratively:
```bash
ai-architect test --model qwen3-coder:480b-cloud
```

### Interactive Wizard
Simply run the base command to access the selection menu:
```bash
ai-architect
```

---

## 💎 Key Features
- **Explainable AI (XAI)**: Every roadmap decision and code improvement comes with a reasoning report explaining the "Why".
- **Local First & Private**: Runs entirely on your machine using Ollama. No code ever leaves your infrastructure.
- **High-Performance Models**: Optimized for `qwen3-coder:480b-cloud` for superior architectural reasoning.

## 📦 Installation

```bash
git clone https://github.com/Hami0095/ai-architecture.git
cd ai-architecture
pip install -e .
```

## 📋 Prerequisites
- **Python**: 3.10+
- **Ollama**: [Installed and running](https://ollama.com/) (`ollama serve`).

## 📄 License
MIT

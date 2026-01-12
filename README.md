# ArchAI: The Autonomous Architectural Judge

**Professional-Grade Architectural Intelligence & Deterministic Sprint Planning**

ArchAI is a strictly deterministic architectural adjudication system. It constructs, reasons over, and explains software systems using **verifiable graph evidence** rather than probabilistic intuition. It is designed to navigate complex codebases with the precision of a senior staff engineer, ensuring that every architectural decision is backed by a "Receipt Chain."

---

## Core Philosophy: "Receipts or Silence"
ArchAI operates under a mandatory trust-preserving protocol:
- **Graph-First Reasoning**: Every software system is a typed, multi-layer graph. Reasoning always follows graph construction.
- **The Evidence Ladder**: Explanations progress through four tiers of rigor (Direct citations → Structural proximity → Inherited risk → Absence-as-Signal).
- **Deterministic Adjudication**: If the graph cannot prove a claim, ArchAI remains silent. It prefers `INSUFFICIENT_GRAPH_EVIDENCE` over speculation.

---

## Installation (For Testers & Developers)

To ensure a complete and stable installation, follow these steps exactly:

### 1. Prerequisites
- **Python**: 3.10 or higher.
- **Ollama**: [Installed and running](https://ollama.com/) (`ollama serve`).

### 2. Setup
```bash
# Clone the repository
git clone https://github.com/Hami0095/ai-architecture.git
cd ai-architecture

# (Optional but Recommended) Create a Virtual Environment
python -m venv venv
source venv/bin/activate  # Mac/Linux
.\venv\Scripts\activate   # Windows

# Install the package in editable mode
# This now correctly installs ALL dependencies listed in requirements.txt
pip install -e .
```

---

## Command Center: The Professional Toolkit

ArchAI features an interactive **Command-Center Console** as well as one-shot CLI commands.

### Launch the Interactive Console
```bash
ai-architect
```
*Note: Type `PHIR-MILTY-HAIN` to exit safely.*

---

### 🧩 The Thinkers (Strategic & Architectural Reasoning)
Use these commands to build your mental model and generate deterministic blueprints.

#### **AUDIT** — *The Site Survey*
*   `AUDIT .` : Full structural scan of the current directory.
*   `AUDIT /path/to/project --goal "Modernize DB Layer"` : Target the audit toward a specific outcome.
*   `AUDIT . --verbose` : Show real-time agent latency and reasoning logs.
*   `AUDIT . --diagnostics` : Non-destructive scan to verify filesystem readability.
*   `GITHUB AUDIT owner/repo` : Sandbox audit a remote repository via automated cloning.

#### **PLAN** — *The Blueprint Maker*
*   `PLAN . "Complete Auth System"` : Decompose a high-level goal into prioritized tasks.
*   `PLAN /path/to/project "Refactor API" --days 10 --team-size 5` : Configure capacity for a custom sprint duration and team size.

#### **EXPLAIN & G-REASON** — *The Architectural Defense*
*   `EXPLAIN RISK "module/file.py"` : Generate a "Reasoning Receipt" for a specific risk finding.
*   `EXPLAIN EFFORT "T001"` : Justify the min-max effort range for a generated task.
*   `EXPLAIN PRIORITY "T005" --json` : Export machine-readable justification for task ordering.
*   `G-REASON . "Analyze coupling between X and Y"` : Direct graph-core reasoning for structural questions.

---

### 🔍 The Doubters (Tactical & Defensive Verification)
Use these commands to verify AI claims and bulletproof your releases.

#### **IMPACT** — *The Safety Scan*
*   `IMPACT . "PaymentService"` : Map dependency fan-out before modifying core logic.
*   `IMPACT . "utils.py" --verbose` : Full traversal trace of every inherited risk path.
*   `GITHUB VALIDATE-LOCAL . main` : Audit local changes against a base branch before pushing.

#### **TRACE** — *The Receipt Finder*
*   `TRACE T001` : Show the exact agent, file, and line numbers that generated this task.
*   `TRACE 240112153022` : Recover evidence from historical tasks using timestamp IDs.

#### **SIMULATE** — *The Time Pilot*
*   `SIMULATE "Implement JWT"` : Predict success probability based on current team velocity.
*   `SIMULATE T001 --team-size 2` : Check if a single task is feasible with a smaller team.
*   `RELEASE-CONFIDENCE . "v2.0" --velocity 0.6` : Evaluate release stability assuming lower team productivity.

---

## ArchAI Orientation

### For the Newbies
> "Think of ArchAI as a **Static Analysis tool with a brain**. While a normal linter tells you about a missing semicolon, ArchAI tells you about a missing **future**. It looks at the calls and imports in your code to build a 'Dependency Graph'. Then, it uses a deterministic graph engine to look at that graph and say: 'Hey, if you change this, you'll break the payment system' or 'This goal will take your team 3 weeks, not 1'."

### For the non-technical Project Manager (The Lego City)
> "Imagine you have a **giant Lego City** that's so big you can't see the whole thing at once. ArchAI is like a **Magic Map** and a **Robot Helper**. **AUDIT** is like flying a drone over the city to find where the blocks are loose. **PLAN** is when you say 'I want to build a space station!', and the Robot tells you exactly which bricks you need. **IMPACT** is like checking if pulling out one brick will make the whole building fall down!"

## Configuration & Integrations

ArchAI is designed to live where your work happens.

### Connecting External Tools
```bash
# Register your tokens securely in the session
SET-GITHUB-TOKEN <your_token>
SET-PM-TOKEN JIRA <your_token> <email>
SET-PM-TOKEN TRELLO <your_token> <api_key>
```

### The GitHub Agent
ArchAI can adjudicate Pull Requests automatically:
- **PR Analysis**: `GITHUB ANALYZE owner/repo 123 . --publish`
- **Impact Assessment**: It posts risk scores and rationales directly to PR comments.

---

## Testing ArchAI
We include a suite of **Adversarial Project Mimics** to stress-test the engine's deterministic reasoning:
- **Circular Trap**: Tests topological cycle detection.
- **Hidden Risk**: Tests risk inheritance through leaky abstractions.
- **Responsibility Drift**: Tests module encapsulation and drift detection.

Run these tests via:
```bash
python -m pytest tests/
```

---

## License
ArchAI is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. 

---

**ArchAI: Receipts or Silence.**
**PHIR-MILTY-HAIN**

# Autonomous Iterative AI Improvement System

This project implements an autonomous loop used to improve AI task performance (specifically Python unit test generation) using Ollama LLMs.

## Architecture
- **Core AI**: Generates unit tests.
- **Evaluator**: Runs tests using `pytest` and calculates coverage.
- **Improvement Eng ine**: Analyzes failures and proposes strategies (with XAI).
- **Reconciler**: Selects the best strategy based on risk/impact.
- **XAI Layer**: Provides explanations for decisions.

## Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com/) installed and running (`ollama serve`).
- `gemma3:1b` model pulled (`ollama pull gemma3:1b`).

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the system:
   ```bash
   python main.py
   ```

## Configuration
- Modify `main.py` to change the `target_score` or `max_iterations`.
- Models are defined in the class `__init__` methods (default: `gemma3:1b`).

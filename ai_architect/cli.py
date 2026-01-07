import asyncio
import os
import uuid
import sys
import json
from .core_ai.generator import CoreAI
from .core_ai.auditor import ArchitecturalAuditor
from .evaluations.runner import TestRunner
from .improvement_engine.analyzer import ImprovementEngine
from .reconciler.logic import Reconciler
from .data.db_client import DBClient
from .utils.ollama_manager import initialize_ollama

# Test Target (Example)
TARGET_CODE = """
def calculate_tax(income: float, status: str) -> float:
    if income < 0:
        raise ValueError("Income cannot be negative")
        
    if status not in ["single", "married"]:
        raise ValueError("Invalid status")
        
    tax_rate = 0.2 if status == "single" else 0.15
    return income * tax_rate
"""

TARGET_FILE_PATH = os.path.abspath("target_calc.py")

async def run_test_generation_loop(model_name):
    # Setup
    print("Initializing Test Generation System...")
    
    # Write target file for coverage
    with open(TARGET_FILE_PATH, "w") as f:
        f.write(TARGET_CODE)

    db = DBClient()
    core = CoreAI(model=model_name)
    runner = TestRunner()
    # Note: Evaluator doesn't use LLM, but others do
    improver = ImprovementEngine(model=model_name)
    reconciler = Reconciler(model=model_name)

    max_iterations = 5
    target_score = 0.9

    for i in range(max_iterations):
        run_id = str(uuid.uuid4())[:8]
        print(f"\n--- Iteration {i+1} (RunID: {run_id}) ---")

        # 1. Generate
        print("CoreAI: Generating tests...")
        tests = core.generate_tests(TARGET_CODE)
        
        # 2. Evaluate
        print("Evaluator: Running pytest...")
        metrics = runner.run_evaluation(run_id, tests, TARGET_FILE_PATH)
        print(f"Metrics: Valid={metrics.valid_syntax}, Passed={metrics.tests_passed}, Cov={metrics.coverage_percent*100}%, Score={metrics.total_score:.2f}")
        
        db.log_metrics(metrics)

        if metrics.total_score >= target_score:
            print("SUCCESS: Target score reached!")
            break

        # 3. Analyze & Suggest
        print("ImprovementEngine: Analyzing failure...")
        fail_details = {
            "valid": metrics.valid_syntax,
            "passed": metrics.tests_passed,
            "coverage": metrics.coverage_percent,
            "error_log": metrics.details.get("error", "")[:500]
        }
        suggestions = improver.generate_suggestions(TARGET_CODE, str(fail_details))
        print(f"Generated {len(suggestions)} suggestions.")

        if not suggestions:
            print("No suggestions generated. Stopping.")
            break

        # 4. Reconcile
        print("Reconciler: Selecting best strategy...")
        result = reconciler.reconcile(suggestions)
        print(f"Selected: {result.selected_strategy}")
        print(f"Rationale: {result.rationale}")
        
        db.log_decision(result)

        # 5. Implementation
        new_instruction = f"\nIMPORTANT IMPROVEMENT: {result.selected_strategy} - {result.rationale}"
        core.update_prompt(core.system_prompt + new_instruction)

async def run_audit(model_name):
    path = input("Enter project path to audit (default: .): ") or "."
    path = os.path.abspath(path)
    
    # New Context Inputs
    print("\n--- Additional Context (Optional) ---")
    user_context = input("Enter Project Context (What is this app?): ")
    project_status = input("Enter Project Status (e.g., Prototype, Production, MVP): ")
    expected_output = input("Enter Expected Plan/Output (What do you want to achieve?): ")
    
    auditor = ArchitecturalAuditor(model=model_name)
    print(f"\nStarting audit for: {path}")
    
    report = auditor.audit_project(path, user_context, project_status, expected_output)
    
    tickets = report.get('tickets', [])
    print(f"\nFound {len(tickets)} issues.")
    
    output_file = "audit_tickets.json"
    with open(output_file, "w") as f:
        json.dump(report, f, indent=2)
        
    print(f"Tickets saved to {output_file}")
    print("\n--- Summary ---")
    for t in tickets:
        print(f"[{t.get('type', 'General').upper()}] {t.get('title')} ({t.get('severity')})")

async def main():
    # 1. Initialize Ollama First
    model_name = initialize_ollama(preferred_model="gemma3:1b")
    
    print("\nSelect Mode:")
    print("1. Test Generation Loop (Core Task)")
    print("2. Architectural Audit (Scan Project)")
    
    choice = input("Enter 1 or 2: ")
    
    if choice == "2":
        await run_audit(model_name)
    else:
        await run_test_generation_loop(model_name)

def run_cli():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    run_cli()

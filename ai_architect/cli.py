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

import argparse

async def run_audit(model_name, path=None, context=None, status=None, goal=None):
    if not path:
        path = input("Enter project path to audit (default: .): ") or "."
    path = os.path.abspath(path)
    
    if not context:
        print("\n--- Project Context (ArchAI) ---")
        context = input("Enter Goal/Purpose of the app: ")
    if not status:
        status = input("Current Status (e.g. Planning, Alpha, MVP, Prod): ")
    if not goal:
        goal = input("Perfect State (What are you trying to build?): ")
    
    auditor = ArchitecturalAuditor(model=model_name)
    print(f"\nStarting ArchAI Analysis for: {path}")
    
    report = auditor.audit_project(path, context, status, goal)
    
    # Save Report
    output_file = "archai_report.json"
    with open(output_file, "w") as f:
        json.dump(report, f, indent=2)
    
    # Display Results
    print(f"\n{'='*60}")
    print(f" ARCHAI ANALYSIS REPORT: {os.path.basename(path)} ")
    print(f"{'='*60}")
    
    discovery = report.get('discovery', {})
    print(f"\n[DISCOVERY]")
    print(f" - Languages: {', '.join(discovery.get('languages', []))}")
    print(f" - Frameworks: {', '.join(discovery.get('frameworks', []))}")
    print(f" - Arch Type: {discovery.get('architecture_type', 'Unknown')}")
    
    print(f"\n[GAP ANALYSIS]")
    print(report.get('gap_analysis', 'No gap analysis available.'))
    
    print(f"\n[TICKETS FOUND: {len(report.get('tickets', []))}]")
    for t in report.get('tickets', []):
        print(f" - [{t.get('priority', 'Medium')}] {t.get('title')} ({t.get('effort_hours')}h)")

    print(f"\n[5-DAY SPRINT PLAN]")
    for day in report.get('sprint_plan', []):
        if day.get('tickets'):
            print(f" {day.get('day')} ({day.get('total_hours')}h):")
            for t in day.get('tickets'):
                print(f"   * {t.get('title')} [{t.get('module') or 'General'}]")
        else:
            print(f" {day.get('day')}: No tasks assigned.")

    print(f"\n{'='*60}")
    print(f"Full report saved to {output_file}")
    print(f"{'='*60}")

async def main():
    parser = argparse.ArgumentParser(description="AI Architect: Autonomous Improvement & Audit System")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Audit command
    audit_parser = subparsers.add_parser("audit", help="Run an architectural audit (ArchAI)")
    audit_parser.add_argument("path", nargs="?", default=None, help="Path to project root")
    audit_parser.add_argument("--context", help="Project goal/context")
    audit_parser.add_argument("--status", help="Current project status")
    audit_parser.add_argument("--goal", help="Target 'perfect' state")

    # Test command
    test_parser = subparsers.add_parser("test", help="Run iterative test generation loop")
    test_parser.add_argument("--model", default="qwen3-coder:480b-cloud", help="Model to use")

    args = parser.parse_args()

    # 1. Initialize Ollama
    model_name = initialize_ollama(preferred_model=getattr(args, 'model', "qwen3-coder:480b-cloud"))
    
    if args.command == "audit":
        await run_audit(model_name, args.path, args.context, args.status, args.goal)
    elif args.command == "test":
        await run_test_generation_loop(model_name)
    else:
        # Interactive mode fallback
        print("\nWelcome to AI Architect!")
        print("1. Architectural Audit (ArchAI)")
        print("2. Test Generation Loop")
        choice = input("Select (1/2): ")
        if choice == "1":
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

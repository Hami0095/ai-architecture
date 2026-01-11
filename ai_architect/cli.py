import asyncio
import sys
import os
import json
import argparse
import logging
from typing import Optional
from .core_ai.generator import CoreAI
from .evaluations.runner import EvaluationRunner
from .improvement_engine.analyzer import ImprovementEngine
from .reconciler.logic import Reconciler
from .core_ai.auditor import ArchitecturalAuditor
from .utils.ollama_manager import initialize_ollama

# Global logging config
logging.basicConfig(level=logging.WARNING, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("ArchAI.CLI")

async def run_archai_flow(path: str, context: Optional[str] = None, status: Optional[str] = None, goal: Optional[str] = None, verbose: bool = False, diagnostics: bool = False):
    """
    Orchestrates the ArchAI audit flow via CLI.
    """
    if verbose:
        logging.getLogger("ArchAI").setLevel(logging.INFO)
    
    auditor = ArchitecturalAuditor()
    
    if diagnostics:
        print(f"\n[DIAGNOSTIC MODE] Scanning: {path}")
        structure = auditor.scan_directory(path)
        print(structure)
        print("\n[DIAGNOSTIC MODE] Scan Complete. No LLM calls made.")
        return

    print(f"\nStarting ArchAI Analysis for: {path}")
    
    # Run the audit
    report = auditor.audit_project(
        root_path=path,
        user_context=context or "General software project",
        project_status=status or "Early Prototype",
        expected_output=goal or "Production-ready system"
    )
    
    # Save Report
    with open("archai_report.json", "w") as f:
        json.dump(report, f, indent=4)
        
    # Display Results (Handle both old and new Orchestrated formats)
    print(f"\n{'='*60}")
    print(f" ARCHAI ANALYSIS REPORT: {os.path.basename(path)} ")
    print(f"{'='*60}")
    
    # The new orchestrator uses keys like 'tasks' and 'sprintPlan'
    tasks = report.get('tasks') or report.get('tickets', [])
    sprint_plan = report.get('sprintPlan') or report.get('sprint_plan', [])
    
    # Discovery may be nested in 'discovery' or summarized in 'notes'
    if 'discovery' in report:
        discovery = report['discovery']
        print(f"\n[DISCOVERY]")
        print(f" - Languages: {', '.join(discovery.get('languages', []))}")
        print(f" - Frameworks: {', '.join(discovery.get('frameworks', []))}")
        print(f" - Arch Type: {discovery.get('architecture_type', 'Unknown')}")
    
    print(f"\n[GAP ANALYSIS]")
    gap_data = report.get('gap_analysis') or report.get('goal', 'Gaps identified by Orchestrator.')
    print(gap_data)
    
    print(f"\n[TASKS FOUND: {len(tasks)}]")
    for t in tasks:
        # Resolve camelCase vs snake_case
        priority = t.get('priority', 'Medium')
        title = t.get('title', 'Unknown Task')
        effort = t.get('effortHours') or t.get('effort_hours', 2)
        print(f" - [{priority}] {title} ({effort}h)")

    print(f"\n[5-DAY SPRINT PLAN]")
    for day in sprint_plan:
        day_name = day.get('day')
        hours = day.get('totalHours') or day.get('total_hours', 0)
        day_tasks = day.get('taskIds') or day.get('tickets', [])
        
        if day_tasks:
            print(f" {day_name} ({hours}h):")
            for t in day_tasks:
                if isinstance(t, str): # taskId
                    print(f"   * {t}")
                else: # Ticket object
                    print(f"   * {t.get('title')} [{t.get('module') or 'General'}]")
        else:
            print(f" {day_name}: No tasks assigned.")

    print(f"\n{'='*60}")
    print(f"Full report saved to archai_report.json")
    print(f"Final Audit Notes: {report.get('notes', report.get('summary', 'Audit Complete'))}")
    print(f"{'='*60}")

async def run_improvement_loop():
    """
    Main interactive entry point for ArchAI (Original Test Loop).
    """
    print("Welcome to ArchAI: Autonomous Development System")
    
    target_code = input("\nEnter the code you want to test and improve (or path to file):\n")
    if os.path.exists(target_code):
        with open(target_code, "r") as f:
            target_code = f.read()

    # Initialize Components
    generator = CoreAI()
    runner = EvaluationRunner()
    analyzer = ImprovementEngine()
    reconciler = Reconciler()

    max_iterations = 3
    current_iteration = 0

    while current_iteration < max_iterations:
        current_iteration += 1
        print(f"\n--- Iteration {current_iteration} ---")

        # 1. Generate Tests
        print("Generating tests...")
        tests = generator.generate_tests(target_code)
        
        # 2. Run Tests & Evaluate
        print("Running tests...")
        metrics = runner.evaluate(target_code, tests)
        print(f"Metrics: {metrics.to_dict()}")

        if metrics.success_rate >= 1.0:
            print("\nSuccess! Tests passed 100%.")
            break

        # 3. Analyze Failures
        print("Analyzing failures and generating improvement strategies...")
        failure_details = metrics.error_logs if metrics.error_logs else "Low coverage or logical gaps."
        suggestions = analyzer.generate_suggestions(target_code, failure_details)

        if not suggestions:
            print("No improvements generated. Optimization stopped.")
            break

        # 4. Reconcile & Select Strategy
        print("Reconciling strategies...")
        decision = reconciler.reconcile(suggestions)
        print(f"Selected Strategy: {decision.selected_strategy}")
        print(f"Rationale: {decision.rationale}")

        # Find the selected suggestion
        selected_suggestion = next((s for s in suggestions if s.strategy_name == decision.selected_strategy), suggestions[0])

        # 5. Apply Improvement (Update generator prompt)
        generator.update_prompt(selected_suggestion.suggested_prompt_modification)

    print("\nFinalizing ArchAI Session.")

def run_cli():
    parser = argparse.ArgumentParser(description="ArchAI: Autonomous Improvement & Audit System")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Audit command
    audit_parser = subparsers.add_parser("audit", help="Run an orchestrated architectural audit (ArchAI)")
    audit_parser.add_argument("path", nargs="?", default=None, help="Path to project root")
    audit_parser.add_argument("--context", help="Project goal/context")
    audit_parser.add_argument("--status", help="Current project status")
    audit_parser.add_argument("--goal", help="Target 'perfect' state")
    audit_parser.add_argument("--model", default="qwen3-coder:480b-cloud", help="Model to use")
    audit_parser.add_argument("--verbose", action="store_true", help="Show detailed execution logs")
    audit_parser.add_argument("--diagnostics", action="store_true", help="Run path scan only (no AI) to verify readability")

    # Test command
    test_parser = subparsers.add_parser("test", help="Run iterative test generation loop")
    test_parser.add_argument("--model", default="qwen3-coder:480b-cloud", help="Model to use")
    test_parser.add_argument("--verbose", action="store_true", help="Show detailed execution logs")

    args = parser.parse_args()

    # 1. Initialize Ollama
    model_name = initialize_ollama(preferred_model=getattr(args, 'model', "qwen3-coder:480b-cloud"))

    if args.verbose:
        logging.getLogger("ArchAI").setLevel(logging.INFO)

    if args.command == "audit":
        path = args.path or os.getcwd()
        asyncio.run(run_archai_flow(path, args.context, args.status, args.goal, args.verbose, args.diagnostics))
    elif args.command == "test":
        asyncio.run(run_improvement_loop())
    else:
        # Interactive mode or help
        print("\nNo command provided. Launching interactive wizard...")
        asyncio.run(run_improvement_loop())

if __name__ == "__main__":
    run_cli()

import asyncio
import sys
import os
import json
import argparse
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from .core_ai.generator import CoreAI
from .evaluations.runner import EvaluationRunner
from .improvement_engine.analyzer import ImprovementEngine
from .reconciler.logic import Reconciler
from .core_ai.auditor import ArchitecturalAuditor
from .utils.ollama_manager import initialize_ollama
from .analysis.validator import ArchValidator

# Global logging config
logging.basicConfig(level=logging.WARNING, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("ArchAI.CLI")

def save_feedback(useful: bool, rejected_ids: List[str]):
    feedback_file = "archai_feedback.json"
    data = []
    if os.path.exists(feedback_file):
        try:
            with open(feedback_file, "r") as f:
                data = json.load(f)
        except: data = []
    
    entry = {
        "timestamp": str(datetime.now()),
        "useful": useful,
        "rejected_ids": rejected_ids
    }
    data.append(entry)
    with open(feedback_file, "w") as f:
        json.dump(data, f, indent=4)

async def run_archai_flow(path: str, context: Optional[str] = None, status: Optional[str] = None, goal: Optional[str] = None, verbose: bool = False, diagnostics: bool = False):
    if verbose:
        logging.getLogger("ArchAI").setLevel(logging.INFO)
    
    auditor = ArchitecturalAuditor()
    
    if diagnostics:
        print(f"\n[DIAGNOSTIC MODE] Scanning: {path}")
        structure = auditor.scan_directory(path)
        print(structure)
        return

    print(f"\n🚀 Starting ArchAI Sprint Planning Audit: {path}")
    report = await auditor.audit_project(
        root_path=path,
        user_context=context or "Improve reliability and sprint planning",
        project_status=status or "Stable"
    )
    
    with open("archai_report.json", "w") as f:
        json.dump(report, f, indent=4)
        
    print(f"\n{'='*70}")
    print(f" ARCHAI SPRINT ADVISOR: {os.path.basename(path)} ")
    print(f"{'='*70}")
    
    tasks = report.get('tasks', [])
    sprint_plan = report.get('sprintPlan', [])
    
    print(f"\n[IDENTIFIED WORK: {len(tasks)} items]")
    for t in tasks:
        prio = t.get('priority', 'Medium')
        tid = t.get('ticket_id', '???')
        title = t.get('title', 'Unknown')
        epic = t.get('epic', 'General')
        risk = " [RISKY]" if t.get('risk_flags') else ""
        conf = f"(Conf: {t.get('evidence', {}).get('confidence', 1.0):.2f})"
        print(f" - [{tid}] {prio} | EPIC: {epic} | {title}{risk} {conf}")

    print(f"\n[FEASIBILITY-DRIVEN SPRINT PLAN]")
    for day in sprint_plan:
        name = day.get('day')
        hrs = day.get('total_hours', 0)
        feas = day.get('feasibility', 'Unknown')
        print(f"\n {name} ({hrs:.1f}h) - STATUS: {feas}")
        for t in day.get('tickets', []):
            print(f"   * [{t.get('ticket_id')}] {t.get('title')}")

    print(f"\n{'='*70}")
    print(f"Use 'ai-architect trace <ID>' to see evidence for a finding.")
    print(f"Use 'ai-architect explain' for a detailed summary.")
    
    useful = input("\nWas this sprint plan helpful? (y/n): ").lower().strip() == 'y'
    save_feedback(useful, [])
    print("Feedback saved. Thank you!")

def run_cli():
    parser = argparse.ArgumentParser(description="ArchAI: Sprint Planning & Architectural Reliability")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Audit
    audit_parser = subparsers.add_parser("audit", help="Run sprint planning audit")
    audit_parser.add_argument("path", nargs="?", default=None)
    audit_parser.add_argument("--verbose", action="store_true")
    audit_parser.add_argument("--diagnostics", action="store_true")
    audit_parser.add_argument("--explain", action="store_true", help="Show explanation after audit")
    audit_parser.add_argument("--trace", help="Show evidence for specific ticket ID after audit")

    # Trace
    trace_parser = subparsers.add_parser("trace", help="Show evidence for a specific ticket ID")
    trace_parser.add_argument("ticket_id")

    # Explain
    explain_parser = subparsers.add_parser("explain", help="Detailed architectural explanation")

    # Validate
    validate_parser = subparsers.add_parser("validate", help="CI/CD Validation")
    validate_parser.add_argument("path", nargs="?", default=None)

    args = parser.parse_args()

    if args.command == "audit":
        initialize_ollama()
        path = args.path or os.getcwd()
        asyncio.run(run_archai_flow(path, verbose=args.verbose, diagnostics=args.diagnostics))
        
        if args.explain:
            with open("archai_report.json", "r") as f:
                report = json.load(f)
            print("\n[ARCHITECTURAL EXPLANATION]")
            print(report.get("gap_analysis", "No explanation available."))
        
        if args.trace:
            with open("archai_report.json", "r") as f:
                report = json.load(f)
            ticket = next((t for t in report.get('tasks', []) if t.get('ticket_id') == args.trace), None)
            if ticket:
                ev = ticket.get('evidence', {})
                print(f"\n[TRACE EVIDENCE FOR {args.trace}]")
                print(f"File: {ev.get('file_path', 'N/A')} | Symbol: {ev.get('symbol', 'N/A')}")
                print(f"Fix: {ticket.get('suggested_fix', 'N/A')}")
            else:
                print(f"Ticket {args.trace} not found.")
    
    elif args.command == "trace":
        if not os.path.exists("archai_report.json"):
            print("No report found. Run 'audit' first.")
            return
        with open("archai_report.json", "r") as f:
            report = json.load(f)
        
        ticket = next((t for t in report.get('tasks', []) if t.get('ticket_id') == args.ticket_id), None)
        if not ticket:
            print(f"Ticket {args.ticket_id} not found.")
            return
        
        ev = ticket.get('evidence', {})
        print(f"\n[TRACE EVIDENCE FOR {args.ticket_id}]")
        print(f"Title: {ticket.get('title')}")
        print(f"Epic: {ticket.get('epic', 'N/A')}")
        print(f"File: {ev.get('file_path', 'N/A')}")
        print(f"Symbol: {ev.get('symbol', 'N/A')}")
        print(f"Lines: {ev.get('line_range', 'N/A')}")
        print(f"Confidence: {ev.get('confidence', 0.0):.2f}")
        if ev.get('uncertainty_drivers'):
            print(f"Uncertainty: {', '.join(ev.get('uncertainty_drivers'))}")
        
        deps = ticket.get('dependencies', [])
        if deps:
            print(f"Dependencies: {', '.join(deps)}")
        
        print(f"\nSuggested Fix:\n{ticket.get('suggested_fix', 'No fix suggested.')}")

    elif args.command == "explain":
        if not os.path.exists("archai_report.json"):
            print("No report found.")
            return
        with open("archai_report.json", "r") as f:
            report = json.load(f)
        print("\n[ARCHITECTURAL SUMMARY]")
        print(report.get("gap_analysis", "No detailed explanation available."))

    elif args.command == "validate":
        path = args.path or os.getcwd()
        validator = ArchValidator(path)
        result = validator.run_validation()
        print(f"\nStatus: {'PASSED' if result['success'] else 'FAILED'}")
        for v in result['violations']:
            print(f" - [{v['severity']}] {v['message']}")
        sys.exit(0 if result['success'] else 1)

    else:
        print("ArchAI: Use 'audit', 'trace', 'explain', or 'validate'.")

if __name__ == "__main__":
    run_cli()

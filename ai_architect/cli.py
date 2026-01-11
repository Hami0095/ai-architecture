import asyncio
import sys
import os
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path
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
    audit_parser.add_argument("--explain", action="store_true")
    audit_parser.add_argument("--trace")

    # Trace
    trace_parser = subparsers.add_parser("trace", help="Show evidence for a specific ticket ID")
    trace_parser.add_argument("ticket_id")

    # Explain
    explain_parser = subparsers.add_parser("explain", help="Detailed architectural explanation")

    # Validate
    validate_parser = subparsers.add_parser("validate", help="CI/CD Validation")
    validate_parser.add_argument("path", nargs="?", default=None)

    # Impact (CIRAS)
    impact_parser = subparsers.add_parser("impact", help="Change Impact & Risk Assessment (CIRAS)")
    impact_parser.add_argument("target", help="File path or symbol name to assess")
    impact_parser.add_argument("--depth", type=int, default=3, help="Max call graph depth")
    impact_parser.add_argument("--json", action="store_true")
    impact_parser.add_argument("--explain", action="store_true")
    impact_parser.add_argument("--strict", action="store_true")
    impact_parser.add_argument("--verbose", action="store_true")

    # Plan (WDP-TG)
    plan_parser = subparsers.add_parser("plan", help="Work Decomposition & Task Generation (WDP-TG)")
    plan_parser.add_argument("goal", help="Engineering goal or feature request")
    plan_parser.add_argument("--team-size", type=int, default=3)
    plan_parser.add_argument("--days", type=int, default=10)
    plan_parser.add_argument("--json", action="store_true")
    plan_parser.add_argument("--verbose", action="store_true")
    plan_parser.add_argument("--strict", action="store_true")
    plan_parser.add_argument("--simulate-sprint", action="store_true")

    # SRC (Simulation & Confidence)
    src_parser = subparsers.add_parser("simulate-sprint", help="Sprint Success Simulation (SRC-RS)")
    src_parser.add_argument("goal", help="Engineering goal to simulate")
    src_parser.add_argument("--team-size", type=int, default=3)
    src_parser.add_argument("--days", type=int, default=10)
    src_parser.add_argument("--json", action="store_true")
    src_parser.add_argument("--verbose", action="store_true")
    src_parser.add_argument("--strict", action="store_true")

    rel_parser = subparsers.add_parser("release-confidence", help="Release Integrity Assessment")
    rel_parser.add_argument("goal", help="Release target to evaluate")
    rel_parser.add_argument("--team-size", type=int, default=3)
    rel_parser.add_argument("--days", type=int, default=10)
    rel_parser.add_argument("--json", action="store_true")
    rel_parser.add_argument("--strict", action="store_true")

    args = parser.parse_args()

    if args.command == "audit":
        initialize_ollama()
        path = args.path or os.getcwd()
        asyncio.run(run_archai_flow(path, verbose=args.verbose, diagnostics=args.diagnostics))
        
        if args.explain:
             if os.path.exists("archai_report.json"):
                with open("archai_report.json", "r") as f:
                    report = json.load(f)
                print("\n[ARCHITECTURAL EXPLANATION]")
                print(report.get("gap_analysis", "No explanation available."))
        
        if args.trace:
             if os.path.exists("archai_report.json"):
                with open("archai_report.json", "r") as f:
                    report = json.load(f)
                ticket = next((t for t in report.get('tasks', []) if t.get('ticket_id') == args.trace), None)
                if ticket:
                    ev = ticket.get('evidence', {})
                    print(f"\n[TRACE EVIDENCE FOR {args.trace}]")
                    print(f"File: {ev.get('file_path', 'N/A')} | Symbol: {ev.get('symbol', 'N/A')}")
                    print(f"Fix: {ticket.get('suggested_fix', 'N/A')}")
    
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

    elif args.command == "impact":
        if args.verbose:
            logging.getLogger("ArchAI").setLevel(logging.INFO)
            
        initialize_ollama()
        auditor = ArchitecturalAuditor()
        assessment = auditor.ImpactAnalyzer(os.getcwd(), args.target, max_depth=args.depth)
        
        if args.json:
            print(assessment.model_dump_json(indent=4))
            return

        print(f"\n{'='*70}")
        print(f" CIRAS IMPACT ASSESSMENT: {args.target} ")
        print(f"{'='*70}")
        
        status_color = "🔴" if assessment.risk_level == "HIGH" else "🟡" if assessment.risk_level == "MEDIUM" else "🟢"
        if assessment.risk_level == "UNKNOWN": status_color = "⚪"
        
        print(f"\n RISK LEVEL: {status_color} {assessment.risk_level} ({assessment.risk_score:.1f}/100)")
        print(f" CONFIDENCE: {assessment.confidence_score*100:.1f}%")
        
        if assessment.insufficient_data:
            print("\n [!] INSUFFICIENT DATA: Analysis could not be completed.")
            print(f" Rationale: {assessment.rationale}")
            return

        print(f"\n[AFFECTED COMPONENTS: {len(assessment.affected_components)} items]")
        for comp in assessment.affected_components:
            print(f" - {comp.get('name')} (Depth: {comp.get('depth')}) | File: {comp.get('file')}")

        print(f"\n[PRIMARY RISK FACTORS]")
        for factor in assessment.primary_risk_factors:
            print(f" ! {factor}")

        print(f"\n[ENGINEERING RECOMMENDATIONS]")
        for rec in assessment.recommendations:
            print(f" * {rec}")

        if args.explain and assessment.rationale:
            print(f"\n[DETAILED RATIONALE]")
            print(assessment.rationale)

        print(f"\n{'='*70}")
        if args.strict and assessment.risk_level == "HIGH":
            print("\nSTRICT MODE: Change blocked due to HIGH risk.")
            sys.exit(1)

    elif args.command == "plan":
        if args.verbose:
            logging.getLogger("ArchAI").setLevel(logging.INFO)
            
        initialize_ollama()
        from .data.models import SprintPlanConfig
        auditor = ArchitecturalAuditor()
        config = SprintPlanConfig(team_size=args.team_size, days=args.days)
        
        print(f"\n🚀 Decomposing goal into actionable tasks: {args.goal}")
        plan = auditor.WDPPlanner(os.getcwd(), args.goal, sprint_config=config)
        
        if args.json:
            print(plan.model_dump_json(indent=4))
            return

        print(f"\n{'='*70}")
        print(f" WDP-TG SPRINT PLAN: {args.goal} ")
        print(f"{'='*70}")
        
        for epic in plan.epics:
            print(f"\n EPIC: {epic.get('name')}")
            print(f" Description: {epic.get('description')}")
            for t in epic.get('tickets', []):
                prio = t.get('priority', 'Medium')
                tid = t.get('ticket_id', '???')
                risk = f" [{', '.join(t.get('risk_flags', []))}]" if t.get('risk_flags') else ""
                print(f"   - [{tid}] {prio} | {t.get('title')}{risk}")
                owner = t.get('suggested_owner')
                if owner: print(f"     Owner: {owner}")
                if args.verbose:
                    print(f"     Effort: {t.get('effort_hours')}h | Deps: {t.get('dependencies', [])}")
                
                subtasks = t.get('subtasks', [])
                for st in subtasks:
                    print(f"       > {st.get('title')} ({st.get('effort_hours')}h)")

        feas = plan.sprint_feasibility
        status_color = "🟢" if feas.get('status') == "Likely fits" else "🟡" if feas.get('status') == "High risk" else "🔴"
        print(f"\n FEASIBILITY: {status_color} {feas.get('status')}")
        print(f" Rationale: {feas.get('rationale')}")
        
        if feas.get('bottlenecks'):
            print("\n BOTTLENECKS IDENTIFIED:")
            for b in feas['bottlenecks']:
                print(f" ! {b}")

        print(f"\n CONFIDENCE SCORE: {plan.overall_confidence*100:.1f}%")
        if plan.assumptions:
             print("\n ASSUMPTIONS:")
             for a in plan.assumptions:
                 print(f" * {a}")

        print(f"\n{'='*70}")
        if args.strict and feas.get('status') == "Will overflow":
            print("\nSTRICT MODE: Plan blocked due to capacity overflow.")
            sys.exit(1)

    elif args.command in ["simulate-sprint", "release-confidence"]:
        if args.verbose:
            logging.getLogger("ArchAI").setLevel(logging.INFO)
            
        initialize_ollama()
        from .data.models import SprintPlanConfig
        auditor = ArchitecturalAuditor()
        config = SprintPlanConfig(team_size=args.team_size, days=args.days)
        
        # 1. Generate Plan first (Internal call)
        print(f"🚀 Step 1: Generating Work Decomposition (WDP-TG)...")
        plan = auditor.WDPPlanner(os.getcwd(), args.goal, sprint_config=config)
        
        # 2. Run Simulation
        print(f"🛡️ Step 2: Simulating Execution & Predicting Confidence (SRC-RS)...")
        src = auditor.SRCEngine(os.getcwd(), args.goal, wdp_plan=plan, sprint_config=config, strict=args.strict)
        
        if args.json:
            print(src.model_dump_json(indent=4))
            return

        print(f"\n{'='*70}")
        print(f" SRC-RS RELEASE CONFIDENCE: {args.goal} ")
        print(f"{'='*70}")
        
        conf_color = "🔴" if src.confidence_score < 0.5 else "🟡" if src.confidence_score < 0.8 else "🟢"
        print(f"\n OVERALL CONFIDENCE: {conf_color} {src.confidence_score*100:.1f}% ({src.status})")
        print(f" Rationale: {src.confidence_rationale}")
        
        print("\n[PREDICTED COMPLETION BY EPIC]")
        for e in src.epic_forecasts:
            p = e.get('completion_probability', 0)
            status = "🟢" if p > 0.8 else "🟡" if p > 0.5 else "🔴"
            print(f" {status} {e.get('epic_name')}: {p*100:.1f}%")

        if args.verbose:
            print("\n[PER-TASK PREDICTIONS]")
            for tp in src.task_predictions:
                p = tp.probability
                status = "🟢" if p > 0.8 else "🟡" if p > 0.5 else "🔴"
                print(f" {status} [{tp.ticket_id}] {p*100:.0f}% | {tp.risk_level} | {tp.completion_window}")
                print(f"   Rationale: {tp.rationale}")

        print("\n[TASKS AT RISK]")
        if src.risk_summary.get('critical'):
            print(f" ! CRITICAL: {', '.join(src.risk_summary['critical'])}")
        if src.risk_summary.get('high'):
            print(f" ! HIGH: {', '.join(src.risk_summary['high'])}")

        print("\n[SAFETY RECOMMENDATIONS]")
        for rec in src.recommendations:
            print(f" * {rec.get('task')}: {rec.get('action')}")

        if src.bottlenecks:
            print("\n[BOTTLENECKS]")
            for b in src.bottlenecks:
                print(f" - {b}")

        print(f"\n{'='*70}")

    else:
        print("ArchAI: Use 'audit', 'trace', 'explain', 'impact' or 'validate'.")

if __name__ == "__main__":
    run_cli()

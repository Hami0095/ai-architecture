import asyncio
import sys
import os
import shlex
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
from .utils.console_utils import ConsoleUI
from .infrastructure.config_manager import config
from .connectors.github import GitHubConnector
from .connectors.google_drive import GoogleDriveConnector
from .connectors.pm import PMConnector
from .infrastructure.usage_tracker import BackupManager, UsageTracker
from .data.models import SprintPlanConfig

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
    ConsoleUI.step_header("Context Acquisition", "Discovering and validating structural metadata")
    ConsoleUI.progress_bar("Path Navigation", 0.3)
    ConsoleUI.progress_bar("Discovery Agent", 0.5)
    
    auditor = ArchitecturalAuditor()
    if verbose:
        logging.getLogger("ArchAI").setLevel(logging.INFO)

    if diagnostics:
         ConsoleUI.step_header("Site Survey (Diagnostics)", "Performing non-destructive structural scan")
         structure = auditor.scan_directory(path)
         print(structure)
         return

    # 1. Structural Analysis
    ConsoleUI.step_header("Structural Analysis", "Mapping component relationships and critical paths")
    
    report = await auditor.audit_project(
        root_path=path,
        user_context=context or "Improve reliability and sprint planning",
        project_status=status or "Stable"
    )
    
    with open("archai_report.json", "w") as f:
        json.dump(report, f, indent=4)
        
    ConsoleUI.step_header("Execution Forecast", f"Deterministic plan for {os.path.basename(path)}")
    
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
    print(f"SUGGESTED NEXT STEP: Use 'trace <ID>' to see evidence for specific tickets.")
    print(f"ALTERNATELY: Use 'impact <path> <symbol>' to analyze risks of identified areas.")
    print(f"Use 'explain' for a detailed summary.")
    
    useful = input("\nWas this sprint plan helpful? (y/n): ").lower().strip() == 'y'
    save_feedback(useful, [])
    print("Feedback saved. Thank you!")

def print_help_table():
    print(f"\n{'='*80}")
    print(f"{'COMMAND':<25} | {'DESCRIPTION':<50}")
    print(f"{'-'*25}-+-{'-'*50}")
    print(f"{'PLAN':<25} | {'Generate actionable tasks (WDP-TG) for a goal'}")
    print(f"{'IMPACT':<25} | {'Assess risk (CIRAS) for a file or symbol'}")
    print(f"{'AUDIT':<25} | {'Full architectural audit and sprint planning'}")
    print(f"{'TRACE':<25} | {'Show evidence trail for a specific ticket ID'}")
    print(f"{'SIMULATE':<25} | {'Simulate sprint execution success (SRC-RS)'}")
    print(f"{'RELEASE-CONFIDENCE':<25} | {'Evaluate integrity of a release target'}")
    print(f"{'SET-GITHUB-TOKEN':<25} | {'Securely register GitHub Personal Access Token'}")
    print(f"{'SET-PM-TOKEN':<25} | {'Securely register Jira/Trello credentials'}")
    print(f"{'CONFIG':<25} | {'View current configuration and integrations'}")
    print(f"{'HELP':<25} | {'Show this command context table'}")
    print(f"{'EXIT / PHIR-MILTY-HAIN':<25} | {'Terminate the ArchAI console session'}")
    print(f"{'='*80}\n")

def process_command(cmd_line: str):
    try:
        parts = shlex.split(cmd_line)
    except ValueError:
        print("Error: Invalid command syntax.")
        return

    if not parts:
        return

    command = parts[0].upper()
    args = parts[1:]

    # --- CONFIGURATION COMMANDS ---
    if command == "SET-GITHUB-TOKEN":
        if len(args) != 1:
            print("Usage: SET-GITHUB-TOKEN <token>")
            return
        os.environ["ARCHAI_GITHUB_TOKEN"] = args[0]
        # In a real app we would save to keyring/config
        print("✅ GitHub token updated in session environment.")
        return

    if command == "SET-PM-TOKEN":
        if len(args) < 2:
            print("Usage: SET-PM-TOKEN <service> <token> [extra_id]")
            return
        service = args[0].upper()
        if service == "JIRA":
             os.environ["ARCHAI_JIRA_TOKEN"] = args[1]
             print("✅ Jira token updated in session environment.")
        elif service == "TRELLO":
             os.environ["ARCHAI_TRELLO_TOKEN"] = args[1]
             if len(args) > 2: os.environ["ARCHAI_TRELLO_API_KEY"] = args[2]
             print("✅ Trello credentials updated.")
        else:
            print("Unknown service. Use JIRA or TRELLO.")
        return

    if command == "CONFIG":
        print("\n[CURRENT CONFIGURATION]")
        print(f" User Identity: {config.get('user_id', 'Anonymous')}")
        print(f" Model: {config.get('model', 'Unknown')}")
        print(f" GitHub Integration: {'✅ Connected' if os.getenv('ARCHAI_GITHUB_TOKEN') or config.get_secret('github_token') else '❌ Missing'}")
        print(f" Jira Integration: {'✅ Connected' if os.getenv('ARCHAI_JIRA_TOKEN') or config.get_secret('jira.token') else '❌ Missing'}")
        print("")
        return

    if command == "HELP":
        print_help_table()
        return

    # --- ACTION COMMANDS (Mapped to existing logic) ---
    
    # AUDIT
    if command == "AUDIT":
        parser = argparse.ArgumentParser(prog="AUDIT", add_help=False)
        parser.add_argument("path", nargs="?", default=os.getcwd())
        parser.add_argument("--verbose", action="store_true")
        parser.add_argument("--diagnostics", action="store_true")
        try:
            parsed, unknown = parser.parse_known_args(args)
            print(f"🔍 Starting Audit on: {parsed.path}")
            initialize_ollama()
            asyncio.run(run_archai_flow(parsed.path, verbose=parsed.verbose, diagnostics=parsed.diagnostics))
        except Exception as e:
            print(f"❌ Audit failed: {e}")
        return

    # IMPACT
    if command == "IMPACT":
        if len(args) < 2:
            print("Usage: IMPACT <path> <target_symbol> [--verbose]")
            return
        path = args[0]
        target = args[1]
        verbose = "--verbose" in args
        
        try:
            if verbose: logging.getLogger("ArchAI").setLevel(logging.INFO)
            initialize_ollama()
            auditor = ArchitecturalAuditor()
            print(f"🛡️ Assessing Impact for: {target} in {path}")
            assessment = auditor.ImpactAnalyzer(path, target)
            
            status_color = "🔴" if assessment.risk_level == "HIGH" else "🟡" if assessment.risk_level == "MEDIUM" else "🟢"
            print(f"\n RISK LEVEL: {status_color} {assessment.risk_level} ({assessment.risk_score:.1f}/100)")
            print(f" CONFIDENCE: {assessment.confidence_score*100:.1f}%")
            if assessment.rationale:
                print(f" Rationale: {assessment.rationale}")
        except Exception as e:
            print(f"❌ Impact analysis failed: {e}")
        return

    # PLAN
    if command == "PLAN":
        if len(args) < 2:
            print("Usage: PLAN <path> <goal> [--days N]")
            return
        path = args[0]
        goal = args[1]
        
        try:
            initialize_ollama()
            auditor = ArchitecturalAuditor()
            conf = SprintPlanConfig()
            print(f"🚀 Generating Plan for: {goal}")
            plan = auditor.WDPPlanner(path, goal, sprint_config=conf)
            
            print(f"\n[GENERATED PLAN]")
            for epic in plan.epics:
                print(f" Epic: {epic.get('name')}")
                for t in epic.get('tickets', []):
                    print(f"  - [{t.get('ticket_id')}] {t.get('title')} ({t.get('effort_hours')}h)")
        except Exception as e:
            print(f"❌ Planning failed: {e}")
        return

    # TRACE
    if command == "TRACE":
        if not args:
            print("Usage: TRACE <ticket_id>")
            return
        ticket_id = args[0]
        if not os.path.exists("archai_report.json"):
             print("No active report found. Run AUDIT first.")
             return
        with open("archai_report.json", "r") as f:
            report = json.load(f)
        ticket = next((t for t in report.get('tasks', []) if t.get('ticket_id') == ticket_id), None)
        if ticket:
             ev = ticket.get('evidence', {})
             print(f"\n[TRACE EVIDENCE FOR {ticket_id}]")
             print(f" File: {ev.get('file_path', 'N/A')}")
             print(f" Symbol: {ev.get('symbol', 'N/A')}")
             print(f" Confidence: {ev.get('confidence', 'N/A')}")
        else:
            print(f"Ticket {ticket_id} not found.")
        return

    # SIMULATE / RELEASE-CONFIDENCE (Shared logic)
    if command in ["SIMULATE", "RELEASE-CONFIDENCE"]:
         if len(args) < 2:
            print(f"Usage: {command} <path> <goal>")
            return
         path = args[0]
         goal = args[1]
         try:
            initialize_ollama()
            auditor = ArchitecturalAuditor()
            conf = SprintPlanConfig()
            print(f"🎲 Simulating Execution: {goal}")
            plan = auditor.WDPPlanner(path, goal, sprint_config=conf)
            src = auditor.SRCEngine(path, goal, wdp_plan=plan, sprint_config=conf)
            
            print(f"\n CONFIDENCE: {src.confidence_score*100:.1f}% ({src.status})")
            print(f" Rationale: {src.confidence_rationale}")
         except Exception as e:
             print(f"❌ Simulation failed: {e}")
         return


    print(f"Unknown command: {command}. Type HELP for valid commands.")

def run_interactive_console():
    # 1. Identity Banner
    ConsoleUI.banner()
    
    # 2. System Status
    user_id = config.get("user_id", "Anonymous-Engineer")
    auth_token = config.get_secret("google_drive_token")
    mode = "AUTHENTICATED" if auth_token else "TEST-MODE"
    
    print(f"{'='*80}")
    print(f" IDENTITY: {user_id} | MODE: {mode} | MODEL: {config.get('model','Default')}")
    print(f"{'='*80}\n")

    # 3. Command Context
    print_help_table()

    # 4. REPL Loop
    while True:
        try:
            user_input = input("ArchAI> ").strip()
            if not user_input:
                continue
            
            if user_input.lower() in ["exit", "quit", "phir-milty-hain", "phir milty hain"]:
                print("🛑 Session Terminated. Phir milty hain!")
                break
                
            process_command(user_input)
            
        except KeyboardInterrupt:
            print("\n(Use 'phir-milty-hain' to exit)")
        except Exception as e:
            logger.error(f"Console Error: {e}")
            print(f"Critical Console Error: {e}")

def run_cli():
    """Main entry point for the ai-architect command."""
    run_interactive_console()

if __name__ == "__main__":
    run_cli()

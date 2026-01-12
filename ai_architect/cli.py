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
from .data.models import SprintPlanConfig, WDPOutput, AuditTicket

# Global logging config
logging.basicConfig(level=logging.WARNING, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("ArchAI.CLI")

class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)

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
    
    with ConsoleUI.spinner("Executing 7-agent architectural adjudication pipeline"):
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
        
        # Phase 1 Hardening: Range and Confidence
        emin = t.get('effort_min', 1.0)
        emax = t.get('effort_max', 4.0)
        clevel = t.get('confidence_level', 'HIGH')
        cscore = t.get('confidence_score', 1.0)
        
        # Highlight: Risky if flags present, level not HIGH, or score < 70%
        is_risky = t.get('risk_flags') or clevel != 'HIGH' or cscore < 0.7
        risk = " [RISKY]" if is_risky else ""
        drivers = f" | DRIVERS: {', '.join(t.get('uncertainty_drivers', []))}" if t.get('uncertainty_drivers') else ""
        
        print(f" - [{tid}] {prio} | EPIC: {epic} | [{emin}-{emax}h] | {title}{risk} (Conf: {clevel} {cscore*100:.0f}%){drivers}")

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
    print(f"{'GITHUB':<25} | {'Interact with GitHub (CONNECT, PRS, ANALYZE)'}")
    print(f"{'TRACE':<25} | {'Show evidence trail for a specific ticket ID'}")
    print(f"{'SIMULATE':<25} | {'Simulate success for a goal or specific ticket ID'}")
    print(f"{'EXPLAIN':<25} | {'Justify decisions (PRIORITY, EFFORT, RISK, DEP)'}")
    print(f"{'RELEASE-CONFIDENCE':<25} | {'Evaluate integrity of a release target'}")
    print(f"{'G-REASON':<25} | {'Deterministic graph-based architectural reasoning'}")
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
        gh_status = '✅ Connected' if os.getenv('ARCHAI_GITHUB_TOKEN') or config.get_secret('github.token') or config.get_secret('github_token') else '❌ Missing'
        pm_status = '✅ Connected' if os.getenv('ARCHAI_JIRA_TOKEN') or config.get_secret('jira.token') else '❌ Missing'
        print("\n[CURRENT CONFIGURATION]")
        print(f" User Identity: {config.get('user_id', 'Anonymous')}")
        print(f" Model: {config.get('model', 'Unknown')}")
        print(f" GitHub Integration: {gh_status}")
        print(f" Jira Integration: {pm_status}")
        print("")
        return

    if command == "HELP":
        print_help_table()
        return

    # --- GITHUB COMMANDS ---
    if command == "GITHUB":
        if not args:
            print("Usage: GITHUB <subcommand> [args]")
            print("Subcommands: CONNECT <repo>, PRS <repo>, ANALYZE <repo> <pr#> <local_path>, AUDIT <repo>, VALIDATE-LOCAL <path> [base]")
            return
        
        sub = args[0].upper()
        connector = GitHubConnector()
        
        if sub == "CONNECT":
            if len(args) < 2:
                print("Usage: GITHUB CONNECT <owner/repo>")
                return
            repo_name = args[1].replace("https://github.com/", "")
            print(f"📡 Connecting to {repo_name}...")
            repo = connector.get_repo(repo_name)
            if repo:
                print(f"✅ Success: {repo.full_name}")
                print(f"   Stars: {repo.stargazers_count} | Forks: {repo.forks_count}")
                print(f"   Description: {repo.description}")
            return

        if sub == "PRS":
            if len(args) < 2:
                print("Usage: GITHUB PRS <owner/repo>")
                return
            repo_name = args[1].replace("https://github.com/", "")
            print(f"🔍 Fetching open PRs for {repo_name}...")
            with ConsoleUI.spinner("Retrieving PR metadata from GitHub API"):
                prs = connector.fetch_open_prs(repo_name)
            if not prs:
                print("No open PRs found.")
            else:
                for pr in prs:
                    print(f" #{pr.number} | {pr.title} (by {pr.author})")
            return

        if sub == "ANALYZE":
            if len(args) < 4:
                print("Usage: GITHUB ANALYZE <owner/repo> <pr_number> <local_path> [--publish]")
                return
            repo_name = args[1].replace("https://github.com/", "")
            pr_num = int(args[2])
            local_path = args[3]
            publish = "--publish" in args
            
            print(f"🛡️ Analyzing PR #{pr_num} for {repo_name}...")
            with ConsoleUI.spinner("Adjudicating PR architectural impact"):
                report = connector.analyze_pr(repo_name, pr_num, local_path)
            if report:
                print(f"\n[ANALYSIS REPORT PR #{pr_num}]")
                c_level = report.impact_assessment.confidence_level
                c_score = report.impact_assessment.confidence_score
                print(f" Impact: {report.impact_assessment.risk_level} (Score: {report.impact_assessment.risk_score:.1f})")
                print(f" Confidence: {c_level} ({c_score*100:.1f}%)")
                if report.impact_assessment.uncertainty_drivers:
                    print(f" Drivers: {', '.join(report.impact_assessment.uncertainty_drivers)}")
                print(f" Rationale: {report.impact_assessment.rationale}")
                
                if publish:
                    print(f"🚀 Publishing comment to PR #{pr_num}...")
                    connector.post_pr_comment(repo_name, pr_num, report)
                    print("✅ Comment published.")
                else:
                    print("ℹ️ Quiet Mode: Use --publish to post this as a PR comment.")
            return

        if sub == "AUDIT":
            if len(args) < 2:
                print("Usage: GITHUB AUDIT <owner/repo> [--goal 'goal text']")
                return
            repo_name = args[1].replace("https://github.com/", "")
            
            goal = None
            if "--goal" in args:
                goal_idx = args.index("--goal")
                if len(args) > goal_idx + 1:
                    goal = args[goal_idx + 1]
            
            print(f"🔍 Starting Deep Audit on remote repo: {repo_name}")
            if goal:
                print(f"🎯 Target Goal: {goal}")
            initialize_ollama()
            # We need to run inside a dummy flow for progress headers etc.
            # But for simplicity, we directly call the auditor through the connector
            with ConsoleUI.spinner("Cloning and auditing remote infrastructure"):
                report = asyncio.run(connector.audit_repo(repo_name, context=goal))
            if report:
                # Save to locally for TRACE and future commands
                with open("archai_report.json", "w") as f:
                    json.dump(report, f, indent=4)
                
                # Print results (reusing some logic from run_archai_flow)
                tasks = report.get('tasks', [])
                print(f"\n[IDENTIFIED WORK: {len(tasks)} items]")
                for t in tasks:
                    prio = t.get('priority', 'Medium')
                    tid = t.get('ticket_id', '???')
                    title = t.get('title', 'Unknown')
                    print(f" - [{tid}] {prio} | {title}")
                print(f"\nAudit complete. Use 'TRACE <ID>' for evidence.")
            return

        if sub == "VALIDATE-LOCAL":
            if len(args) < 2:
                print("Usage: GITHUB VALIDATE-LOCAL <path> [base_branch]")
                return
            path = args[1]
            base = args[2] if len(args) > 2 else "main"
            print(f"🔍 Starting Quiet Validation for {path} vs {base}...")
            initialize_ollama()
            with ConsoleUI.spinner("Evaluating local diff against base branch safety thresholds"):
                reports = connector.validate_local_diff(path, base)
            if not reports:
                print("No changes found or analysis failed.")
            else:
                print(f"\n[VALIDATION SUMMARY: {len(reports)} files]")
                for r in reports:
                    status_color = "🔴" if r.risk_level == "HIGH" else "🟡" if r.risk_level == "MEDIUM" else "🟢"
                    print(f" - {r.target} | RISK: {status_color} {r.risk_level} | CONF: {r.confidence_level} ({r.confidence_score*100:.0f}%)")
                    if r.uncertainty_drivers:
                        print(f"   ! Drivers: {', '.join(r.uncertainty_drivers)}")
            return

        print(f"Unknown GITHUB subcommand: {sub}")
        return

    # --- ACTION COMMANDS (Mapped to existing logic) ---
    
    # AUDIT
    if command == "AUDIT":
        parser = SafeArgumentParser(prog="AUDIT", add_help=False)
        parser.add_argument("path", nargs="?", default=os.getcwd())
        parser.add_argument("--goal", type=str, help="Specific architectural goal for the audit")
        parser.add_argument("--verbose", action="store_true")
        parser.add_argument("--diagnostics", action="store_true")
        try:
            parsed, unknown = parser.parse_known_args(args)
            print(f"🔍 Starting Audit on: {parsed.path}")
            if parsed.goal:
                print(f"🎯 Target Goal: {parsed.goal}")
            initialize_ollama()
            asyncio.run(run_archai_flow(parsed.path, context=parsed.goal, verbose=parsed.verbose, diagnostics=parsed.diagnostics))
        except ValueError as e:
            print(f"❌ Audit Usage Error: {e}")
            print("Usage: AUDIT <path> [--goal 'goal'] [--verbose] [--diagnostics]")
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
            with ConsoleUI.spinner("Mapping dependency fan-out and risk propagation"):
                assessment = auditor.ImpactAnalyzer(path, target)
            
            status_color = "🔴" if assessment.risk_level == "HIGH" else "🟡" if assessment.risk_level == "MEDIUM" else "🟢"
            print(f"\n RISK LEVEL: {status_color} {assessment.risk_level} ({assessment.risk_score:.1f}/100)")
            conf_color = "🟢" if assessment.confidence_level == "HIGH" else "🟡" if assessment.confidence_level == "MEDIUM" else "🔴"
            print(f" CONFIDENCE: {conf_color} {assessment.confidence_level} ({assessment.confidence_score*100:.1f}%)")
            
            if assessment.uncertainty_drivers:
                print(f" UNCERTAINTY DRIVERS: {', '.join(assessment.uncertainty_drivers)}")
            
            if assessment.rationale:
                print(f" RATIONALE: {assessment.rationale}")
            
            if assessment.affected_components:
                print("\n AFFECTED EDGES:")
                for comp in assessment.affected_components:
                    print(f"   -> {comp.get('name')} [Depth: {comp.get('depth')}] in {comp.get('file')} (Edge: {comp.get('dependency_edge', 'Direct')})")
        except Exception as e:
            print(f"❌ Impact analysis failed: {e}")
        return

    # PLAN
    if command == "PLAN":
        parser = SafeArgumentParser(prog="PLAN", add_help=False)
        parser.add_argument("path", help="Project path")
        parser.add_argument("goal", help="Engineering goal")
        parser.add_argument("--team-size", type=int, default=3)
        parser.add_argument("--days", type=int, default=5)
        parser.add_argument("--velocity", type=float, default=0.8)
        
        try:
            parsed, unknown = parser.parse_known_args(args)
            initialize_ollama()
            auditor = ArchitecturalAuditor()
            conf = SprintPlanConfig(team_size=parsed.team_size, days=parsed.days, velocity_factor=parsed.velocity)
            
            print(f"🚀 Generating Plan for: {parsed.goal}")
            print(f"⚙️ Capacity: {parsed.team_size} devs | {parsed.days} days | {parsed.velocity*100:.0f}% velocity")
            with ConsoleUI.spinner("Analyzing codebase and decomposing work"):
                plan = auditor.WDPPlanner(parsed.path, parsed.goal, sprint_config=conf)
            
            print(f"\n[GENERATED PLAN]")
            for epic in plan.epics:
                print(f" Epic: {epic.get('name')} (Conf: {epic.get('tickets', [{}])[0].get('confidence_level', 'N/A')})")
                for t in epic.get('tickets', []):
                    emin = t.get('effort_min', 0)
                    emax = t.get('effort_max', 0)
                    print(f"  - [{t.get('ticket_id')}] {t.get('title')} [{emin}-{emax}h]")
        except ValueError as e:
            print(f"❌ Plan Usage Error: {e}")
            print("Usage: PLAN <path> <goal> [--team-size N] [--days N] [--velocity F]")
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
             print(f" Responsible Agent: {ev.get('responsible_agent', 'Unassigned')}")
             print(f" File Target: {ev.get('file_path', 'N/A')}")
             if ev.get('line_range'): print(f" Line Range: {ev.get('line_range')}")
             print(f" Confidence: {ticket.get('confidence_level', 'Unknown')} ({ticket.get('confidence_score', 0)*100:.1f}%)")
             if ticket.get('uncertainty_drivers'):
                 print(f" Uncertainty Drivers: {', '.join(ticket.get('uncertainty_drivers'))}")
             print(f" Logic Trace: {ticket.get('description')}")
        else:
            print(f"Ticket {ticket_id} not found.")
        return

    # EXPLAIN
    if command == "EXPLAIN":
        if len(args) < 2:
            print("Usage: EXPLAIN <intent> <target> [--json]")
            print("Intents: PRIORITY, EFFORT, RISK, DEPENDENCIES")
            return
        intent = args[0].upper()
        target = args[1]
        json_mode = "--json" in args
        
        # Standard artifacts
        artifacts = ["archai_report.json", "risk-map.json", "dependency-graph.json", "historical-metrics.json"]
        
        try:
            initialize_ollama()
            auditor = ArchitecturalAuditor()
            print(f"🧐 Explaining {intent} for {target}...")
            with ConsoleUI.spinner("Generating deterministic reasoning receipt"):
                result = auditor.ExplainabilityAgent(intent, target, artifacts, json_mode=json_mode)
            
            if json_mode:
                print(result.model_dump_json(indent=2))
            else:
                print("\n" + "="*80)
                print(f" ARCHAI EXPLAINABILITY REPORT: {target} [{intent}]")
                print("="*80)
                print(result.raw_markdown)
                print("="*80)
        except Exception as e:
            print(f"❌ Explanation failed: {e}")
        return

    # G-REASON
    if command == "G-REASON":
        if len(args) < 2:
            print("Usage: G-REASON <path> <query>")
            return
        path = args[0]
        query = args[1]
        try:
            initialize_ollama()
            auditor = ArchitecturalAuditor()
            print(f"🕸️ Reasoning over Deterministic Graph at {path}...")
            with ConsoleUI.spinner("Traversing multi-layer architectural graph"):
                result = auditor.DeterministicGraphEngine(path, query)
            print("\n" + "="*80)
            print(f" ARCHAI GRAPH-CORE JUDGMENT")
            print("="*80)
            print(result)
            print("="*80)
        except Exception as e:
            print(f"❌ Graph reasoning failed: {e}")
        return

    # SIMULATE / RELEASE-CONFIDENCE (Shared logic)
    if command in ["SIMULATE", "RELEASE-CONFIDENCE"]:
         parser = SafeArgumentParser(prog=command, add_help=False)
         parser.add_argument("target", nargs="*", help="Path and Goal OR Ticket ID")
         parser.add_argument("--team-size", type=int, default=3)
         parser.add_argument("--days", type=int, default=5)
         parser.add_argument("--velocity", type=float, default=0.8)
         
         try:
            parsed, unknown = parser.parse_known_args(args)
            if not parsed.target:
                raise ValueError("No target specified.")
                
            initialize_ollama()
            auditor = ArchitecturalAuditor()
            conf = SprintPlanConfig(team_size=parsed.team_size, days=parsed.days, velocity_factor=parsed.velocity)
            
            # 1. Logic for SIMULATE <ticket_id>
            if len(parsed.target) == 1:
                ticket_id = parsed.target[0]
                if not os.path.exists("archai_report.json"):
                    print("No active report found. Run AUDIT first.")
                    return
                with open("archai_report.json", "r") as f:
                    report = json.load(f)
                
                # Locate ticket in the report
                ticket_data = next((t for t in report.get('tasks', []) if t.get('ticket_id') == ticket_id), None)
                if not ticket_data:
                    print(f"Ticket {ticket_id} not found in current report.")
                    return
                
                # Map camelCase from JSON back to snake_case for Pydantic if necessary
                pd_data = ticket_data.copy()
                if "effortHours" in pd_data: pd_data["effort_hours"] = pd_data.pop("effortHours")
                if "tags" in pd_data: pd_data["labels"] = pd_data.pop("tags")
                
                ticket = AuditTicket(**pd_data)
                plan = WDPOutput(
                    epics=[{"name": "Target Ticket", "description": "Simulation for specific ticket", "tickets": [ticket]}],
                    sprint_feasibility={"status": "SPECIFIC-TARGET", "rationale": "Single ticket simulation", "bottlenecks": []},
                    overall_confidence=1.0
                )
                path = os.getcwd() 
                goal = ticket.title
                print(f"🎲 Simulating Ticket: [{ticket_id}] {goal}")
                print(f"⚙️ Capacity: {parsed.team_size} devs | {parsed.days} days | {parsed.velocity*100:.0f}% velocity")
                with ConsoleUI.spinner("Predicting execution risk and release probability"):
                    src = auditor.SRCEngine(path, goal, wdp_plan=plan, sprint_config=conf)

            else:
                path = parsed.target[0]
                goal = parsed.target[1]
                print(f"🎲 Simulating Execution: {goal}")
                print(f"⚙️ Capacity: {parsed.team_size} devs | {parsed.days} days | {parsed.velocity*100:.0f}% velocity")
                with ConsoleUI.spinner("Running Monte Carlo simulation over dependency graph"):
                    plan = auditor.WDPPlanner(path, goal, sprint_config=conf)
                    src = auditor.SRCEngine(path, goal, wdp_plan=plan, sprint_config=conf)
            
            print(f"\n CONFIDENCE: {src.confidence_score*100:.1f}% ({src.status})")
            print(f" Rationale: {src.confidence_rationale}")
         except ValueError as e:
             print(f"❌ {command} Usage Error: {e}")
             print(f"Usage: {command} <path> <goal> [--team-size N]  OR  {command} <ticket_id>")
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

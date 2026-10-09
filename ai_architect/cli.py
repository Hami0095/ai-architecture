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

from ai_architect.core_ai.generator import CoreAI
from ai_architect.evaluations.runner import EvaluationRunner
from ai_architect.improvement_engine.analyzer import ImprovementEngine
from ai_architect.reconciler.logic import Reconciler
from ai_architect.core_ai.auditor import ArchitecturalAuditor
from ai_architect.utils.ollama_manager import initialize_ollama
from ai_architect.analysis.validator import ArchValidator
from ai_architect.utils.console_utils import ConsoleUI
from ai_architect.infrastructure.config_manager import config
from ai_architect.connectors.github import GitHubConnector
from ai_architect.connectors.google_drive import GoogleDriveConnector
from ai_architect.connectors.pm import PMConnector
from ai_architect.infrastructure.usage_tracker import BackupManager, UsageTracker
from ai_architect.data.models import SprintPlanConfig, WDPOutput, AuditTicket
from ai_architect.version import ARCHAI_VERSION, get_graph_core_hash
from ai_architect.utils.license import LicenseManager
from ai_architect.standards import StandardsConfigError, exit_code, run_check
from ai_architect.standards.config import load_config
from ai_architect.standards.report import to_json, to_markdown

# Global logging config
logging.basicConfig(level=logging.WARNING, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("ArchAI.CLI")

class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)

def session_status() -> Dict[str, Any]:
    """Identity, mode and license state shown in the banner and by CONFIG.

    Modes that exist in the code:
      access   LICENSED   valid signed token in ARCHAI_LICENSE (or --license)
               DEV        ARCHAI_DEV_MODE set: license gate bypassed for local development
               BLOCKED    neither; the console refuses to start
      flags    DEMO       --test-mode (sets ARCHAI_TEST_MODE; nothing reads it yet, so no mock data)
               LEGACY-PLANNING  ARCHAI_ENABLE_LEGACY_PLANNING=1 re-enables PLAN/SIMULATE
      profile  ARCHAI_ENV (default "dev") selects config.<profile>.yaml
    """
    lic = LicenseManager.inspect_token(os.environ.get("ARCHAI_LICENSE"))
    dev = bool(os.environ.get("ARCHAI_DEV_MODE"))
    if lic["state"] == "VALID":
        access, identity, source = "LICENSED", lic["user"], "license holder"
    else:
        access = "DEV" if dev else "BLOCKED"
        identity, source = config.get("user_id", "Anonymous-Engineer"), "local config user_id, unlicensed"
    flags = [name for name, on in (
        ("DEMO", os.environ.get("ARCHAI_TEST_MODE") == "1"),
        ("LEGACY-PLANNING", legacy_planning_enabled()),
    ) if on]
    return {
        "identity": identity,
        "identity_source": source,
        "access_mode": access,
        "flags": flags,
        "profile": os.getenv("ARCHAI_ENV", "dev").lower(),
        "license": lic,
        "integrations": {
            "github": bool(os.getenv("ARCHAI_GITHUB_TOKEN") or config.get("github.token") or config.get("github_token")),
            "jira": bool(os.getenv("ARCHAI_JIRA_TOKEN") or config.get("jira.token")),
            "google_drive": bool(config.get("google_drive_token")),
        },
        "llm": f"{config.get('ai.provider', 'ollama')}:{config.get('model', 'unknown')}",
    }

def license_text(lic: Dict[str, Any]) -> str:
    if lic["state"] == "VALID":
        return f"VALID - {lic['user']}, expires {lic['expires']} ({lic['days_left']} days left)"
    return f"{lic['state']} - {lic['reason']}"

def legacy_planning_enabled() -> bool:
    """Sprint planning (PLAN, SIMULATE, RELEASE-CONFIDENCE) is deferred from the
    product; its code is kept and can be re-enabled for existing users."""
    return os.environ.get("ARCHAI_ENABLE_LEGACY_PLANNING") == "1"

def check_standards_command(args: List[str]) -> int:
    """CHECK-STANDARDS: deterministic, evidence-backed standards check. No LLM, no network."""
    parser = SafeArgumentParser(prog="CHECK-STANDARDS", add_help=False)
    parser.add_argument("path", nargs="?", default=os.getcwd())
    parser.add_argument("--config", help="Standards YAML (default: <path>/archai_standards.yaml)")
    parser.add_argument("--no-defaults", action="store_true", help="Do not add ArchAI default rules")
    parser.add_argument("--json", nargs="?", const="-", help="Write JSON report to a file, or stdout if no file")
    parser.add_argument("--markdown", help="Write the Markdown report to a file")
    parser.add_argument("--okf-out", help="Export the OKF v0.2 knowledge bundle to this directory")
    parser.add_argument("--from-okf", help="Adjudicate facts loaded from an existing OKF bundle instead of source")
    parser.add_argument("--verbose", action="store_true", help="Show full evidence and observed facts")
    try:
        parsed = parser.parse_args(args)
    except ValueError as e:
        print(f"CHECK-STANDARDS usage error: {e}")
        print("Usage: CHECK-STANDARDS <path> [--config FILE] [--json [FILE]] [--markdown FILE] "
              "[--okf-out DIR] [--from-okf DIR] [--no-defaults] [--verbose]")
        return 2

    from ai_architect.okf import check_conformance, export_bundle, load_bundle
    try:
        if parsed.from_okf:
            loaded = load_bundle(parsed.from_okf)
            config = load_config(Path(parsed.path), Path(parsed.config), not parsed.no_defaults) \
                if parsed.config else loaded["config"]
            report = run_check(None, graph=loaded["graph"], config=config, fact_source="okf-bundle")
        else:
            report = run_check(parsed.path, parsed.config, include_defaults=not parsed.no_defaults)
        if parsed.okf_out:
            bundle = export_bundle(report, parsed.okf_out)
    except (StandardsConfigError, OSError, ValueError) as e:
        print(f"CHECK-STANDARDS failed: {e}")
        return 2

    if parsed.okf_out:
        conformance = check_conformance(str(bundle))
        state = "conformant with OKF v0.2 section 11" if conformance["conformant"] else "NOT conformant"
        print(f"OKF bundle written to {bundle} ({conformance['concepts']} concepts, {state})", file=sys.stderr)
        for err in conformance["errors"]:
            print(f"   ! {err}", file=sys.stderr)
    if parsed.markdown:
        Path(parsed.markdown).write_text(to_markdown(report, parsed.verbose), encoding="utf-8")
        print(f"Markdown report written to {parsed.markdown}", file=sys.stderr)
    if parsed.json == "-":
        print(to_json(report))
    else:
        if parsed.json:
            Path(parsed.json).write_text(to_json(report), encoding="utf-8")
            print(f"JSON report written to {parsed.json}", file=sys.stderr)
        print(to_markdown(report, parsed.verbose))
    return exit_code(report)

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
            user_context=context or "Improve reliability and architectural integrity",
            project_status=status or "Stable"
        )
    
    with open("archai_report.json", "w") as f:
        json.dump(report, f, indent=4)
        
    ConsoleUI.step_header("Audit Findings", f"LLM-assisted audit of {os.path.basename(path)}")
    print("Note: AUDIT findings are generated with an LLM. For deterministic, evidence-backed checks use CHECK-STANDARDS.")
    
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

    if legacy_planning_enabled():
        print(f"\n[FEASIBILITY-DRIVEN SPRINT PLAN] (legacy)")
    for day in (sprint_plan if legacy_planning_enabled() else []):
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
    
    if not sys.stdin.isatty():
        return
    useful = input("\nWas this audit helpful? (y/n): ").lower().strip() == 'y'
    save_feedback(useful, [])
    print("Feedback saved. Thank you!")

def print_help_table():
    print(f"\n{'='*80}")
    print(f"{'COMMAND':<25} | {'DESCRIPTION':<50}")
    print(f"{'-'*25}-+-{'-'*50}")
    print(f"{'CHECK-STANDARDS':<25} | {'Deterministic standards check with cited evidence (no LLM)'}")
    print(f"{'IMPACT':<25} | {'Assess risk (CIRAS) for a file or symbol'}")
    print(f"{'AUDIT':<25} | {'LLM-assisted architectural audit'}")
    print(f"{'GITHUB':<25} | {'Interact with GitHub (CONNECT, PRS, ANALYZE)'}")
    print(f"{'TRACE':<25} | {'Show evidence trail for a specific ticket ID'}")
    print(f"{'EXPLAIN':<25} | {'LLM explanation of a report item (PRIORITY, EFFORT, RISK, DEP)'}")
    print(f"{'G-REASON':<25} | {'LLM reasoning over the extracted dependency graph'}")
    print(f"{'SET-GITHUB-TOKEN':<25} | {'Securely register GitHub Personal Access Token'}")
    print(f"{'SET-PM-TOKEN':<25} | {'Securely register Jira/Trello credentials'}")
    print(f"{'CONFIG':<25} | {'View current configuration and integrations'}")
    print(f"{'HELP':<25} | {'Show this command context table'}")
    print(f"{'EXIT / PHIR-MILTY-HAIN':<25} | {'Terminate the ArchAI console session'}")
    print(f"{'='*80}\n")

def split_command(cmd_line: str) -> List[str]:
    """POSIX shlex treats backslashes as escapes, which mangles Windows paths."""
    if os.name != "nt":
        return shlex.split(cmd_line)
    parts = shlex.split(cmd_line, posix=False)
    return [p[1:-1] if len(p) >= 2 and p[0] == p[-1] and p[0] in "\"'" else p for p in parts]

def process_command(cmd_line) -> Optional[int]:
    """Runs one console command. Accepts a command line string or a list of tokens."""
    try:
        parts = list(cmd_line) if isinstance(cmd_line, (list, tuple)) else split_command(cmd_line)
    except ValueError:
        print("Error: Invalid command syntax.")
        return 2

    if not parts:
        return

    command = parts[0].upper()
    args = parts[1:]

    if command == "CHECK-STANDARDS":
        return check_standards_command(args)

    if command in ("PLAN", "SIMULATE", "RELEASE-CONFIDENCE") and not legacy_planning_enabled():
        print(f"{command} is deferred: sprint planning and estimation are no longer part of ArchAI's "
              "product direction. The code is kept; set ARCHAI_ENABLE_LEGACY_PLANNING=1 to use it.")
        return 2

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
        st = session_status()
        on = lambda flag: "connected" if flag else "not configured"
        print("\n[CURRENT CONFIGURATION]")
        print(f" Identity: {st['identity']} ({st['identity_source']})")
        print(f" Access mode: {st['access_mode']} | Flags: {', '.join(st['flags']) or 'none'} | Profile: {st['profile']}")
        print(f" License: {license_text(st['license'])}")
        print(f" LLM: {st['llm']}")
        print(f" GitHub: {on(st['integrations']['github'])} | Jira: {on(st['integrations']['jira'])} | "
              f"Google Drive: {on(st['integrations']['google_drive'])}")
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
    st = session_status()
    mode = st["access_mode"] + "".join(f" + {flag}" for flag in st["flags"])
    print(f"{'='*80}")
    print(f" IDENTITY: {st['identity']} ({st['identity_source']})")
    print(f" MODE: {mode} | PROFILE: {st['profile']} | VERSION: {ARCHAI_VERSION}")
    print(f" LICENSE: {license_text(st['license'])}")
    print(f" INTEGRITY: {get_graph_core_hash()}")
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
    # Banner box-drawing and emoji crash on legacy Windows code pages (e.g. when piped).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(prog="ai-architect", description="ArchAI Deterministic Adjudication CLI")
    parser.add_argument("--license", type=str, help="Apply a pilot license token")
    parser.add_argument("--check-token", type=str, help="Verify the status of a specific token")
    parser.add_argument("--version", action="store_true", help="Display version and core hash")
    parser.add_argument("--test-mode", action="store_true", help="Set the DEMO flag (ARCHAI_TEST_MODE=1)")
    
    args, unknown = parser.parse_known_args()
    
    if args.version:
        print(f"ArchAI Version: {ARCHAI_VERSION}")
        print(f"Graph Core Integrity: {get_graph_core_hash()}")
        return

    if args.check_token:
        print(LicenseManager.get_token_info(args.check_token))
        return

    if args.license:
        try:
            LicenseManager.validate_token(args.license)
            os.environ["ARCHAI_LICENSE"] = args.license
            print("✅ License token accepted for this session.")
        except ValueError as e:
            print(f"❌ {str(e)}")
            return

    # Enforcement Gate: a token must actually validate, not merely be present
    # (or ARCHAI_DEV_MODE must be set for local development).
    lic = LicenseManager.inspect_token(os.environ.get("ARCHAI_LICENSE"))
    if lic["state"] != "VALID" and not os.environ.get("ARCHAI_DEV_MODE"):
        print(f"\n[SECURITY ALERT] License {lic['state']}: {lic['reason']}")
        print("Contact the pilot admin for a renewal token.")
        print("Usage: ai-architect --license <TOKEN>\n")
        sys.exit(3)

    if args.test_mode:
        print("\n[DEMO FLAG SET] ARCHAI_TEST_MODE=1 (no mock data is loaded yet).")
        os.environ["ARCHAI_TEST_MODE"] = "1"

    if unknown:
        # One-shot mode: ai-architect CHECK-STANDARDS . --json report.json
        sys.exit(process_command(unknown) or 0)

    run_interactive_console()

if __name__ == "__main__":
    run_cli()

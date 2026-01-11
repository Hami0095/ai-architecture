import os
import json
import ollama
import logging
from pathlib import Path
from .prompts import (
    DISCOVERY_SYSTEM_PROMPT, 
    GAP_ANALYSIS_SYSTEM_PROMPT, 
    TICKET_GENERATION_SYSTEM_PROMPT,
    CONTEXT_BUILDER_SYSTEM_PROMPT,
    AUDITOR_VERIFIER_SYSTEM_PROMPT,
    PATH_NAVIGATOR_SYSTEM_PROMPT
)

logger = logging.getLogger("ArchAI.Auditor")

class ArchitecturalAuditor:
    def __init__(self, model="qwen3-coder:480b-cloud"):
        self.model = model

    def scan_directory(self, root_path, max_depth=4) -> str:
        """
        Creates a text representation of the project structure and key file contents.
        Uses pathlib for cross-platform (Windows/Mac/Ubuntu) stability.
        """
        # Expand user path (~) if present and resolve
        root = Path(root_path).expanduser().resolve()
        if not root.exists():
            logger.error(f"Directory not found: {root}")
            return f"Error: Directory {root} does not exist."

        summary = f"Project Root: {root}\nStructure:\n"
        ignore_dirs = {'.git', '__pycache__', '.venv', 'venv', 'env', 'node_modules', 'dist', 'build', '.idea', '.vscode'}
        relevant_extensions = {'.py', '.md', '.sql', '.yaml', '.yml', '.json', '.toml', '.env', 'Dockerfile', '.js', '.ts'}
        
        file_contents = ""
        files_scanned = 0
        
        # Helper to get depth relative to root
        def get_depth(p: Path):
            try:
                return len(p.relative_to(root).parts)
            except:
                return 0

        for path in root.rglob('*'):
            # Skip ignored directories
            if any(part in ignore_dirs for part in path.parts):
                continue
            
            depth = get_depth(path)
            if depth > max_depth:
                continue

            indent = ' ' * 4 * (depth - 1)
            
            if path.is_dir():
                summary += f"{indent}{path.name}/\n"
            else:
                ext = path.suffix.lower()
                if ext in relevant_extensions or path.name in relevant_extensions:
                    summary += f"{indent}{path.name}\n"
                    files_scanned += 1
                    try:
                        # Only read specific text-based formats for context
                        if ext in {'.py', '.sql', '.yaml', '.yml', '.toml', '.env', '.js', '.ts'} or path.name == 'Dockerfile':
                            with open(path, 'r', encoding='utf-8', errors='ignore') as file_obj:
                                content = file_obj.read()
                                if len(content) > 1500:
                                    content = content[:1000] + "\n...[TRUNCATED]...\n" + content[-500:]
                                rel_path = path.relative_to(root)
                                file_contents += f"--- FILE: {rel_path} ---\n{content}\n\n"
                    except Exception as e:
                        logger.warning(f"Failed to read {path}: {e}")

        logger.info(f"Scan complete. {files_scanned} files included in analysis context.")
        return summary + f"\n\nTotal Files Scanned: {files_scanned}\n\nKey File Contents:\n" + file_contents

    def _call_llm_json(self, system_prompt: str, user_prompt: str) -> dict:
        try:
            response = ollama.chat(model=self.model, format='json', messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ])
            content = response['message']['content']
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            return json.loads(content)
        except Exception as e:
            logger.error(f"LLM JSON Error: {e}")
            return {}

    def _call_llm_text(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = ollama.chat(model=self.model, messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ])
            return response['message']['content']
        except Exception as e:
            logger.error(f"LLM Text Error: {e}")
            return "Analysis failed."

    # --- Agent Implementations ---

    def PathNavigator(self, user_input_path: str) -> dict:
        """Agent 0: Resolves the user's input path to a safe absolute path."""
        import platform
        home_dir = str(Path.home())
        cwd = os.getcwd()
        os_name = platform.system()
        
        prompt = PATH_NAVIGATOR_SYSTEM_PROMPT.format(
            user_input=user_input_path,
            home_dir=home_dir,
            cwd=cwd,
            os_name=os_name
        )
        
        result = self._call_llm_json("You are an ArchAI Path Navigator.", prompt)
        
        # Validation as secondary check
        resolved = result.get("resolved_path", user_input_path)
        final_path = Path(resolved).expanduser().resolve()
        
        if not final_path.exists():
            # If not exists, try to be smarter (e.g. check if it's in home)
            if not Path(resolved).is_absolute():
                 potential = Path.home() / resolved
                 if potential.exists():
                      final_path = potential
        
        result["resolved_path"] = str(final_path)
        logger.info(f"PathNavigator resolved '{user_input_path}' to '{final_path}'")
        return result

    def Discovery(self, repo_path: str) -> dict:
        """Agent 1: Scans the repository and returns technical metadata."""
        code_structure = self.scan_directory(repo_path)
        discovery = self._call_llm_json(DISCOVERY_SYSTEM_PROMPT, f"Project Path: {repo_path}\n\nCode Structure:\n{code_structure}")
        
        # Fallback heuristic
        if not discovery.get("languages"):
            discovery["languages"] = []
            if ".py" in code_structure: discovery["languages"].append("python")
            if ".js" in code_structure: discovery["languages"].append("javascript")
        
        discovery.setdefault("frameworks", [])
        discovery.setdefault("architecture_type", "Unknown")
        discovery["_raw_structure"] = code_structure # Carry forward for ContextBuilder
        logger.info(f"Discovery detected languages: {discovery.get('languages')}")
        return discovery

    def ContextBuilder(self, discovery_result: dict) -> dict:
        """Agent 2: Analyzes discovery data to build a dependency/relationship graph."""
        raw_structure = discovery_result.get("_raw_structure", "")
        # Clean up for LLM context
        metadata = {k:v for k,v in discovery_result.items() if k != '_raw_structure'}
        msg = f"Metadata: {json.dumps(metadata)}\nStructure Snippet: {raw_structure[:2000]}"
        return self._call_llm_json(CONTEXT_BUILDER_SYSTEM_PROMPT, msg)

    def GapAnalyzer(self, context_graph: dict, goals: dict) -> dict:
        """Agent 3: Compares context against goals to identify missing gaps."""
        gap_prompt = GAP_ANALYSIS_SYSTEM_PROMPT.format(
            discovery_data=json.dumps(context_graph),
            user_context=goals.get("user_context", ""),
            project_status=goals.get("project_status", ""),
            expected_output=goals.get("expected_output", "")
        )
        report_text = self._call_llm_text("You are an ArchAI Gap Analyzer.", gap_prompt)
        return {"markdown_report": report_text}

    def TicketGenerator(self, gap_report: dict) -> dict:
        """Agent 4: Generates actionable dev tickets from the gap report."""
        prompt = f"Gap Report: {gap_report.get('markdown_report')}\nGenerate detailed tickets."
        return self._call_llm_json(TICKET_GENERATION_SYSTEM_PROMPT, prompt)

    def Planner(self, tickets_list_raw: list) -> list:
        """Agent 5: Creates a 5-day sprint plan."""
        from ..data.models import AuditTicket
        from ..improvement_engine.planner import SprintPlanner
        
        valid_tickets = []
        for t in tickets_list_raw:
            if isinstance(t, dict):
                t.setdefault("title", "Proposed Improvement")
                t.setdefault("type", "Logic")
                t.setdefault("severity", "Medium")
                t.setdefault("priority", "Medium")
                t.setdefault("effort_hours", 2)
                try:
                    valid_tickets.append(AuditTicket(**t))
                except Exception as e:
                    logger.debug(f"Invalid ticket data: {e}")
        
        planner = SprintPlanner(hours_per_day=5.0, total_days=5)
        sprint_days = planner.plan_sprint(valid_tickets)
        return [day.model_dump(mode='json') for day in sprint_days]

    def AuditorVerifier(self, sprint_plan: list) -> dict:
        """Agent 6: Verifies the sprint plan for risks and quality."""
        prompt = f"Proposed Sprint Plan: {json.dumps(sprint_plan)}\nVerify for risks."
        return self._call_llm_json(AUDITOR_VERIFIER_SYSTEM_PROMPT, prompt)

    def audit_project(self, root_path: str, user_context: str = "", project_status: str = "", expected_output: str = "") -> dict:
        """
        Legacy wrapper for audit_project, now using the Orchestrator.
        """
        from .orchestrator import Orchestrator
        goals = {
            "user_context": user_context,
            "project_status": project_status,
            "expected_output": expected_output
        }
        orchestrator = Orchestrator(self)
        return orchestrator.run_pipeline(root_path, goals)

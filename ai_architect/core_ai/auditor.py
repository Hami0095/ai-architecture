import os
import json
import logging
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from .prompts import (
    DISCOVERY_SYSTEM_PROMPT, 
    GAP_ANALYSIS_SYSTEM_PROMPT, 
    TICKET_GENERATION_SYSTEM_PROMPT,
    CONTEXT_BUILDER_SYSTEM_PROMPT,
    AUDITOR_VERIFIER_SYSTEM_PROMPT,
    PATH_NAVIGATOR_SYSTEM_PROMPT
)
from ..data.models import (
    PathNavigatorOutput,
    DiscoveryOutput,
    ContextBuilderOutput,
    GapAnalyzerOutput,
    TicketGeneratorOutput,
    PlannerOutput,
    AuditorVerifierOutput,
    AuditTicket
)
from ..models.base import BaseAIModel
from ..models.factory import get_model
from ..infrastructure.caching import cache

logger = logging.getLogger("ArchAI.Auditor")

class ArchitecturalAuditor:
    def __init__(self, model: Optional[BaseAIModel] = None):
        self.model = model or get_model()

    def scan_directory(self, root_path, max_depth=4) -> str:
        """
        Creates a text representation of the project structure and key file contents.
        Uses caching to avoid rescanning unchanged directories (simple path-based cache).
        """
        root = Path(root_path).expanduser().resolve()
        cache_key = f"scan:{root}:{max_depth}"
        cached_summary = cache.get("scanner", cache_key)
        
        # Note: In a real system, we'd check file mtimes or hashes to invalidate.
        # For now, we assume if it's cached, it's valid for the TTL duration.
        if cached_summary:
            logger.info(f"Using cached file scan for {root}")
            return cached_summary

        if not root.exists():
            logger.error(f"Directory not found: {root}")
            return f"Error: Directory {root} does not exist."

        summary = f"Project Root: {root}\nStructure:\n"
        ignore_dirs = {'.git', '__pycache__', '.venv', 'venv', 'env', 'node_modules', 'dist', 'build', '.idea', '.vscode'}
        relevant_extensions = {'.py', '.md', '.sql', '.yaml', '.yml', '.json', '.toml', '.env', 'Dockerfile', '.js', '.ts'}
        
        file_contents = ""
        files_scanned = 0
        
        def get_depth(p: Path):
            try:
                return len(p.relative_to(root).parts)
            except:
                return 0

        for path in root.rglob('*'):
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
                        if ext in {'.py', '.sql', '.yaml', '.yml', '.toml', '.env', '.js', '.ts'} or path.name == 'Dockerfile':
                            with open(path, 'r', encoding='utf-8', errors='ignore') as file_obj:
                                content = file_obj.read()
                                if len(content) > 1500:
                                    content = content[:1000] + "\n...[TRUNCATED]...\n" + content[-500:]
                                rel_path = path.relative_to(root)
                                file_contents += f"--- FILE: {rel_path} ---\n{content}\n\n"
                    except Exception as e:
                        logger.warning(f"Failed to read {path}: {e}")

        final_result = summary + f"\n\nTotal Files Scanned: {files_scanned}\n\nKey File Contents:\n" + file_contents
        logger.info(f"Scan complete. {files_scanned} files included in analysis context.")
        
        # Cache the result
        cache.set("scanner", cache_key, final_result, ttl=300) # 5 minutes cache for scans
        return final_result

    def _call_llm_json(self, system_prompt: str, user_prompt: str, retries: int = 2) -> dict:
        # Check cache for identical prompts (useful for repetitive development runs)
        cache_key = {"sys": system_prompt, "usr": user_prompt, "model": getattr(self.model, "model_name", "unknown")}
        cached_response = cache.get("llm_json", cache_key)
        if cached_response:
            return cached_response

        for attempt in range(retries + 1):
            try:
                content = self.model.chat(
                    messages=[
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt}
                    ],
                    format='json'
                )
                result = json.loads(content)
                cache.set("llm_json", cache_key, result, ttl=3600) # 1 hour cache
                return result
            except Exception as e:
                logger.warning(f"LLM JSON Error (Attempt {attempt+1}/{retries+1}): {e}")
                if attempt == retries:
                    logger.error("LLM JSON calls failed after all retries.")
                    return {}
                time.sleep(1)
        return {}

    def _call_llm_text(self, system_prompt: str, user_prompt: str) -> str:
        cache_key = {"sys": system_prompt, "usr": user_prompt, "model": getattr(self.model, "model_name", "unknown")}
        cached_response = cache.get("llm_text", cache_key)
        if cached_response:
            return cached_response

        try:
            result = self.model.chat(
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ]
            )
            cache.set("llm_text", cache_key, result, ttl=3600)
            return result
        except Exception as e:
            logger.error(f"LLM Text Error: {e}")
            return "Analysis failed."

    # --- Agent Implementations ---

    def PathNavigator(self, user_input_path: str) -> PathNavigatorOutput:
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
        
        raw_result = self._call_llm_json("You are an ArchAI Path Navigator.", prompt)
        resolved = raw_result.get("resolved_path", user_input_path)
        final_path = Path(resolved).expanduser().resolve()
        
        if not final_path.exists():
            if not Path(resolved).is_absolute():
                 potential = Path.home() / resolved
                 if potential.exists():
                      final_path = potential
        
        output = PathNavigatorOutput(
            resolved_path=str(final_path),
            exists_hint=final_path.exists(),
            rationale=raw_result.get("rationale", "Resolved via fallback logic")
        )
        logger.info(f"PathNavigator resolved '{user_input_path}' to '{final_path}'")
        return output

    def Discovery(self, repo_path: str) -> DiscoveryOutput:
        code_structure = self.scan_directory(repo_path)
        raw_discovery = self._call_llm_json(DISCOVERY_SYSTEM_PROMPT, f"Project Path: {repo_path}\n\nCode Structure:\n{code_structure}")
        
        languages = raw_discovery.get("languages", [])
        if not languages:
            if ".py" in code_structure: languages.append("python")
            if ".js" in code_structure: languages.append("javascript")
            if ".ts" in code_structure: languages.append("typescript")
        
        output = DiscoveryOutput(
            languages=languages,
            frameworks=raw_discovery.get("frameworks", []),
            architecture_type=raw_discovery.get("architecture_type", "Unknown"),
            module_summary=raw_discovery.get("module_summary", {}),
            raw_structure=code_structure
        )
        logger.info(f"Discovery detected languages: {output.languages}")
        return output

    def ContextBuilder(self, discovery_result: DiscoveryOutput) -> ContextBuilderOutput:
        raw_structure = discovery_result.raw_structure or ""
        metadata = discovery_result.model_dump(exclude={'raw_structure'})
        msg = f"Metadata: {json.dumps(metadata)}\nStructure Snippet: {raw_structure[:2000]}"
        raw_result = self._call_llm_json(CONTEXT_BUILDER_SYSTEM_PROMPT, msg)
        
        return ContextBuilderOutput(
            dependencies=raw_result.get("dependencies", []),
            patterns=raw_result.get("patterns", []),
            critical_paths=raw_result.get("critical_paths", [])
        )

    def GapAnalyzer(self, context_graph: ContextBuilderOutput, goals: dict) -> GapAnalyzerOutput:
        gap_prompt = GAP_ANALYSIS_SYSTEM_PROMPT.format(
            discovery_data=context_graph.model_dump_json(),
            user_context=goals.get("user_context", ""),
            project_status=goals.get("project_status", ""),
            expected_output=goals.get("expected_output", "")
        )
        report_text = self._call_llm_text("You are an ArchAI Gap Analyzer.", gap_prompt)
        return GapAnalyzerOutput(markdown_report=report_text)

    def TicketGenerator(self, gap_report: GapAnalyzerOutput) -> TicketGeneratorOutput:
        prompt = f"Gap Report: {gap_report.markdown_report}\nGenerate detailed tickets."
        raw_result = self._call_llm_json(TICKET_GENERATION_SYSTEM_PROMPT, prompt)
        
        tickets_raw = raw_result.get("tickets", [])
        valid_tickets = []
        for t in tickets_raw:
            try:
                valid_tickets.append(AuditTicket(**t))
            except Exception as e:
                logger.debug(f"Skipping malformed ticket: {e}")
        
        return TicketGeneratorOutput(tickets=valid_tickets)

    def Planner(self, tickets_list: List[AuditTicket]) -> PlannerOutput:
        from ..improvement_engine.planner import SprintPlanner
        planner = SprintPlanner(hours_per_day=5.0, total_days=5)
        sprint_days = planner.plan_sprint(tickets_list)
        return PlannerOutput(sprint_plan=sprint_days)

    def AuditorVerifier(self, sprint_plan: List[Dict[str, Any]]) -> AuditorVerifierOutput:
        prompt = f"Proposed Sprint Plan: {json.dumps(sprint_plan)}\nVerify for risks."
        raw_result = self._call_llm_json(AUDITOR_VERIFIER_SYSTEM_PROMPT, prompt)
        
        return AuditorVerifierOutput(
            findings=raw_result.get("findings", []),
            summary=raw_result.get("summary", "Verification complete.")
        )

    async def audit_project(self, root_path: str, user_context: str = "", project_status: str = "", expected_output: str = "") -> dict:
        from .orchestrator import Orchestrator
        goals = {
            "user_context": user_context,
            "project_status": project_status,
            "expected_output": expected_output
        }
        orchestrator = Orchestrator(self)
        return await orchestrator.run_pipeline(root_path, goals)

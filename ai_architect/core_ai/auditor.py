import os
import json
import logging
import time
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from .prompts import (
    DISCOVERY_SYSTEM_PROMPT, 
    GAP_ANALYSIS_SYSTEM_PROMPT, 
    TICKET_GENERATION_SYSTEM_PROMPT,
    CONTEXT_BUILDER_SYSTEM_PROMPT,
    AUDITOR_VERIFIER_SYSTEM_PROMPT,
    PATH_NAVIGATOR_SYSTEM_PROMPT,
    CIRAS_SYSTEM_PROMPT,
    WDP_SYSTEM_PROMPT,
    SRC_SYSTEM_PROMPT
)
from ..data.models import (
    PathNavigatorOutput,
    DiscoveryOutput,
    ContextBuilderOutput,
    GapAnalyzerOutput,
    TicketGeneratorOutput,
    PlannerOutput,
    AuditorVerifierOutput,
    AuditTicket,
    Evidence,
    ImpactAssessment,
    WDPOutput,
    SprintPlanConfig,
    SRCOutput,
    TaskPrediction
)
from ..models.base import BaseAIModel
from ..models.factory import get_model
from ..infrastructure.caching import cache

logger = logging.getLogger("ArchAI.Auditor")

class ArchitecturalAuditor:
    def __init__(self, model: Optional[BaseAIModel] = None):
        self.model = model or get_model()

    def _locate_symbol(self, root: Path, symbol: str) -> Optional[str]:
        """Scans the codebase for the definition of a symbol (class or function)."""
        ignore_dirs = {'.git', '__pycache__', '.venv', 'venv', 'env', 'node_modules', 'dist', 'build'}
        for path in root.rglob("*.py"):
            if any(part in ignore_dirs for part in path.parts): continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                # Regex to find 'class Symbol' or 'def Symbol'
                if re.search(fr"^\s*(class|def)\s+{re.escape(symbol)}\b", content, re.MULTILINE):
                    return str(path)
            except: pass
        return None

    def scan_directory(self, root_path, max_depth=4) -> str:
        root = Path(root_path).expanduser().resolve()
        cache_key = f"scan:{root}:{max_depth}"
        cached_summary = cache.get("scanner", cache_key)
        if cached_summary: return cached_summary
        if not root.exists(): return f"Error: Directory {root} does not exist."

        summary = f"Project Root: {root}\nStructure:\n"
        ignore_dirs = {'.git', '__pycache__', '.venv', 'venv', 'env', 'node_modules', 'dist', 'build'}
        relevant_extensions = {'.py', '.md', '.sql', '.yaml', '.yml', '.json', '.toml', '.env', 'Dockerfile'}
        file_contents = ""
        files_scanned = 0
        for path in root.rglob('*'):
            if any(part in ignore_dirs for part in path.parts): continue
            try: depth = len(path.relative_to(root).parts)
            except: depth = 0
            if depth > max_depth: continue
            indent = ' ' * 4 * (depth - 1)
            if path.is_dir():
                summary += f"{indent}{path.name}/\n"
            else:
                if path.suffix.lower() in relevant_extensions or path.name in relevant_extensions:
                    summary += f"{indent}{path.name}\n"
                    files_scanned += 1
                    try:
                        if path.suffix.lower() in {'.py', '.yaml', '.toml'} or path.name in {'Dockerfile'}:
                            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                if len(content) > 1000: content = content[:700] + "\n...[TRUNCATED]...\n" + content[-300:]
                                file_contents += f"--- FILE: {path.relative_to(root)} ---\n{content}\n\n"
                    except: pass
        final_result = summary + f"\n\nTotal Files Scanned: {files_scanned}\n\nContents:\n" + file_contents
        cache.set("scanner", cache_key, final_result, ttl=300)
        return final_result

    def _call_llm_json(self, system_prompt: str, user_prompt: str, retries: int = 2) -> dict:
        for attempt in range(retries + 1):
            try:
                content = self.model.chat(messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}], format='json')
                if not content: raise ValueError("Empty response")
                clean = re.sub(r'```json\n?|\n?```', '', content).strip()
                start = clean.find('{')
                if start == -1: raise ValueError("No JSON object")
                decoder = json.JSONDecoder()
                obj, index = decoder.raw_decode(clean[start:])
                return obj
            except Exception as e:
                logger.warning(f"LLM JSON fail (Attempt {attempt+1}): {e}")
                if attempt == retries: return {}
                time.sleep(1)
        return {}

    def PathNavigator(self, user_input_path: str) -> PathNavigatorOutput:
        from pathlib import Path
        import platform
        prompt = PATH_NAVIGATOR_SYSTEM_PROMPT.format(user_input=user_input_path, home_dir=str(Path.home()), cwd=os.getcwd(), os_name=platform.system())
        raw = self._call_llm_json(PATH_NAVIGATOR_SYSTEM_PROMPT, prompt)
        res_path = raw.get("resolved_path", user_input_path)
        final_path = Path(res_path).expanduser().resolve()
        return PathNavigatorOutput(resolved_path=str(final_path), exists_hint=final_path.exists(), rationale=raw.get("rationale", "Resolved"))

    def Discovery(self, repo_path: str) -> DiscoveryOutput:
        from ..analysis.graph_engine import GraphEngine
        engine = GraphEngine(Path(repo_path))
        engine.analyze_project()
        arch_graph = engine.get_graph_summary()
        structure = self.scan_directory(repo_path)
        prompt = f"Project: {repo_path}\nGraph Summary: {json.dumps(arch_graph.get('layer_stats', {}))}\nStructure:\n{structure[:4000]}"
        raw = self._call_llm_json(DISCOVERY_SYSTEM_PROMPT, prompt)
        return DiscoveryOutput(languages=raw.get("languages", ["python"]), frameworks=raw.get("frameworks", []), architecture_type=raw.get("architecture_type", "Unknown"), module_summary=raw.get("module_summary", {}), raw_structure=structure, architecture_graph=arch_graph)

    def ContextBuilder(self, discovery_result: DiscoveryOutput) -> ContextBuilderOutput:
        arch_graph = discovery_result.architecture_graph or {}
        msg = f"Relationships: {json.dumps(arch_graph.get('relationships', []))}"
        raw = self._call_llm_json(CONTEXT_BUILDER_SYSTEM_PROMPT, msg)
        return ContextBuilderOutput(dependencies=raw.get("dependencies", []), patterns=raw.get("patterns", []), critical_paths=raw.get("critical_paths", []))

    def GapAnalyzer(self, input_data: dict, goals: dict) -> GapAnalyzerOutput:
        gap_prompt = GAP_ANALYSIS_SYSTEM_PROMPT.format(discovery_data=json.dumps(input_data), user_context=goals.get("user_context", ""), project_status=goals.get("project_status", ""))
        raw = self._call_llm_json(GAP_ANALYSIS_SYSTEM_PROMPT, gap_prompt)
        evidence = []
        for e in raw.get("evidence_trail", []):
            try: evidence.append(Evidence(**e))
            except: pass
        return GapAnalyzerOutput(markdown_report=raw.get("markdown_report", "Fail"), evidence_trail=evidence)

    def TicketGenerator(self, gap_report: GapAnalyzerOutput) -> TicketGeneratorOutput:
        prompt = f"Gaps: {gap_report.markdown_report[:4000]}\nEvidence: {json.dumps([e.model_dump() for e in gap_report.evidence_trail])}"
        raw = self._call_llm_json(TICKET_GENERATION_SYSTEM_PROMPT, prompt)
        tickets = []
        for t in raw.get("tickets", []):
            try: tickets.append(AuditTicket(**t))
            except: pass
        return TicketGeneratorOutput(tickets=tickets)

    def Planner(self, tickets_list: List[AuditTicket]) -> PlannerOutput:
        from ..improvement_engine.planner import SprintPlanner
        planner = SprintPlanner(hours_per_day=6.0, total_days=5)
        sprint_days = planner.plan_sprint(tickets_list)
        for day in sprint_days:
            risk_score = 0
            for t in day.tickets:
                if "high-risk" in t.risk_flags or "high-churn" in t.risk_flags:
                    risk_score += 3
                if "deep-dependency" in t.risk_flags:
                    risk_score += 2
                if t.evidence and t.evidence.confidence < 0.7:
                    risk_score += 2
                
            if day.total_hours > 7.0:
                day.feasibility = "Will overflow"
            elif risk_score >= 5 or day.total_hours > 5.5:
                day.feasibility = "High risk"
            else:
                day.feasibility = "Likely fits"
        return PlannerOutput(sprint_plan=sprint_days)

    def AuditorVerifier(self, sprint_plan: List[Dict[str, Any]]) -> AuditorVerifierOutput:
        raw = self._call_llm_json(AUDITOR_VERIFIER_SYSTEM_PROMPT, f"Review: {json.dumps(sprint_plan)[:4000]}")
        return AuditorVerifierOutput(findings=raw.get("findings", []), summary=raw.get("summary", "Complete"))

    async def audit_project(self, root_path: str, user_context: str = "", project_status: str = "") -> dict:
        from .orchestrator import Orchestrator
        goals = {"user_context": user_context, "project_status": project_status}
        orchestrator = Orchestrator(self)
        return await orchestrator.run_pipeline(root_path, goals)

    def ImpactAnalyzer(self, root_path: str, target: str, max_depth: int = 3) -> ImpactAssessment:
        from ..analysis.graph_engine import GraphEngine
        root = Path(root_path).resolve()
        
        # 0. Symbol Discovery (User-Requested "Get-Children" Logic)
        location_hint = ""
        resolved_target = target
        if not (root / target).exists() and not target.endswith(".py"):
            loc = self._locate_symbol(root, target)
            if loc:
                rel_loc = Path(loc).relative_to(root)
                location_hint = f" (Found in: {rel_loc})"
                logger.info(f"Resolved symbol '{target}' to {rel_loc}")
                # Optional: You could update resolved_target to be the file path if GraphEngine supports it better
                # resolved_target = str(rel_loc) 
        
        engine = GraphEngine(root)
        engine.analyze_project()
        
        # 1. Structural Signals
        impact_scope = engine.get_impact_scope(target, max_depth=max_depth)
        metrics = engine.get_symbol_metrics(target)
        
        # 2. Historical Signals (churn)
        churn = metrics.get('churn', 0)
        
        # 3. Signals Preparation
        signals = {
            "impact_scope": impact_scope,
            "fan_in": metrics.get('fan_in'),
            "fan_out": metrics.get('fan_out'),
            "depth": metrics.get('depth'),
            "churn": churn,
            "insufficient_tests": metrics.get('depth', 0) > 3
        }
        
        # 4. Call LLM for final reasoning
        prompt = CIRAS_SYSTEM_PROMPT.format(
            target=f"{target}{location_hint}",
            structural_signals=json.dumps({k: signals[k] for k in ["impact_scope", "fan_in", "fan_out", "depth"]}),
            historical_signals=json.dumps({"churn": signals["churn"]}),
            quality_signals=json.dumps({"insufficient_tests": signals["insufficient_tests"]})
        )
        
        raw = self._call_llm_json("You are the ArchAI Risk Evaluation Agent (CIRAS).", prompt)
        
        if not raw or raw.get('insufficient_data'):
            return ImpactAssessment(
                target=target, risk_level="UNKNOWN", risk_score=0.0, 
                confidence_score=0.0, insufficient_data=True, 
                rationale=f"LLM returned insufficient data or analysis failed. Signals: {json.dumps(signals)}"
            )
            
        return ImpactAssessment(**raw)

    def WDPPlanner(self, root_path: str, goal: str, sprint_config: SprintPlanConfig = SprintPlanConfig()) -> WDPOutput:
        from ..analysis.graph_engine import GraphEngine
        engine = GraphEngine(Path(root_path))
        engine.analyze_project()
        arch_graph = engine.get_graph_summary()
        
        # 1. Get Impact Analysis for the Goal
        # We fuzzy match the goal to a module if possible
        impact = self.ImpactAnalyzer(root_path, goal)
        
        # 2. Get Historical Context (Aggregated churn)
        metrics = {
            "avg_churn": sum(n['complexity_metrics']['churn'] for n in arch_graph['modules'].values()) / max(1, len(arch_graph['modules'])),
            "high_risk_modules": [name for name, m in arch_graph['modules'].items() if m['complexity_metrics']['churn'] > 10 or m['complexity_metrics']['dependency_depth'] > 5]
        }
        
        # 3. Call LLM to generate Tasks
        prompt = WDP_SYSTEM_PROMPT.format(
            goal=goal,
            arch_graph=json.dumps(arch_graph.get('layer_stats', {})),
            impact_assessment=impact.model_dump_json(),
            metrics=json.dumps(metrics),
            sprint_config=sprint_config.model_dump_json()
        )
        
        raw = self._call_llm_json("You are WDP-TG, the ArchAI Task Generation Engine.", prompt)
        
        if not raw:
            return WDPOutput(
                epics=[], 
                sprint_feasibility={"status": "UNKNOWN", "rationale": "Failed to generate plan.", "bottlenecks": []},
                overall_confidence=0.0,
                assumptions=["LLM failed to return valid JSON"]
            )
            
        return WDPOutput(**raw)

    def SRCEngine(self, root_path: str, goal: str, wdp_plan: WDPOutput, sprint_config: SprintPlanConfig = SprintPlanConfig(), strict: bool = False) -> SRCOutput:
        from ..analysis.graph_engine import GraphEngine
        engine = GraphEngine(Path(root_path))
        engine.analyze_project()
        arch_graph = engine.get_graph_summary()
        
        # 1. Get Impact Analysis for the Goal
        impact = self.ImpactAnalyzer(root_path, goal)
        
        # 2. Extract metrics
        metrics = {
             "avg_churn": sum(n['complexity_metrics']['churn'] for n in arch_graph['modules'].values()) / max(1, len(arch_graph['modules'])),
             "high_risk_modules": [name for name, m in arch_graph['modules'].items() if m['complexity_metrics']['churn'] > 10]
        }
        
        # 3. Call LLM to Simulate
        prompt = SRC_SYSTEM_PROMPT.format(
            goal=goal,
            wdp_plan=wdp_plan.model_dump_json(),
            ciras_data=impact.model_dump_json(),
            team_context=sprint_config.model_dump_json(),
            metrics=json.dumps(metrics)
        )
        
        system_msg = "You are SRC-RS, the ArchAI Sprint Confidence Engine."
        if strict:
            system_msg += " STRICT MODE: Treat all UNKNOWN risks as CRITICAL."

        raw = self._call_llm_json(system_msg, prompt)
        
        if not raw:
            return SRCOutput(
                sprint_goal=goal,
                confidence_score=0.0,
                status="Low Confidence",
                task_predictions=[],
                epic_forecasts=[],
                risk_summary={"critical": [], "high": [], "medium": []},
                recommendations=[],
                bottlenecks=["Simulation aborted: LLM failure"],
                confidence_rationale="Analysis failed to complete."
            )
            
        return SRCOutput(**raw)

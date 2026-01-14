import json
import time
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel
from ..data.models import (
    AgentState, 
    AgentResponse,
    PathNavigatorOutput,
    DiscoveryOutput,
    ContextBuilderOutput,
    GapAnalyzerOutput,
    TicketGeneratorOutput,
    PlannerOutput,
    AuditorVerifierOutput
)
from ..improvement_engine.analyzer import ProactiveStabilityAnalyzer
from ..infrastructure.logging_utils import logger
from ..infrastructure.persistence import PersistenceLayer
from ..models.factory import get_model

class Orchestrator:
    def __init__(self, auditor_instance):
        self.auditor = auditor_instance
        self.logger = logger
        self.state: Optional[AgentState] = None
        self.model = getattr(auditor_instance, 'model', get_model())
        self.stability_analyzer = ProactiveStabilityAnalyzer(model=self.model)
        self.persistence = PersistenceLayer()

    async def _execute_agent(self, agent_name: str, func, *args, **kwargs) -> bool:
        start_time = time.time()
        self.logger.info(f"--- [Agent START] {agent_name} ---")
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            latency = (time.time() - start_time) * 1000
            if result is None: raise ValueError(f"Agent {agent_name} returned None.")
            data_dict = result.model_dump() if hasattr(result, "model_dump") else result
            response = AgentResponse(agent_name=agent_name, success=True, data=data_dict, latency_ms=latency)
            self.state.history.append(response)
            self.persistence.save_metric(agent_name, latency, True)
            self.logger.info(f"--- [Agent DONE] {agent_name} (Success, Latency: {latency:.2f}ms) ---")
            return True
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            self.logger.error(f"Agent {agent_name} CRITICAL FAILURE: {e}")
            response = AgentResponse(agent_name=agent_name, success=False, data={}, error=str(e), latency_ms=latency)
            self.state.history.append(response)
            self.persistence.save_metric(agent_name, latency, False)
            return False

    async def run_pipeline(self, repo_path: str, goals: Dict[str, Any]) -> Dict[str, Any]:
        self.state = AgentState(repo_path=repo_path, goals=goals)
        self.logger.info(f"Starting Orchestration pipeline for: {repo_path}")
        
        # 0. Path Navigator
        if not await self._execute_agent("PathNavigator", self.auditor.PathNavigator, repo_path):
            return {"error": "Path navigation failed."}
        nav_data = PathNavigatorOutput(**self.state.get_last_data("PathNavigator"))
        resolved_path = nav_data.resolved_path

        if not nav_data.exists_hint:
            print("The specified directory does not exist. Please verify and re-enter the correct path.")
        
        # 1. Context Acquisition
        if not await self._execute_agent("ContextAcquisition", self.auditor.Discovery, resolved_path):
            return {"error": "Context acquisition failed."}
        discovery_data = DiscoveryOutput(**self.state.get_last_data("ContextAcquisition"))

        # 2. Structural Analysis
        if not await self._execute_agent("StructuralAnalysis", self.auditor.ContextBuilder, discovery_data):
            return {"error": "Structural analysis failed."}
        
        # 3. Risk Evaluation
        context_data = ContextBuilderOutput(**self.state.get_last_data("StructuralAnalysis"))
        # Include metrics in evaluation input
        evaluation_input = context_data.model_dump()
        evaluation_input["metrics"] = discovery_data.architecture_graph.get("modules", {}) if discovery_data.architecture_graph else {}
        
        if not await self._execute_agent("RiskEvaluation", self.auditor.GapAnalyzer, evaluation_input, goals):
            return {"error": "Risk evaluation failed."}
        gap_data = GapAnalyzerOutput(**self.state.get_last_data("RiskEvaluation"))

        # 4. Work Decomposition
        if not await self._execute_agent("WorkDecomposition", self.auditor.TicketGenerator, gap_data):
            return {"error": "Work decomposition failed."}
        tickets_out = TicketGeneratorOutput(**self.state.get_last_data("WorkDecomposition"))
        tickets = tickets_out.tickets

        # 5. Execution Forecasting (Planner)
        if not await self._execute_agent("ExecutionForecasting", self.auditor.Planner, tickets):
            return {"error": "Execution forecasting failed."}
        planner_data = PlannerOutput(**self.state.get_last_data("ExecutionForecasting"))
        sprint_plan = [day.model_dump() for day in planner_data.sprint_plan]

        # 6. Integrity Audit
        if not await self._execute_agent("IntegrityAudit", self.auditor.AuditorVerifier, sprint_plan):
            return {"error": "Integrity audit failed."}
        audit_report = AuditorVerifierOutput(**self.state.get_last_data("IntegrityAudit"))

        # Mapping for UI/CLI
        findings = audit_report.findings
        notes_map = {n.get("title"): n.get("risk_note") for n in findings if isinstance(n, dict)}
        
        final_tasks = []
        for task in tickets:
            final_tasks.append({
                "ticket_id": task.ticket_id,
                "title": task.title,
                "description": task.description,
                "effort_min": task.effort_min,
                "effort_max": task.effort_max,
                "priority": task.priority,
                "type": task.type,
                "severity": task.severity,
                "confidence_score": task.confidence_score,
                "confidence_level": task.confidence_level,
                "uncertainty_drivers": task.uncertainty_drivers,
                "tags": task.labels,
                "module": task.module,
                "evidence": task.evidence.model_dump() if task.evidence else None,
                "risk_flags": task.risk_flags,
                "suggested_fix": task.suggested_fix,
                "dependencies": task.dependencies,
                "subtasks": [st.model_dump() for st in task.subtasks] if task.subtasks else [],
                "notes": notes_map.get(task.title, "")
            })

        result_report = {
            "goal": goals.get("user_context", "General Improvement"),
            "tasks": final_tasks,
            "sprintPlan": sprint_plan,
            "gap_analysis": gap_data.markdown_report,
            "summary": audit_report.summary,
            "performance": {
                "total_latency": sum(r.latency_ms for r in self.state.history if r.latency_ms),
                "resolved_path": resolved_path,
                "metrics": discovery_data.architecture_graph.get("layer_stats", {}) if discovery_data.architecture_graph else {}
            }
        }
        
        self.persistence.save_report(resolved_path, result_report)
        return result_report

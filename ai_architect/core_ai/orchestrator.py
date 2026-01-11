import json
import logging
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

# Set up logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("ArchAI.Orchestrator")

class Orchestrator:
    def __init__(self, auditor_instance):
        self.auditor = auditor_instance
        self.logger = logger
        self.state: Optional[AgentState] = None
        self.stability_analyzer = ProactiveStabilityAnalyzer(model=auditor_instance.model)

    async def _execute_agent(self, agent_name: str, func, *args, **kwargs) -> bool:
        """
        Executes a single agent with monitoring, state recording, and output validation.
        Supports both sync and async functions.
        """
        start_time = time.time()
        self.logger.info(f"--- [Agent START] {agent_name} ---")
        
        try:
            # Handle both sync and async agent functions
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            latency = (time.time() - start_time) * 1000
            
            # Validation: Result must not be None and must be a dict or Pydantic model
            if result is None:
                raise ValueError(f"Agent {agent_name} returned None.")
            
            # Convert Pydantic model to dict for storage in AgentResponse.data
            data_dict = result.model_dump() if isinstance(result, BaseModel) else result
            
            response = AgentResponse(
                agent_name=agent_name,
                success=True,
                data=data_dict,
                latency_ms=latency
            )
            self.state.history.append(response)
            self.logger.info(f"--- [Agent DONE] {agent_name} (Success, Latency: {latency:.2f}ms) ---")
            return True
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            self.logger.error(f"Agent {agent_name} CRITICAL FAILURE: {e}")
            response = AgentResponse(
                agent_name=agent_name,
                success=False,
                data={},
                error=str(e),
                latency_ms=latency
            )
            self.state.history.append(response)
            return False

    async def run_pipeline(self, repo_path: str, goals: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orchestrates the 7-agent workflow with strict validation and error recovery.
        """
        self.state = AgentState(repo_path=repo_path, goals=goals)
        self.logger.info(f"Starting Orchestration pipeline for: {repo_path}")
        
        # 0. Path Navigator
        if not await self._execute_agent("PathNavigator", self.auditor.PathNavigator, repo_path):
            return {"error": "Path navigation failed. Orchestration stopped."}
        
        nav_data = PathNavigatorOutput(**self.state.get_last_data("PathNavigator"))
        resolved_path = nav_data.resolved_path
        
        if not nav_data.exists_hint:
             return {"error": f"Resolved path does not exist: {resolved_path}. Analysis impossible."}

        # 1. Discovery
        if not await self._execute_agent("Discovery", self.auditor.Discovery, resolved_path):
            return {"error": "Discovery failed. Orchestration stopped."}
        
        discovery_data = DiscoveryOutput(**self.state.get_last_data("Discovery"))

        # 2. Context Builder
        if not await self._execute_agent("ContextBuilder", self.auditor.ContextBuilder, discovery_data):
            return {"error": "Context building failed. Orchestration stopped."}
        
        context_data = ContextBuilderOutput(**self.state.get_last_data("ContextBuilder"))

        # 3. Gap Analyzer
        if not await self._execute_agent("GapAnalyzer", self.auditor.GapAnalyzer, context_data, goals):
            return {"error": "Gap analysis failed. Orchestration stopped."}
        
        gap_data = GapAnalyzerOutput(**self.state.get_last_data("GapAnalyzer"))

        # 4. Ticket Generator
        if not await self._execute_agent("TicketGenerator", self.auditor.TicketGenerator, gap_data):
            return {"error": "Ticket generation failed. Orchestration stopped."}
        
        tickets_full = TicketGeneratorOutput(**self.state.get_last_data("TicketGenerator"))
        tickets = tickets_full.tickets
        self.logger.info(f"Generated {len(tickets)} development tickets.")

        # 5. Planner
        if not await self._execute_agent("Planner", self.auditor.Planner, tickets):
            return {"error": "Sprint planning failed. Orchestration stopped."}
        
        planner_data = PlannerOutput(**self.state.get_last_data("Planner"))
        sprint_plan = [day.model_dump() for day in planner_data.sprint_plan]

        # 6. Auditor Verifier
        # Note: We pass the raw sprint plan dicts for LLM processing
        if not await self._execute_agent("AuditorVerifier", self.auditor.AuditorVerifier, sprint_plan):
            return {"error": "Plan verification failed. Orchestration stopped."}
        
        audit_report = AuditorVerifierOutput(**self.state.get_last_data("AuditorVerifier"))

        # --- Final Data Integration ---
        findings = audit_report.findings
        notes_map = {note.get("title"): note.get("risk_note") for note in findings if isinstance(note, dict)}
        
        final_tasks = []
        for task in tickets:
            final_tasks.append({
                "id": task.title.lower().replace(" ", "_"),
                "title": task.title,
                "description": task.description,
                "effortHours": task.effort_hours,
                "priority": task.priority,
                "tags": task.labels,
                "module": task.module,
                "notes": notes_map.get(task.title, "")
            })

        # Calculate performance metrics
        total_latency = sum(r.latency_ms for r in self.state.history if r.latency_ms)
        
        # Proactive Stability Analysis
        self.logger.info("Running Proactive Stability Analysis...")
        stability_recommendations = self.stability_analyzer.analyze_stability_risks(self.state.history)

        result_report = {
            "goal": goals.get("expected_output", "General Improvement"),
            "tasks": final_tasks,
            "sprintPlan": sprint_plan,
            "summary": audit_report.summary,
            "performance": {
                "totalLatencyMs": total_latency,
                "agentCount": len(self.state.history),
                "stabilityRecommendations": stability_recommendations,
                "resolvedPath": resolved_path,
                "discoveryMetrics": {
                    "languages": discovery_data.languages,
                    "frameworks": discovery_data.frameworks
                }
            }
        }
        
        if len(tickets) == 0:
            result_report["diagnostics"] = {
                "languages_found": discovery_data.languages,
                "architecture": discovery_data.architecture_type,
                "reason": "Check if goals are already met or if prompts need adjustment."
            }

        return result_report

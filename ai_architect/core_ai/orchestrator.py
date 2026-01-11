import json
import logging
import time
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from ..data.models import AgentState, AgentResponse
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

    def _execute_agent(self, agent_name: str, func, *args, **kwargs) -> bool:
        """
        Executes a single agent with monitoring and state recording.
        """
        start_time = time.time()
        self.logger.info(f"--- [Agent START] {agent_name} ---")
        
        try:
            result = func(*args, **kwargs)
            latency = (time.time() - start_time) * 1000
            
            # Check for null or empty results which might indicate an issue
            if not result:
                 self.logger.warning(f"Agent {agent_name} returned an empty or null result.")
            
            response = AgentResponse(
                agent_name=agent_name,
                success=True,
                data=result if isinstance(result, dict) else {"content": result},
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

    def run_pipeline(self, repo_path: str, goals: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orchestrates the 7-agent workflow (PathNavigator + 6 standard agents) with detailed diagnostics.
        """
        self.state = AgentState(repo_path=repo_path, goals=goals)
        self.logger.info(f"Starting Orchestration pipeline for: {repo_path}")
        
        # 0. Path Navigator - Resolve the real directory before scanning
        if not self._execute_agent("PathNavigator", self.auditor.PathNavigator, repo_path):
            return {"error": "Path navigation failed."}
        
        nav_data = self.state.get_last_data("PathNavigator")
        resolved_path = nav_data.get("resolved_path", repo_path)
        self.logger.info(f"Resolved Path for analysis: {resolved_path}")
        
        # Verify path exists before proceeding to Discovery
        if not Path(resolved_path).exists():
             self.logger.error(f"Resolved path does not exist: {resolved_path}")
             return {"error": f"Resolved path does not exist: {resolved_path}. Check permissions or input."}

        # 1. Discovery
        if not self._execute_agent("Discovery", self.auditor.Discovery, resolved_path):
            return {"error": "Discovery phase failed."}
        
        discovery_data = self.state.get_last_data("Discovery")

        # 2. Context Builder
        if not self._execute_agent("ContextBuilder", self.auditor.ContextBuilder, discovery_data):
            return {"error": "Context building failed."}
        
        context_data = self.state.get_last_data("ContextBuilder")

        # 3. Gap Analyzer
        if not self._execute_agent("GapAnalyzer", self.auditor.GapAnalyzer, context_data, goals):
            return {"error": "Gap analysis failed."}
        
        gap_data = self.state.get_last_data("GapAnalyzer")

        # 4. Ticket Generator
        if not self._execute_agent("TicketGenerator", self.auditor.TicketGenerator, gap_data):
            return {"error": "Ticket generation failed."}
        
        tickets_full = self.state.get_last_data("TicketGenerator")
        tickets = tickets_full.get("tickets", [])
        self.logger.info(f"Generated {len(tickets)} development tickets.")
        
        if len(tickets) == 0:
            self.logger.warning("Agent Chain reported 0 issues. verify if goals match current state.")

        # 5. Planner
        if not self._execute_agent("Planner", self.auditor.Planner, tickets):
            return {"error": "Sprint planning failed."}
        
        sprint_plan_data = self.state.get_last_data("Planner")
        sprint_plan = sprint_plan_data.get("content") or []

        # 6. Auditor Verifier
        if not self._execute_agent("AuditorVerifier", self.auditor.AuditorVerifier, sprint_plan):
            return {"error": "Plan verification failed."}
        
        audit_report = self.state.get_last_data("AuditorVerifier")

        # Merge Audit Findings Logic
        findings = audit_report.get("findings", [])
        notes_map = {note.get("title"): note.get("risk_note") for note in findings if isinstance(note, dict)}
        
        final_tasks = []
        for task in tickets:
            tid = task.get("id") or task.get("title", "task").lower().replace(" ", "_")
            final_tasks.append({
                "id": tid,
                "title": task.get("title", "Proposed Improvement"),
                "description": task.get("description", ""),
                "effortHours": task.get("effort_hours", 2),
                "priority": task.get("priority", "Medium"),
                "tags": task.get("labels", []),
                "dependencies": task.get("dependencies", []),
                "notes": notes_map.get(task.get("title"), "")
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
            "notes": audit_report.get("summary", "Final audit completed successfully."),
            "performance": {
                "totalLatencyMs": total_latency,
                "agentCount": len(self.state.history),
                "stabilityRecommendations": stability_recommendations,
                "resolvedPath": resolved_path
            }
        }
        
        if len(tickets) == 0:
            result_report["diagnostics"] = {
                "scan_summary": discovery_data.get("_raw_structure", "No scan data.")[:500] + "...",
                "detected_languages": discovery_data.get("languages", []),
                "issue": "0 tickets generated. Check if goals are already met.",
                "resolved_path_used": resolved_path
            }

        return result_report

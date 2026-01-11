from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class TestGenerationRequest(BaseModel):
    source_code: str
    function_name: str
    target_file_path: str

class TestGenerationResult(BaseModel):
    generated_code: str
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class EvaluationMetric(BaseModel):
    run_id: str
    valid_syntax: bool
    tests_passed: bool
    coverage_percent: float
    total_score: float
    details: Dict[str, Any] = {}

class ImprovementSuggestion(BaseModel):
    strategy_name: str
    description: str
    suggested_prompt_modification: Optional[str] = None
    suggested_code_example: Optional[str] = None
    xai_explanation: Optional[str] = None

class ReconciliationResult(BaseModel):
    selected_strategy: str
    rationale: str
    timestamp: datetime = Field(default_factory=datetime.now)

class AuditTicket(BaseModel):
    title: str
    type: str # Architecture, Database, Logic, Security, Performance
    severity: str # High, Medium, Low
    priority: str = "Medium" # Critical, High, Medium, Low
    description: str
    suggested_fix: str
    effort_hours: int = 2
    labels: List[str] = []
    module: Optional[str] = None

class SprintDay(BaseModel):
    day: str
    tickets: List[AuditTicket]
    total_hours: float

class AuditReport(BaseModel):
    discovery: Dict[str, Any] = {}
    gap_analysis: Optional[str] = None
    tickets: List[AuditTicket]
    sprint_plan: List[SprintDay] = []
    summary: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class AgentResponse(BaseModel):
    agent_name: str
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    latency_ms: Optional[float] = None

class AgentState(BaseModel):
    repo_path: str
    goals: Dict[str, Any]
    history: List[AgentResponse] = []
    metadata: Dict[str, Any] = {}

    def get_last_data(self, agent_name: str) -> Optional[Dict[str, Any]]:
        for response in reversed(self.history):
            if response.agent_name == agent_name and response.success:
                return response.data
        return None

# --- Specific Agent Protocols ---

class PathNavigatorOutput(BaseModel):
    resolved_path: str
    exists_hint: bool
    rationale: str

class DiscoveryOutput(BaseModel):
    languages: List[str]
    frameworks: List[str]
    architecture_type: str
    module_summary: Dict[str, str]
    raw_structure: Optional[str] = None
    architecture_graph: Optional[Dict[str, Any]] = None

class ContextBuilderOutput(BaseModel):
    dependencies: List[Dict[str, str]]
    patterns: List[str]
    critical_paths: List[str]

class GapAnalyzerOutput(BaseModel):
    markdown_report: str

class TicketGeneratorOutput(BaseModel):
    tickets: List[AuditTicket]

class PlannerOutput(BaseModel):
    sprint_plan: List[SprintDay]

class AuditorVerifierOutput(BaseModel):
    findings: List[Dict[str, Any]]
    summary: str

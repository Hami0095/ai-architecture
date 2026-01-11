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

class Evidence(BaseModel):
    file_path: str
    symbol: Optional[str] = None # Function or class name
    line_range: Optional[str] = None # e.g. "10-25"
    call_chain: List[str] = []
    confidence: float = 1.0 # 0.0 to 1.0
    uncertainty_drivers: List[str] = [] # e.g. "dynamic_dispatch", "missing_tests"

class AuditTicket(BaseModel):
    ticket_id: str = Field(default_factory=lambda: datetime.now().strftime("%y%m%d%H%M%S"))
    title: str
    epic: Optional[str] = None # Grouping for tasks
    type: str # Architecture, Database, Logic, Security, Performance
    severity: str # High, Medium, Low
    priority: str = "Medium" # Critical, High, Medium, Low
    description: str
    suggested_fix: str
    effort_hours: int = 2
    labels: List[str] = []
    module: Optional[str] = None
    evidence: Optional[Evidence] = None
    risk_flags: List[str] = [] # e.g. ["high-churn", "deep-dependency"]
    dependencies: List[str] = [] # IDs of other tickets

class SprintDay(BaseModel):
    day: str
    tickets: List[AuditTicket]
    total_hours: float
    feasibility: str = "Likely fits" # "Likely fits", "High risk", "Will overflow"

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
    evidence_trail: List[Evidence] = [] # Added for traceabilty

class TicketGeneratorOutput(BaseModel):
    tickets: List[AuditTicket]

class PlannerOutput(BaseModel):
    sprint_plan: List[SprintDay]

class AuditorVerifierOutput(BaseModel):
    findings: List[Dict[str, Any]]
    summary: str

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

class SubTask(BaseModel):
    title: str
    description: str
    effort_hours: float = 1.0
    risk_level: str = "LOW" # LOW, MEDIUM, HIGH

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
    subtasks: List[SubTask] = []

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

class ImpactAssessment(BaseModel):
    target: str # path or symbol
    risk_level: str # LOW, MEDIUM, HIGH, UNKNOWN
    risk_score: float # 0-100
    confidence_score: float # 0.0-1.0
    affected_components: List[Dict[str, Any]] = [] # list of {name, depth, file}
    primary_risk_factors: List[str] = []
    recommendations: List[str] = []
    insufficient_data: bool = False
    rationale: Optional[str] = None

class WDPOutput(BaseModel):
    epics: List[Dict[str, Any]] # {name, description, tickets: [AuditTicket]}
    sprint_feasibility: Dict[str, Any] # {status, rationale, bottlenecks}
    overall_confidence: float
    assumptions: List[str] = []

class SprintPlanConfig(BaseModel):
    team_size: int = 3
    days: int = 10
    velocity_factor: float = 0.8 # 0.0 to 1.0

class TaskPrediction(BaseModel):
    ticket_id: str
    probability: float # 0.0 - 1.0
    risk_level: str
    rationale: str
    completion_window: Optional[str] = None # e.g. "Early Sprint", "Late Sprint", "Risk of Spillover"

class SRCOutput(BaseModel):
    sprint_goal: str
    confidence_score: float # 0.0 - 1.0
    status: str # High Confidence, Medium Confidence, Low Confidence
    task_predictions: List[TaskPrediction]
    epic_forecasts: List[Dict[str, Any]] # {epic_name, completion_probability}
    risk_summary: Dict[str, List[str]] # {critical, high, medium}
    recommendations: List[Dict[str, str]] # {task, action}
    bottlenecks: List[str]
    confidence_rationale: str

# --- GitHub Integration Models ---

class GitHubChange(BaseModel):
    file_path: str
    status: str # added, modified, removed
    additions: int
    deletions: int
    patch: Optional[str] = None

class GitHubCommit(BaseModel):
    sha: str
    message: str
    author: str
    timestamp: datetime
    changes: List[GitHubChange] = []

class GitHubPR(BaseModel):
    number: int
    title: str
    state: str # open, closed
    author: str
    target_branch: str
    source_branch: str
    commits: List[GitHubCommit] = []
    diff_url: Optional[str] = None

class PRAnalysisReport(BaseModel):
    pr_number: int
    impact_assessment: ImpactAssessment
    task_generation: Optional[WDPOutput] = None
    confidence_prediction: Optional[SRCOutput] = None
    timestamp: datetime = Field(default_factory=datetime.now)

# --- PM Integration Models ---

class PMTaskMetadata(BaseModel):
    tool: str # jira, trello
    remote_id: str
    remote_url: Optional[str] = None
    status: str
    last_sync: datetime = Field(default_factory=datetime.now)

class PMSyncReport(BaseModel):
    tool: str
    project_key: str
    tasks_created: int
    tasks_updated: int
    errors: List[str] = []
    sync_time: datetime = Field(default_factory=datetime.now)

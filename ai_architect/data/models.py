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

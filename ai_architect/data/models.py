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

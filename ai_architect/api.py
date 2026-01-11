from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
from .core_ai.auditor import ArchitecturalAuditor
from .infrastructure.logging_utils import logger
from .infrastructure.config_manager import config

app = FastAPI(title="ArchAI API", description="REST API for Autonomous Architectural Audits")

class AuditRequest(BaseModel):
    path: str
    context: Optional[str] = "General software project"
    goal: Optional[str] = "Production-ready system"

@app.get("/health")
def health_check():
    return {"status": "online", "model": config.get("model", "qwen3-coder:480b-cloud")}

@app.post("/audit")
async def run_audit(request: AuditRequest):
    """Triggers an asynchronous architectural audit."""
    logger.info(f"API Request: Audit path {request.path}")
    auditor = ArchitecturalAuditor()
    try:
        report = await auditor.audit_project(
            root_path=request.path,
            user_context=request.context,
            expected_output=request.goal
        )
        return report
    except Exception as e:
        logger.error(f"API Audit Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

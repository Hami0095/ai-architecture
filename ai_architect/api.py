import time
from fastapi import FastAPI, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Dict, Any, Optional
from .core_ai.auditor import ArchitecturalAuditor
from .infrastructure.logging_utils import logger
from .infrastructure.config_manager import config
from .infrastructure.monitoring import monitor
from .infrastructure.caching import cached

app = FastAPI(title="ArchAI API", description="REST API for Autonomous Architectural Audits")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = (time.time() - start_time) * 1000
    logger.info(f"HTTP {request.method} {request.url.path} - {response.status_code} ({duration:.2f}ms)")
    return response

class AuditRequest(BaseModel):
    path: str
    context: Optional[str] = "General software project"
    goal: Optional[str] = "Production-ready system"

    # Make hashable for caching key generation
    def __hash__(self):
        return hash((self.path, self.context, self.goal))

@app.get("/health")
def health_check():
    return {"status": "online", "model": config.get("model", "qwen3-coder:480b-cloud")}

@app.get("/metrics")
@cached(prefix="metrics", ttl=10) # Cache metrics for 10 seconds to reduce DB load
async def get_metrics():
    """Returns real-time performance and health metrics."""
    return monitor.get_system_health()

@app.post("/audit")
@cached(prefix="full_audit", ttl=300) # Cache identical audit requests for 5 minutes
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

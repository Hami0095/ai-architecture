import time
from fastapi import FastAPI, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Dict, Any, Optional
from .core_ai.auditor import ArchitecturalAuditor
from .infrastructure.logging_utils import logger
from .infrastructure.config_manager import config
from .infrastructure.monitoring import monitor
from .infrastructure.caching import cached

from starlette.middleware.sessions import SessionMiddleware
from .api import auth

app = FastAPI(title="ArchAI API", description="REST API for Autonomous Architectural Audits")

# Add Session Middleware for OAuth
app.add_middleware(SessionMiddleware, secret_key=config.get_secret("session_secret", "archai-dev-secret"))

# Register Auth Router
app.include_router(auth.router)

API_KEY = config.get("api_key", "archai-secret-key")
api_key_header = APIKeyHeader(name="X-API-Key")

def get_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key

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

class ImpactRequest(BaseModel):
    path: str
    target: str
    depth: int = 3

class PlanRequest(BaseModel):
    path: str
    goal: str
    team_size: int = 3
    days: int = 10

class SimulationRequest(BaseModel):
    path: str
    goal: str
    team_size: int = 3
    days: int = 10
    strict: bool = False

class GitHubPRListRequest(BaseModel):
    repo: str

class GitHubPRAnalyzeRequest(BaseModel):
    repo: str
    pr_number: int
    path: str
    comment: bool = False

    # Make hashable for caching key generation
    def __hash__(self):
        return hash((self.path, self.context, self.goal))

@app.get("/health")
def health_check():
    return {"status": "online", "model": config.get("model", "qwen3-coder:480b-cloud")}

@app.get("/metrics", dependencies=[Depends(get_api_key)])
@cached(prefix="metrics", ttl=10) # Cache metrics for 10 seconds to reduce DB load
async def get_metrics():
    """Returns real-time performance and health metrics."""
    return monitor.get_system_health()

@app.post("/impact", dependencies=[Depends(get_api_key)])
async def run_impact(request: ImpactRequest):
    """CIRAS: Change Impact & Risk Assessment."""
    auditor = ArchitecturalAuditor()
    return auditor.ImpactAnalyzer(request.path, request.target, max_depth=request.depth)

@app.post("/plan", dependencies=[Depends(get_api_key)])
async def run_plan(request: PlanRequest):
    """WDP-TG: Work Decomposition & Task Generation."""
    from .data.models import SprintPlanConfig
    auditor = ArchitecturalAuditor()
    config = SprintPlanConfig(team_size=request.team_size, days=request.days)
    return auditor.WDPPlanner(request.path, request.goal, sprint_config=config)

@app.post("/simulate-sprint", dependencies=[Depends(get_api_key)])
async def run_simulation(request: SimulationRequest):
    """SRC-RS: Sprint Success Simulation."""
    from .data.models import SprintPlanConfig
    auditor = ArchitecturalAuditor()
    config = SprintPlanConfig(team_size=request.team_size, days=request.days)
    plan = auditor.WDPPlanner(request.path, request.goal, sprint_config=config)
    return auditor.SRCEngine(request.path, request.goal, wdp_plan=plan, sprint_config=config, strict=request.strict)

@app.post("/release-confidence", dependencies=[Depends(get_api_key)])
async def run_release_confidence(request: SimulationRequest):
    """SRC-RS: Release Integrity Assessment."""
    return await run_simulation(request)

@app.post("/github/prs", dependencies=[Depends(get_api_key)])
async def list_github_prs(request: GitHubPRListRequest):
    """Lists open pull requests for a repository."""
    from .connectors.github import GitHubConnector
    connector = GitHubConnector()
    return connector.fetch_open_prs(request.repo)

@app.post("/github/analyze-pr", dependencies=[Depends(get_api_key)])
async def analyze_github_pr(request: GitHubPRAnalyzeRequest):
    """Analyzes a specific GitHub PR and optionally posts a comment."""
    from .connectors.github import GitHubConnector
    connector = GitHubConnector()
    report = connector.analyze_pr(request.repo, request.pr_number, request.path)
    if report and request.comment:
        connector.post_pr_comment(request.repo, request.pr_number, report)
    return report

@app.post("/audit", dependencies=[Depends(get_api_key)])
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

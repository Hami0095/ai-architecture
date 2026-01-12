import os
import logging
import subprocess
import tempfile
import shutil
from typing import List, Optional, Dict, Any
from github import Github, GithubException
from pathlib import Path
from ..data.models import GitHubPR, GitHubCommit, GitHubChange, PRAnalysisReport
from ..core_ai.auditor import ArchitecturalAuditor
from ..infrastructure.config_manager import config

logger = logging.getLogger("ArchAI.GitHub")

class GitHubConnector:
    """Connects ArchAI to GitHub for automated project analysis and risk assessment."""
    
    def __init__(self, token: Optional[str] = None):
        self.token = token or config.get_secret("github.token") or config.get_secret("github_token")
        if not self.token:
            logger.warning("No GitHub token provided. Some operations may fail due to rate limiting.")
        self.gh = Github(self.token) if self.token else Github()
        self.auditor = ArchitecturalAuditor()

    def get_repo(self, repo_full_name: str):
        """Fetches a repository by its full name (e.g., 'owner/repo')."""
        try:
            return self.gh.get_repo(repo_full_name)
        except GithubException as e:
            if e.status == 403 and "rate limit exceeded" in str(e).lower():
                msg = "GitHub Rate Limit Exceeded. "
                if not self.token:
                    msg += "Please provide a 'github_token' in archai_config.yaml or .env to increase limits."
                else:
                    msg += "Your token may have reached its hourly limit."
                logger.error(msg)
                print(f"❌ {msg}")
            else:
                logger.error(f"Failed to fetch repo {repo_full_name}: {e}")
            return None

    def fetch_open_prs(self, repo_full_name: str) -> List[GitHubPR]:
        """Retrieves all open pull requests for a repository."""
        repo = self.get_repo(repo_full_name)
        if not repo:
            return []
        
        prs = []
        for pr in repo.get_pulls(state='open'):
            prs.append(GitHubPR(
                number=pr.number,
                title=pr.title,
                state=pr.state,
                author=pr.user.login,
                target_branch=pr.base.ref,
                source_branch=pr.head.ref,
                diff_url=pr.diff_url
            ))
        return prs

    def analyze_pr(self, repo_full_name: str, pr_number: int, local_repo_path: str) -> Optional[PRAnalysisReport]:
        """Analyzes a specific PR by running CIRAS and WDP-TG on its changes."""
        repo = self.get_repo(repo_full_name)
        if not repo:
            return None
        
        try:
            pr = repo.get_pull(pr_number)
            files = pr.get_files()
            
            # 1. Identify critical files in the PR
            critical_files = [f.filename for f in files if f.status in ['modified', 'added']]
            if not critical_files:
                logger.info(f"No active file changes in PR #{pr_number}")
                return None
            
            # 2. Run CIRAS on the primary target (e.g., the first file or most complex one)
            # For simplicity, we assess the first modified file
            target = critical_files[0]
            logger.info(f"Running CIRAS on {target} for PR #{pr_number}")
            
            impact = self.auditor.ImpactAnalyzer(local_repo_path, target)
            
            # 3. Generate Task Plan (WDP-TG)
            goal = f"Implement changes proposed in PR #{pr_number}: {pr.title}"
            plan = self.auditor.WDPPlanner(local_repo_path, goal)
            
            # 4. Predict Confidence (SRC-RS)
            src = self.auditor.SRCEngine(local_repo_path, goal, wdp_plan=plan)
            
            return PRAnalysisReport(
                pr_number=pr_number,
                impact_assessment=impact,
                task_generation=plan,
                confidence_prediction=src
            )
            
        except Exception as e:
            logger.error(f"Error analyzing PR #{pr_number}: {e}")
            return None

    def post_pr_comment(self, repo_full_name: str, pr_number: int, report: PRAnalysisReport):
        """Posts the analysis result as a comment on the GitHub PR."""
        repo = self.get_repo(repo_full_name)
        if not repo:
            return
        
        try:
            pr = repo.get_pull(pr_number)
            
            comment = f"## 🛡️ ArchAI Risk Assessment: PR #{pr_number}\n\n"
            comment += f"**Risk Level:** {report.impact_assessment.risk_level} (Score: {report.impact_assessment.risk_score})\n"
            comment += f"**Confidence:** {report.impact_assessment.confidence_score*100:.1f}%\n\n"
            
            comment += "### 📋 Impact Summary\n"
            comment += f"{report.impact_assessment.rationale}\n\n"
            
            if report.confidence_prediction:
                conf = report.confidence_prediction
                comment += "### 🎯 Sprint Confidence\n"
                comment += f"**Score:** {conf.confidence_score*100:.1f}% ({conf.status})\n"
                comment += f"**Rationale:** {conf.confidence_rationale}\n\n"
            
            comment += "---\n*Generated by ArchAI GitHub Connector*"
            
            pr.create_issue_comment(comment)
            logger.info(f"Posted analysis comment on PR #{pr_number}")
            
        except Exception as e:
            logger.error(f"Failed to post comment on PR #{pr_number}: {e}")

    def clone_repo(self, repo_full_name: str, target_dir: str):
        """Clones a GitHub repository to a local directory."""
        repo = self.get_repo(repo_full_name)
        if not repo:
            return False
        
        clone_url = repo.clone_url
        if self.token:
            # Inject token for private repos
            clone_url = clone_url.replace("https://", f"https://{self.token}@")
        
        try:
            logger.info(f"Cloning {repo_full_name} to {target_dir}...")
            subprocess.run(["git", "clone", "--depth", "1", clone_url, target_dir], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clone repo: {e.stderr.decode()}")
            return False

    async def audit_repo(self, repo_full_name: str, context: Optional[str] = None):
        """Clones and audits a remote GitHub repository."""
        temp_dir = tempfile.mkdtemp(prefix="archai_git_")
        try:
            if self.clone_repo(repo_full_name, temp_dir):
                print(f"📡 Clone complete. Starting audit on {repo_full_name}...")
                report = await self.auditor.audit_project(
                    root_path=temp_dir,
                    user_context=context or f"Audit of {repo_full_name}",
                    project_status="Remote Source"
                )
                return report
            return None
        finally:
            # Note: We keep the temp dir for now if the user wants to IMPACT/PLAN later, 
            # but ideally we should manage its lifecycle.
            pass

    def validate_local_diff(self, repo_path: str, base_branch: str = "main"):
        """Phase 2: Quiet validation on local diffs. Skips remote API entirely."""
        try:
            # 1. Get changed files vs base branch using git
            result = subprocess.run(
                ["git", "diff", "--name-only", base_branch],
                cwd=repo_path, capture_output=True, text=True, check=True
            )
            files = [f for f in result.stdout.splitlines() if f.endswith(".py")]
            
            if not files:
                return []

            reports = []
            for file in files:
                # 2. Run high-fidelity Impact Analysis on each changed file
                impact = self.auditor.ImpactAnalyzer(repo_path, file)
                reports.append(impact)
            
            return reports
        except Exception as e:
            logger.error(f"Local diff validation failed: {e}")
            return []

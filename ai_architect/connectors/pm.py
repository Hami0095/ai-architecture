import logging
from typing import List, Optional, Dict, Any
from jira import JIRA
from trello import TrelloClient
from ..data.models import WDPOutput, PMSyncReport, AuditTicket
from ..infrastructure.config_manager import config

logger = logging.getLogger("ArchAI.PM")

class PMConnector:
    """Connects ArchAI to Project Management tools like Jira and Trello."""

    def __init__(self, tool: str = "jira"):
        self.tool = tool.lower()
        self.client = self._init_client()

    def _init_client(self):
        if self.tool == "jira":
            server = config.get("jira.server")
            email = config.get("jira.email")
            token = config.get_secret("jira.token")
            if not all([server, email, token]):
                logger.warning("Jira configuration incomplete.")
                return None
            return JIRA(server=server, basic_auth=(email, token))
        
        elif self.tool == "trello":
            api_key = config.get("trello.api_key")
            token = config.get_secret("trello.token")
            if not all([api_key, token]):
                logger.warning("Trello configuration incomplete.")
                return None
            return TrelloClient(api_key=api_key, token=token)
        
        return None

    def push_plan(self, project_key: str, plan: WDPOutput) -> PMSyncReport:
        """Pushes a WDP-TG plan to the PM tool."""
        if not self.client:
            return PMSyncReport(tool=self.tool, project_key=project_key, tasks_created=0, tasks_updated=0, errors=["Client not initialized"])

        if self.tool == "jira":
            return self._push_to_jira(project_key, plan)
        elif self.tool == "trello":
            return self._push_to_trello(project_key, plan)
        
        return PMSyncReport(tool=self.tool, project_key=project_key, tasks_created=0, tasks_updated=0, errors=["Unsupported tool"])

    def _push_to_jira(self, project_key: str, plan: WDPOutput) -> PMSyncReport:
        created = 0
        errors = []
        try:
            for epic in plan.epics:
                # 1. Create Epic
                epic_issue = self.client.create_issue(
                    project=project_key,
                    summary=f"[ArchAI] Epic: {epic['name']}",
                    description=epic['description'],
                    issuetype={'name': 'Epic'},
                    customfield_10011=epic['name'] # Epic Name field often varies, this is a default
                )
                
                for ticket in epic.get('tickets', []):
                    # 2. Create Task linked to Epic
                    task_issue = self.client.create_issue(
                        project=project_key,
                        summary=f"[{ticket.get('priority')}] {ticket.get('title')}",
                        description=self._format_description(ticket),
                        issuetype={'name': 'Task'},
                        parent={'id': epic_issue.id} if hasattr(epic_issue, 'id') else None
                    )
                    created += 1
                    
                    # 3. Create Subtasks
                    for st in ticket.get('subtasks', []):
                        self.client.create_issue(
                            project=project_key,
                            summary=st.get('title'),
                            description=st.get('description'),
                            issuetype={'name': 'Sub-task'},
                            parent={'id': task_issue.id}
                        )
                        created += 1
                        
            return PMSyncReport(tool="jira", project_key=project_key, tasks_created=created, tasks_updated=0)
        except Exception as e:
            logger.error(f"Jira Sync Error: {e}")
            return PMSyncReport(tool="jira", project_key=project_key, tasks_created=created, tasks_updated=0, errors=[str(e)])

    def _push_to_trello(self, board_id: str, plan: WDPOutput) -> PMSyncReport:
        created = 0
        errors = []
        try:
            board = self.client.get_board(board_id)
            for epic in plan.epics:
                # Create a List for each Epic
                trello_list = board.add_list(epic['name'])
                
                for ticket in epic.get('tickets', []):
                    # Create a Card for each Ticket
                    card = trello_list.add_card(
                        name=f"[{ticket.get('priority')}] {ticket.get('title')}",
                        desc=self._format_description(ticket)
                    )
                    created += 1
                    
                    # Add Checklists for Subtasks
                    if ticket.get('subtasks'):
                        checklist = card.add_checklist("Subtasks", [st.get('title') for st in ticket['subtasks']])
                        created += 1
                        
            return PMSyncReport(tool="trello", project_key=board_id, tasks_created=created, tasks_updated=0)
        except Exception as e:
            logger.error(f"Trello Sync Error: {e}")
            return PMSyncReport(tool="trello", project_key=board_id, tasks_created=created, tasks_updated=0, errors=[str(e)])

    def _format_description(self, ticket: Dict[str, Any]) -> str:
        desc = ticket.get('description', '') + "\n\n"
        if ticket.get('risk_flags'):
            desc += f"*Risk Flags:* {', '.join(ticket['risk_flags'])}\n"
        if ticket.get('effort_min') and ticket.get('effort_max'):
            desc += f"*Estimated Effort:* {ticket['effort_min']}-{ticket['effort_max']}h\n"
        if ticket.get('suggested_fix'):
            desc += f"\n*Suggested Fix:*\n{ticket['suggested_fix']}"
        return desc

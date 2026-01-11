# Project Management (PM) Integration

ArchAI bridges the gap between architectural analysis and project execution by automatically pushing generated tasks to your team's preferred PM tools.

## Capability Overview

### 1. Automated Task Export
ArchAI can convert its internal **WDP-TG** plans (hierarchical Epics, Tasks, and Subtasks) into native entities in tools like Jira and Trello.

### 2. Risk-Aware Workflows
Every task pushed to a PM tool includes:
- **Risk Level**: Clearly flagged (e.g., HIGH, MEDIUM) based on CIRAS analysis.
- **Traceability**: Links back to the relevant GitHub commits, files, and functions.
- **Technical Guidance**: The "Suggested Fix" is included in the task description to guide developers.

### 3. Tool Support
- **Jira**: Creates Epics, Tasks, and Sub-tasks with established parent-child relationships.
- **Trello**: Creates Lists (for Epics), Cards (for Tasks), and Checklists (for Subtasks).

## CLI Usage

### Push a Plan to Jira
```bash
ai-architect pm push "Refactor the authentication layer" --tool jira --project "PROJ-KEY"
```

### Push a Plan to Trello
```bash
ai-architect pm push "Implement search functionality" --tool trello --project "BOARD-ID"
```

## Configuration

Add your PM credentials to `archai_config.yaml` or as environment variables:

### Jira Configuration
```yaml
jira:
  server: "https://your-domain.atlassian.net"
  email: "your-email@example.com"
  token: "your-atlassian-api-token"
```

### Trello Configuration
```yaml
trello:
  api_key: "your-trello-api-key"
  token: "your-trello-token"
```

## Data Mapping & Traceability
| ArchAI Entity | Jira Entity | Trello Entity |
| --- | --- | --- |
| **Epic** | Epic | List |
| **Ticket** | Task | Card |
| **Subtask** | Sub-task | Checklist Item |
| **Risk Flags** | Labels / Description | Description |
| **Confidence** | Description | Description |

*Note: ArchAI ensures that every ticket remains traceable to its architectural origin, including the specific line ranges and symbols identified by the GraphEngine.*

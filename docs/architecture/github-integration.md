# GitHub Integration

ArchAI can connect directly to your GitHub repositories to provide automated risk assessments and task planning based on real-time development activity.

## Capability Overview

### 1. Repository Analysis
Connect to any public or private repository (with a Personal Access Token). ArchAI can scan branches and understand the codebase structure using its internal `GraphEngine`.

### 2. Pull Request (PR) Tracking
ArchAI tracks open Pull Requests and can analyze the specific "blast radius" of a PR.
- **Risk Assessment**: Runs CIRAS on the files modified in the PR.
- **Task Generation**: Automatically decomposes the PR goal into engineering tickets.
- **Success Simulation**: Predicts the likelihood of the PR being integrated successfully without regressing architectural health.

### 3. Automated Reporting
ArchAI can post its analysis directly to GitHub as comments, providing immediate feedback to developers during the code review process.

## CLI Usage

### Connect to a Repository
```bash
ai-architect github connect owner/repo
```

### List Open PRs
```bash
ai-architect github prs owner/repo
```

### Analyze a Specific PR
```bash
ai-architect github analyze-pr owner/repo 123 --comment
```
*The `--comment` flag will post the results back to the GitHub PR.*

## Configuration

To enable authenticated access and higher rate limits, add your GitHub token to `archai_config.yaml` or set it as an environment variable:

```yaml
# archai_config.yaml
github_token: "your_personal_access_token"
```

```bash
export ARCHAI_GITHUB_TOKEN="your_personal_access_token"
```

## Data Security
ArchAI typically requires **read-only** access for analysis. Write access is only required if you want it to post PR comments or create issue tickets.

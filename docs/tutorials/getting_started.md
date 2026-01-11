# Tutorial: Getting Started with ArchAI

Welcome to ArchAI! This tutorial will guide you through your first architectural audit and successful sprint planning session.

## Step 1: Initialize the Environment
Ensure you have a local LLM running (e.g., Ollama) or your secrets configured in a `.env` file.

```bash
# Check if ArchAI is installed
ai-architect --help
```

## Step 2: Run Your First Impact Analysis
Pick a module in your code you're thinking of refactoring.

```bash
ai-architect impact MyComponentName --explain
```
**Look for**: The "Risk Level" and "Affected Components" list. This tells you the "blast radius" of your change.

## Step 3: Decompose a Goal into Tasks
Now, let's plan the actual change.

```bash
ai-architect plan "Refactor the authentication flow to use JWT" --verbose
```
**Look for**: The hierarchical list of tasks and the "Effort" estimates. Notice how high-risk components are prioritized first.

## Step 4: Simulate the Sprint
Finally, see if your team can actually deliver this in the planned timeframe.

```bash
ai-architect simulate-sprint "Refactor authentication flow" --team-size 3 --days 10
```
**Look for**: The "Overall Confidence" score. If it's below 0.8, check the "Recommendations" to see what pre-work (like adding tests) is needed.

## Next Steps
Explore [Chaining Workflows](chaining_workflows.md) to automate this in your CI/CD pipeline!

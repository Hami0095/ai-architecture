# CLI Usage Examples

## 🛡️ Risk Assessment (CIRAS)

**Determine if refactoring the Orchestrator is safe:**
```bash
ai-architect impact Orchestrator --explain
```

**Verify change safety in CI/CD (Strict Mode):**
```bash
ai-architect impact core.logic.process_data --strict --json
```

## 📋 Planning & Decomposition (WDP-TG)

**Break down a complex cloud migration into tasks:**
```bash
ai-architect plan "Migrate persistence layer to AWS RDS" --team-size 4 --days 14 --verbose
```

**Generate a machine-readable plan for Jira implementation:**
```bash
ai-architect plan "Add OAuth2 support" --json > tasks.json
```

## 🎯 Sprint Simulation (SRC-RS)

**Simulate if a 2-person team can finish a core refactor in 1 week:**
```bash
ai-architect simulate-sprint "Modularize GraphEngine" --team-size 2 --days 5 --verbose
```

**Check release integrity before a deployment:**
```bash
ai-architect release-confidence "v1.2 Stable Release" --strict
```

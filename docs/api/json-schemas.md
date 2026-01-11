# JSON Schemas

ArchAI uses standardized Pydantic models for all agent communications and API responses.

## ImpactAssessment (CIRAS)
```json
{
  "target": "string",
  "risk_level": "LOW|MEDIUM|HIGH|UNKNOWN",
  "risk_score": "float (0-100)",
  "confidence_score": "float (0-1)",
  "affected_components": [
    {"name": "string", "depth": "int", "file": "string"}
  ],
  "primary_risk_factors": ["string"],
  "recommendations": ["string"],
  "insufficient_data": "boolean",
  "rationale": "string"
}
```

## WDPOutput (WDP-TG)
```json
{
  "epics": [
    {
      "name": "string",
      "description": "string",
      "tickets": [
        {
          "ticket_id": "string",
          "title": "string",
          "priority": "Critical|High|Medium|Low",
          "risk_flags": ["string"],
          "effort_hours": "float",
          "dependencies": ["string"],
          "subtasks": [
             {"title": "string", "description": "string", "effort_hours": "float"}
          ]
        }
      ]
    }
  ],
  "sprint_feasibility": {
    "status": "string",
    "rationale": "string",
    "bottlenecks": ["string"]
  }
}
```

## SRCOutput (SRC-RS)
```json
{
  "sprint_goal": "string",
  "confidence_score": "float (0-1)",
  "status": "string",
  "task_predictions": [
    {
      "ticket_id": "string",
      "probability": "float (0-1)",
      "risk_level": "string",
      "rationale": "string"
    }
  ],
  "recommendations": [
    {"task": "string", "action": "string"}
  ]
}
```

# API Reference

ArchAI provides a FastAPI-based REST API for integration into internal dashboards and CI/CD pipelines.

## Endpoints

### `POST /impact`
Triggers a CIRAS risk assessment.

**Request Body:**
```json
{
  "path": "/abs/path/to/repo",
  "target": "SymbolOrFileName",
  "depth": 3
}
```

### `POST /plan`
Triggers a WDP-TG work decomposition.

**Request Body:**
```json
{
  "path": "/abs/path/to/repo",
  "goal": "Feature description",
  "team_size": 3,
  "days": 10
}
```

### `POST /simulate-sprint`
Runs a SRC-RS sprint success simulation.

**Request Body:**
```json
{
  "path": "/abs/path/to/repo",
  "goal": "Goal name",
  "team_size": 3,
  "days": 10,
  "strict": false
}
```

### `POST /release-confidence`
Assess release integrity. Identical request schema to `/simulate-sprint`.

---

## Authentication

ArchAI API uses API Key authentication. All requests to protected endpoints must include the `X-API-Key` header.

**Default Key**: `archai-secret-key` (Configure via `api_key` in `archai_config.yaml`)

## SDK Integration

### Python Example
```python
import requests

headers = {"X-API-Key": "your-secret-key"}
response = requests.post("http://localhost:8000/impact", headers=headers, json={
    "path": "/Development/project",
    "target": "CoreLogic",
    "depth": 5
})

print(response.json())
```

### JavaScript Example
```javascript
const response = await fetch("http://localhost:8000/plan", {
  method: "POST",
  body: JSON.stringify({
    path: "/Development/project",
    goal: "Add unit tests",
    team_size: 2
  }),
  headers: { 
      "Content-Type": "application/json",
      "X-API-Key": "your-secret-key"
  }
});
const data = await response.json();
```

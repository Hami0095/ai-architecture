import asyncio
import pytest
import os
import json
from pathlib import Path
from ai_architect.core_ai.auditor import ArchitecturalAuditor
from ai_architect.data.models import (
    PathNavigatorOutput, 
    DiscoveryOutput, 
    ContextBuilderOutput,
    GapAnalyzerOutput,
    TicketGeneratorOutput,
    PlannerOutput,
    AuditorVerifierOutput,
    AuditTicket
)
from ai_architect.models.base import BaseAIModel

# Mock Model Implementation for Testing
class MockAIModel(BaseAIModel):
    def chat(self, messages, format=None):
        system_prompt = messages[0]['content'].lower()
        
        # Route by actual system prompt keywords from prompts.py
        if "path navigator" in system_prompt:
            return json.dumps({"resolved_path": "/tmp/mock_repo", "rationale": "Mock resolution"})
        elif "discovery agent" in system_prompt:
            return json.dumps({
                "languages": ["Python"],
                "frameworks": ["FastAPI"],
                "architecture_type": "Microservices",
                "module_summary": {"core": "Logic"}
            })
        elif "context builder" in system_prompt:
            return json.dumps({
                "dependencies": [],
                "patterns": ["MockPattern"],
                "critical_paths": []
            })
        elif "gap analyzer" in system_prompt:
            return "Mock Gap Report: Everything is missing."
        elif "lead engineer" in system_prompt: # Ticket Generator
            return json.dumps({
                "tickets": [
                    {
                        "title": "Mock Task",
                        "type": "Logic",
                        "severity": "High",
                        "priority": "Critical",
                        "description": "Clean up",
                        "suggested_fix": "Use better code",
                        "effort_hours": 3,
                        "labels": ["refactor"],
                        "module": "Core"
                    }
                ]
            })
        elif "auditor & verifier" in system_prompt or "verifier" in system_prompt:
            return json.dumps({
                "findings": [{"title": "Mock Task", "risk_note": "No risk"}],
                "summary": "Mock Verification Complete"
            })
        
        return "Generic Mock Response"

@pytest.fixture
def mock_auditor():
    mock_model = MockAIModel("mock-gpt")
    return ArchitecturalAuditor(model=mock_model)

@pytest.mark.asyncio
async def test_agent_decoupling_with_mock(mock_auditor):
    """
    Verifies that the agents work correctly when a non-Ollama model is injected.
    """
    print("\nTesting decoupled agents with MockModel...")
    
    # 1. PathNavigator
    nav = mock_auditor.PathNavigator("/some/relative/path")
    assert nav.rationale == "Mock resolution"
    
    # 2. Discovery
    discovery = mock_auditor.Discovery(".")
    assert any("python" in l.lower() for l in discovery.languages)
    
    # 3. Gap Analysis
    context = ContextBuilderOutput(dependencies=[], patterns=[], critical_paths=[])
    gap = mock_auditor.GapAnalyzer(context, {"expected_output": "Perfect system"})
    assert "everything is missing" in gap.markdown_report.lower()
    
    # 4. Ticket Generator
    tickets_out = mock_auditor.TicketGenerator(gap)
    assert len(tickets_out.tickets) > 0
    assert tickets_out.tickets[0].title == "Mock Task"
    
    print("✓ Decoupled agent testing successful")

@pytest.mark.asyncio
async def test_real_auditor_pipeline():
    """
    Sanity check for the real auditor (defaults to Ollama).
    """
    auditor = ArchitecturalAuditor()
    # Skip full LLM run if not available, but check type
    result = auditor.PathNavigator(".")
    assert isinstance(result, PathNavigatorOutput)
    print(f"✓ Real PathNavigator called successfully")

if __name__ == "__main__":
    pytest.main([__file__])

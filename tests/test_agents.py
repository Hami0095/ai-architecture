import asyncio
import pytest
import os
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

@pytest.fixture
def auditor():
    return ArchitecturalAuditor()

@pytest.mark.asyncio
async def test_agent0_path_navigator(auditor):
    print("\nTesting PathNavigator...")
    result = auditor.PathNavigator(".")
    assert isinstance(result, PathNavigatorOutput)
    assert Path(result.resolved_path).is_absolute()
    assert result.exists_hint is True
    print(f"✓ Resolved path: {result.resolved_path}")

@pytest.mark.asyncio
async def test_agent1_discovery(auditor):
    print("\nTesting Discovery...")
    result = auditor.Discovery(".")
    assert isinstance(result, DiscoveryOutput)
    assert len(result.languages) > 0
    assert "python" in [l.lower() for l in result.languages]
    assert result.raw_structure is not None
    print(f"✓ Detected languages: {result.languages}")

@pytest.mark.asyncio
async def test_agent2_context_builder(auditor):
    print("\nTesting ContextBuilder...")
    # Mock discovery input
    discovery = DiscoveryOutput(
        languages=["python"],
        frameworks=["pytest"],
        architecture_type="Monolith",
        module_summary={"tests": "Testing module"},
        raw_structure="Project structure snippet"
    )
    result = auditor.ContextBuilder(discovery)
    assert isinstance(result, ContextBuilderOutput)
    assert hasattr(result, "dependencies")
    print(f"✓ Patterns found: {result.patterns}")

@pytest.mark.asyncio
async def test_agent3_gap_analyzer(auditor):
    print("\nTesting GapAnalyzer...")
    context = ContextBuilderOutput(dependencies=[], patterns=[], critical_paths=[])
    goals = {"expected_output": "A perfect testing system"}
    result = auditor.GapAnalyzer(context, goals)
    assert isinstance(result, GapAnalyzerOutput)
    assert len(result.markdown_report) > 0
    print(f"✓ Gap Report generated (length: {len(result.markdown_report)})")

@pytest.mark.asyncio
async def test_agent4_ticket_generator(auditor):
    print("\nTesting TicketGenerator...")
    gap = GapAnalyzerOutput(markdown_report="Missing unit tests for core logic.")
    result = auditor.TicketGenerator(gap)
    assert isinstance(result, TicketGeneratorOutput)
    # Even if 0 tickets, it should be the right type
    assert isinstance(result.tickets, list)
    print(f"✓ Tickets generated: {len(result.tickets)}")

@pytest.mark.asyncio
async def test_agent5_planner(auditor):
    print("\nTesting Planner...")
    tickets = [
        AuditTicket(title="Test Task", type="Logic", severity="High", description="Fix it", suggested_fix="Now", effort_hours=2)
    ]
    result = auditor.Planner(tickets)
    assert isinstance(result, PlannerOutput)
    assert len(result.sprint_plan) > 0
    assert result.sprint_plan[0].day == "Monday"
    print(f"✓ Sprint plan created for {len(result.sprint_plan)} days")

@pytest.mark.asyncio
async def test_agent6_auditor_verifier(auditor):
    print("\nTesting AuditorVerifier...")
    sprint_plan = [{"day": "Monday", "tickets": [], "total_hours": 0}]
    result = auditor.AuditorVerifier(sprint_plan)
    assert isinstance(result, AuditorVerifierOutput)
    assert result.summary is not None
    print(f"✓ Verification summary: {result.summary[:50]}...")

@pytest.mark.asyncio
async def test_full_orchestration_integrity(auditor):
    print("\nTesting Full Orchestration Integrity (E2E)...")
    # This calls the orchestrator via the auditor wrapper
    report = await auditor.audit_project(".", expected_output="Verify robust architecture")
    assert "tasks" in report
    assert "performance" in report
    assert "resolvedPath" in report["performance"]
    print("✓ Full Pipeline run successful")

if __name__ == "__main__":
    # Standard unittest style run if called directly
    pytest.main([__file__])

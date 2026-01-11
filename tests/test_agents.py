import asyncio
import pytest
from ai_architect.core_ai.auditor import ArchitecturalAuditor
from ai_architect.data.models import DiscoveryOutput, ContextBuilderOutput

@pytest.mark.asyncio
async def test_path_navigator():
    auditor = ArchitecturalAuditor()
    # Test with CWD
    result = auditor.PathNavigator(".")
    assert result.resolved_path is not None
    assert result.exists_hint is True

@pytest.mark.asyncio
async def test_discovery():
    auditor = ArchitecturalAuditor()
    result = auditor.Discovery(".")
    assert isinstance(result, DiscoveryOutput)
    assert len(result.languages) > 0

@pytest.mark.asyncio
async def test_full_pipeline_dry_run():
    # This might require a running Ollama
    auditor = ArchitecturalAuditor()
    try:
        report = await auditor.audit_project(".", expected_output="Verify current structure")
        assert "tasks" in report
        assert "performance" in report
    except Exception as e:
        pytest.fail(f"Pipeline failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_path_navigator())
    print("PathNavigator Test Passed")

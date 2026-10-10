"""ArchAI tools for AI agents (MCP): facts, citations, errors, and the real stdio protocol."""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from ai_architect.agents import tools
from ai_architect.agents.tools import ToolError
from ai_architect.standards.config import RULE_KINDS

FILES = {
    "app/__init__.py": "",
    "app/api.py": "from app import service\n",
    "app/service.py": "from app import repo\n\ndef helper():\n    from app import util\n",
    "app/repo.py": "import os\nfrom app import util\n",
    "app/util.py": "x = 1\n",
    "app/a.py": "from app import b\n",
    "app/b.py": "from app import a\n",
}


@pytest.fixture(autouse=True)
def dev_mode(monkeypatch):
    monkeypatch.setenv("ARCHAI_DEV_MODE", "1")


@pytest.fixture
def repo(make_repo):
    return make_repo(FILES)


def test_overview_reports_counts_and_coupling(repo):
    o = tools.atlas_graph_overview(str(repo), top=3)
    assert o["modules"] == 7 and o["packages"] == {"app": 7}
    assert {"module": "app.service", "imports": 2} in o["top_fan_out"]
    assert o["top_fan_in"][0] == {"module": "app.util", "imported_by": 2}


def test_module_lists_imports_and_importers_with_lines(repo):
    m = tools.atlas_module(str(repo), "app/service.py")  # paths work too
    assert m["module"] == "app.service" and m["file"] == "app/service.py"
    assert [(i["module"], i["line"], i["scope"]) for i in m["imports"]] == [("app.repo", 1, "module"), ("app.util", 4, "function")]
    assert [(i["module"], i["file"], i["line"]) for i in m["imported_by"]] == [("app.api", "app/api.py", 1)]


def test_import_path_cites_every_hop(repo):
    p = tools.atlas_import_path(str(repo), "app.api", "app.util")
    assert p["path"] == ["app.api", "app.service", "app.util"]
    assert [(h["file"], h["line"]) for h in p["hops"]] == [("app/api.py", 1), ("app/service.py", 4)]
    strict = tools.atlas_import_path(str(repo), "app.api", "app.util", include_deferred=False)
    assert strict["path"] == ["app.api", "app.service", "app.repo", "app.util"]
    none = tools.atlas_import_path(str(repo), "app.util", "app.api")
    assert none["path"] is None and "No import chain" in none["answer"]


def test_dependents_respect_depth(repo):
    d1 = tools.seismograph_dependents(str(repo), "app.util", max_depth=1)
    assert sorted(x["module"] for x in d1["dependents"]) == ["app.repo", "app.service"]
    d3 = tools.seismograph_dependents(str(repo), "app.util", max_depth=3)
    assert sorted(x["module"] for x in d3["dependents"]) == ["app.api", "app.repo", "app.service"]
    assert next(x for x in d3["dependents"] if x["module"] == "app.api")["depth"] == 2


def test_unknown_module_suggests_close_names(repo):
    with pytest.raises(ToolError, match="Did you mean: app.service"):
        tools.atlas_module(str(repo), "app.servce")
    with pytest.raises(ToolError, match="not a directory"):
        tools.atlas_graph_overview(str(repo / "missing"))


def test_check_standards_filters_and_trims(repo):
    cfg = repo / "archai_standards.yaml"
    cfg.write_text(yaml.safe_dump({"rules": [
        {"id": "no-cycles", "kind": "circular_dependency"},
        {"id": "fan", "kind": "coupling_threshold", "max": 0}]}), encoding="utf-8")
    r = tools.plumb_check_standards(str(repo), statuses=["VERIFIED_VIOLATION"], max_findings=2, max_evidence=1)
    assert r["exit_code"] == 1 and r["truncated"] is True
    findings = [f for rr in r["rule_results"] for f in rr["findings"]]
    assert len(findings) == 2 and all(f["status"] == "VERIFIED_VIOLATION" for f in findings)
    assert all(len(f["evidence"]) <= 1 and f["evidence_total"] >= 1 for f in findings)
    assert "how_to_read" in r and r["provenance"]["llm_used"] is False


def test_validate_config_and_reference():
    ok = tools.plumb_validate_config(config_yaml="rules:\n  - {id: c, kind: circular_dependency}\n")
    assert ok["valid"] and ok["rules"][0]["kind"] == "circular_dependency"
    bad = tools.plumb_validate_config(config_yaml="rules: [{id: x, kind: nope}]")
    assert not bad["valid"] and "unknown kind" in bad["error"]
    with pytest.raises(ToolError):
        tools.plumb_validate_config()
    assert set(tools.plumb_rule_reference()["kinds"]) == RULE_KINDS
    for kind in tools.plumb_rule_reference()["kinds"].values():  # every example is a valid rule
        assert tools.plumb_validate_config(config_yaml="layers: {infrastructure: [x], domain: [y]}\nrules:\n"
                                           + "\n".join("  " + l for l in kind["example"].splitlines()))["valid"]


def test_bundle_export_view_and_concept(repo, tmp_path):
    out = tools.atlas_export_bundle(str(repo), str(tmp_path / "bundle"))
    assert out["conformant_okf_v0_2"] and out["concepts"] > 7
    view = tools.atlas_view(out["bundle_dir"], "findings", status="violation")
    assert "FINDINGS (1)" in view["text"] and "\x1b[" not in view["text"]
    c = tools.atlas_concept(out["bundle_dir"], "app.service")
    assert c["type"] == "Python Module" and c["trust_tier"] == "unverified"
    assert any(l["target"] == "modules/app.repo" and l["exists"] for l in c["links"])
    with pytest.raises(ToolError):
        tools.atlas_view(out["bundle_dir"], "no-such-concept")


def test_foreman_maps_git_changes_to_modules(repo):
    git = lambda *a: subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True)
    git("init", "-q", "-b", "main")
    git("-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init")
    (repo / "app" / "util.py").write_text("x = 2\n", encoding="utf-8")
    (repo / "app" / "new.py").write_text("from app import util\n", encoding="utf-8")
    r = tools.foreman_changed_modules(str(repo), base="main", max_depth=1)
    assert r["changed_modules"] == ["app.new", "app.util"]
    assert {"app.repo", "app.service"} <= {d["module"] for d in r["dependents"]}


def test_ledger_reads_recorded_evidence(tmp_path):
    report = tmp_path / "archai_report.json"
    report.write_text(json.dumps({"tasks": [{"ticket_id": "T001", "title": "t",
                                             "evidence": {"file_path": "app/x.py"}}]}), encoding="utf-8")
    r = tools.ledger_trace("T001", str(report))
    assert r["evidence"] == {"file_path": "app/x.py"} and "not verified" in r["note"]
    with pytest.raises(ToolError, match="No Surveyor"):
        tools.ledger_trace("T001", str(tmp_path / "missing.json"))


def test_license_required_without_dev_mode(monkeypatch):
    monkeypatch.delenv("ARCHAI_DEV_MODE", raising=False)
    monkeypatch.delenv("ARCHAI_LICENSE", raising=False)
    with pytest.raises(ToolError, match="license MISSING"):
        tools.require_license()


# --- The real MCP stdio protocol --------------------------------------------------------

mcp = pytest.importorskip("mcp")


def _call(repo, steps, env_extra=None):
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    # Run the server from this checkout, not whatever an editable install points at.
    root = str(Path(__file__).resolve().parent.parent)
    env = {**os.environ, "ARCHAI_DEV_MODE": "1", "PYTHONPATH": root, **(env_extra or {})}
    if env_extra and env_extra.get("ARCHAI_DEV_MODE") == "":
        env.pop("ARCHAI_DEV_MODE")
    params = StdioServerParameters(command=sys.executable, args=["-m", "ai_architect.agents.mcp_server"],
                                   env=env, cwd=str(repo))

    async def go():
        async with Client(params) as client:
            return await steps(client)
    return asyncio.run(go())


def test_stdio_server_lists_and_runs_tools(repo):
    async def steps(client):
        listed = await client.list_tools()
        names = sorted(t.name for t in listed.tools)
        result = await client.call_tool("atlas_import_path", {"repo_path": str(repo), "source": "app.api",
                                                               "target": "app.util"})
        prompts = await client.list_prompts()
        return names, result, [p.name for p in prompts.prompts]

    names, result, prompts = _call(repo, steps)
    assert names == sorted(["plumb_check_standards", "plumb_validate_config", "plumb_rule_reference",
                            "atlas_graph_overview", "atlas_module", "atlas_import_path", "seismograph_dependents",
                            "foreman_changed_modules", "atlas_view", "atlas_concept", "ledger_trace",
                            "atlas_export_bundle"])
    assert not result.is_error
    assert result.structured_content["result"]["path"] == ["app.api", "app.service", "app.util"]
    assert json.loads(result.content[0].text)["path"] == ["app.api", "app.service", "app.util"]  # text-only clients
    assert prompts == ["archai_review"]


def test_stdio_server_reports_errors_as_tool_errors(repo):
    async def steps(client):
        return await client.call_tool("atlas_module", {"repo_path": str(repo), "module": "app.nope"})

    result = _call(repo, steps)
    assert result.is_error and "Unknown module" in result.content[0].text

    unlicensed = _call(repo, steps, env_extra={"ARCHAI_DEV_MODE": "", "ARCHAI_LICENSE": "bad.token"})
    assert unlicensed.is_error and "license INVALID" in unlicensed.content[0].text

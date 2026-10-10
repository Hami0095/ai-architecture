"""AGENT-SETUP and the ArchAI agent skill (Claude Code and Codex)."""
import re
import tomllib
from pathlib import Path

import pytest
import yaml

from ai_architect.agents import setup
from ai_architect.agents.tools import RULE_REFERENCE
from ai_architect.cli import process_command

SKILL = setup.SKILL_DIR / "SKILL.md"


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    return yaml.safe_load(text.split("---\n", 2)[1])


def test_skill_follows_the_open_agent_skills_format():
    fm = frontmatter(SKILL)
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fm["name"]) and len(fm["name"]) <= 64
    assert fm["name"] == SKILL.parent.name                      # name matches its folder
    assert 0 < len(fm["description"]) <= 1024
    assert len(SKILL.read_text(encoding="utf-8").splitlines()) < 500


def test_skill_mentions_every_mcp_tool_and_reference_is_current():
    from ai_architect.agents import mcp_server
    import asyncio
    names = {t.name for t in asyncio.run(mcp_server.build_server().list_tools())}
    body = SKILL.read_text(encoding="utf-8")
    assert all(f"`{n}`" in body for n in names), sorted(n for n in names if f"`{n}`" not in body)
    reference = (setup.SKILL_DIR / "reference.md").read_text(encoding="utf-8")
    for kind, spec in RULE_REFERENCE["kinds"].items():
        assert f"### `{kind}`" in reference and spec["example"] in reference


def test_prints_commands_without_writing_or_leaking_the_token(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("ARCHAI_LICENSE", "secret.token")
    monkeypatch.setattr(setup.Path, "home", lambda: tmp_path)
    assert setup.agent_setup([]) == 0
    out = capsys.readouterr().out
    assert "claude mcp add archai --scope user -e ARCHAI_LICENSE=YOUR_TOKEN --" in out
    assert "codex mcp add archai --env ARCHAI_LICENSE=YOUR_TOKEN --" in out
    assert "secret.token" not in out
    assert not any(tmp_path.iterdir())


def test_codex_toml_snippet_is_valid_toml(monkeypatch):
    monkeypatch.setattr(setup, "server_command", lambda: [r"C:\Program Files\Py\python.exe", "-m", "ai_architect.agents.mcp_server"])
    data = tomllib.loads(setup.codex_toml({"ARCHAI_DEV_MODE": "1"}))["mcp_servers"]["archai"]
    assert data == {"command": r"C:\Program Files\Py\python.exe", "args": ["-m", "ai_architect.agents.mcp_server"],
                    "env": {"ARCHAI_DEV_MODE": "1"}}


def test_install_skill_for_both_agents_and_protect_edits(tmp_path, capsys):
    assert setup.agent_setup(["--install-skill", "--scope", "project", "--project", str(tmp_path)]) == 0
    for home in (".claude/skills/archai", ".agents/skills/archai"):
        assert (tmp_path / home / "SKILL.md").read_bytes() == SKILL.read_bytes()
        assert (tmp_path / home / "reference.md").exists()
    edited = tmp_path / ".claude/skills/archai/SKILL.md"
    edited.write_text("my local edits", encoding="utf-8")
    assert setup.agent_setup(["--install-skill", "--scope", "project", "--project", str(tmp_path), "--agent", "claude"]) == 2
    assert "use --force" in capsys.readouterr().out and edited.read_text(encoding="utf-8") == "my local edits"
    assert setup.agent_setup(["--install-skill", "--scope", "project", "--project", str(tmp_path), "--agent", "claude", "--force"]) == 0
    assert edited.read_bytes() == SKILL.read_bytes()


def test_register_runs_agent_clis(monkeypatch, capsys):
    monkeypatch.delenv("ARCHAI_LICENSE", raising=False)
    monkeypatch.setenv("ARCHAI_DEV_MODE", "1")
    calls = []
    monkeypatch.setattr(setup.shutil, "which", lambda name: f"/bin/{name}" if name in ("claude", "codex") else None)
    monkeypatch.setattr(setup.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})())
    assert setup.agent_setup(["--register"]) == 0
    assert calls[0][:4] == ["/bin/claude", "mcp", "add", "archai"] and "ARCHAI_DEV_MODE=1" in calls[0]
    assert calls[1][:4] == ["/bin/codex", "mcp", "add", "archai"] and calls[1][-2:] == ["-m", "ai_architect.agents.mcp_server"]


def test_register_needs_credentials(monkeypatch, capsys):
    monkeypatch.delenv("ARCHAI_LICENSE", raising=False)
    monkeypatch.delenv("ARCHAI_DEV_MODE", raising=False)
    assert setup.agent_setup(["--register"]) == 2
    assert "set ARCHAI_LICENSE" in capsys.readouterr().out


def test_cli_dispatch_and_usage(capsys):
    assert process_command(["AGENT-SETUP", "--agent", "codex"]) == 0
    assert "Register with Codex" in capsys.readouterr().out
    assert process_command(["AGENT-SETUP", "--agent", "nope"]) == 2

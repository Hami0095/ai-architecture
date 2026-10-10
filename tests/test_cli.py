"""Console command dispatcher: tokenizing, return codes, and command routing."""
import pytest

from ai_architect import cli
from ai_architect.cli import process_command, split_command


def test_process_command_accepts_tokens_and_reports_syntax_errors(capsys):
    assert process_command(["HELP"]) is None
    assert "COMMAND" in capsys.readouterr().out
    assert process_command("") is None
    assert process_command('CHECK-STANDARDS "unterminated') == 2


@pytest.mark.skipif("os.name != 'nt'")
def test_windows_paths_keep_backslashes():
    assert split_command(r'CHECK-STANDARDS C:\repo\app --json "C:\out dir\r.json"') == \
        ["CHECK-STANDARDS", r"C:\repo\app", "--json", r"C:\out dir\r.json"]


def test_sprint_planning_commands_are_deferred(monkeypatch, capsys):
    monkeypatch.delenv("ARCHAI_ENABLE_LEGACY_PLANNING", raising=False)
    for command in ("PLAN . goal", "SIMULATE T001", "RELEASE-CONFIDENCE . v2"):
        assert process_command(command) == 2
        assert "deferred" in capsys.readouterr().out


@pytest.mark.parametrize("value, state", [
    (None, "not configured"),
    ("", "not configured"),
    ("your-github-token", "placeholder value"),
    ("<token>", "placeholder value"),
    ("ghp_real", "configured"),
])
def test_credential_state_reports_presence_only(value, state):
    assert cli._credential_state(value) == state

"""Console theme: orange only on real terminals, ASCII fallbacks, quiet spinners when piped."""
import io
import sys

import pytest

from ai_architect.utils import console_utils
from ai_architect.utils.console_utils import ConsoleUI


class FakeTTY(io.StringIO):
    def __init__(self, encoding="utf-8"):
        super().__init__()
        self._encoding = encoding

    @property
    def encoding(self):
        return self._encoding

    def isatty(self):
        return True


@pytest.fixture
def no_color_env(monkeypatch):
    for var in ("NO_COLOR", "FORCE_COLOR", "COLORTERM", "WT_SESSION", "TERM_PROGRAM"):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def test_plain_text_when_output_is_not_a_terminal(no_color_env, capsys):
    assert ConsoleUI.accent("CHECK-STANDARDS") == "CHECK-STANDARDS"
    ConsoleUI.banner()
    out = capsys.readouterr().out
    assert "\x1b[" not in out
    assert console_utils.TAGLINE in out


def test_no_color_wins_over_terminal(no_color_env):
    no_color_env.setenv("NO_COLOR", "1")
    no_color_env.setattr(sys, "stdout", FakeTTY())
    assert ConsoleUI.accent("x") == "x"


def test_orange_on_a_terminal(no_color_env):
    no_color_env.setattr(sys, "stdout", FakeTTY())
    no_color_env.setattr(console_utils, "_enable_windows_vt", lambda: True)
    assert ConsoleUI.accent("x") == "\x1b[1m\x1b[38;5;208mx\x1b[0m"          # 256-color fallback
    no_color_env.setenv("COLORTERM", "truecolor")
    assert "\x1b[38;2;255;122;26m" in ConsoleUI.accent("x")                  # exact ArchAI orange


def test_ascii_logo_on_legacy_code_pages(no_color_env, monkeypatch):
    out = FakeTTY(encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", out)
    ConsoleUI.banner()
    text = out.getvalue()
    assert "█" not in text and "/_/  |_/_/" in text
    text.encode("cp1252")  # everything printed is representable


def test_spinner_prints_once_when_piped(capsys):
    with ConsoleUI.spinner("Mapping dependencies"):
        pass
    out = capsys.readouterr().out
    assert out == "  Mapping dependencies...\n"


def test_spinner_animates_and_clears_on_a_terminal(no_color_env, monkeypatch):
    out = FakeTTY()
    monkeypatch.setattr(sys, "stdout", out)
    import time
    with ConsoleUI.spinner("Thinking"):
        time.sleep(0.25)
    text = out.getvalue()
    assert "Thinking" in text and "⠋" in text and "s" in text
    assert text.endswith("\r")  # line cleared after the work finishes

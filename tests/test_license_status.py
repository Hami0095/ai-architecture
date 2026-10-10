"""License validation, the startup gate, and the IDENTITY/MODE/LICENSE banner."""
import sys

import pytest

from ai_architect import cli
from ai_architect.utils.license import LicenseManager


@pytest.fixture
def clean_env(monkeypatch):
    for var in ("ARCHAI_LICENSE", "ARCHAI_DEV_MODE", "ARCHAI_TEST_MODE", "ARCHAI_ENABLE_LEGACY_PLANNING",
                "ARCHAI_ENABLE_SPRINT_PLANNING"):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def test_long_lived_token_is_valid_and_formats_on_windows():
    # datetime.fromtimestamp raises OSError on Windows past year 3000; this used
    # to make a valid token show as EXPIRED/INVALID and crash --check-token.
    token = LicenseManager.generate_token("owner", days=999_999)
    info = LicenseManager.inspect_token(token)
    assert info["state"] == "VALID" and info["user"] == "owner"
    assert info["expires"].startswith("47")
    assert LicenseManager.get_token_info(token).startswith("Valid pilot license for owner")


@pytest.mark.parametrize("token, state", [
    (None, "MISSING"),
    ("", "MISSING"),
    ("not-a-token", "INVALID"),
    (LicenseManager.generate_token("x", days=1)[:-3] + "AAA", "INVALID"),
    (LicenseManager.generate_token("x", days=-1), "EXPIRED"),
])
def test_token_states(token, state):
    assert LicenseManager.inspect_token(token)["state"] == state


def test_identity_comes_from_license_holder(clean_env):
    clean_env.setenv("ARCHAI_LICENSE", LicenseManager.generate_token("Hami0095", days=30))
    st = cli.session_status()
    assert st["identity"] == "Hami0095" and st["identity_source"] == "license holder"
    assert st["access_mode"] == "LICENSED" and st["flags"] == []
    assert st["license"]["days_left"] in (29, 30)


def test_dev_mode_and_flags(clean_env):
    clean_env.setenv("ARCHAI_DEV_MODE", "1")
    clean_env.setenv("ARCHAI_TEST_MODE", "1")
    clean_env.setenv("ARCHAI_ENABLE_SPRINT_PLANNING", "1")
    st = cli.session_status()
    assert st["access_mode"] == "DEV"
    assert st["flags"] == ["DEMO", "SPRINT-PLANNING"]
    assert "unlicensed" in st["identity_source"]


def _run_cli(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["ai-architect", *argv])
    monkeypatch.setattr("builtins.input", lambda prompt="": "exit")
    cli.run_cli()


def test_banner_shows_valid_license(clean_env, capsys):
    token = LicenseManager.generate_token("Hami0095", days=999_999)
    _run_cli(clean_env, "--license", token)
    out = capsys.readouterr().out
    assert " IDENTITY: Hami0095 (license holder)" in out
    assert " MODE: LICENSED | PROFILE:" in out
    assert " LICENSE: VALID - Hami0095, expires 47" in out
    assert "EXPIRED/INVALID" not in out


def test_gate_rejects_expired_token_in_environment(clean_env, capsys):
    clean_env.setenv("ARCHAI_LICENSE", LicenseManager.generate_token("old", days=-1))
    with pytest.raises(SystemExit) as exc:
        _run_cli(clean_env)
    assert exc.value.code == 3
    assert "License EXPIRED" in capsys.readouterr().out


def test_dev_mode_banner(clean_env, capsys):
    clean_env.setenv("ARCHAI_DEV_MODE", "1")
    _run_cli(clean_env, "--test-mode")
    out = capsys.readouterr().out
    assert " MODE: DEV + DEMO |" in out
    assert " LICENSE: MISSING - " in out

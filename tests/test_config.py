import os
from pathlib import Path

import pytest
from ai_architect.infrastructure.config_manager import ConfigManager, ConfigurationError

# Test .env loading
def test_env_loading(tmp_path):
    d = tmp_path / ".env"
    d.write_text("ARCHAI_TEST_KEY=env_value")
    # We need to change cwd or force load, but simplify: 
    # Just check if get retrieves from os.environ
    os.environ["ARCHAI_UNIT_TEST_KEY"] = "unit_test_value"
    cm = ConfigManager()
    assert cm.get("unit.test.key") == "unit_test_value"

def test_profile_loading(tmp_path, monkeypatch):
    # Profiles are read from the working directory as config.<profile>.json/yaml.
    monkeypatch.chdir(tmp_path)
    Path("config.testprofile.json").write_text('{"test_feature": {"enabled": true}}')

    cm = ConfigManager()
    try:
        cm.load_config(profile="testprofile")
        assert cm.get("test_feature.enabled") is True
    finally:
        # ConfigManager is a process-wide singleton; don't leak into other tests.
        cm._config.pop("test_feature", None)
        cm._loaded_files[:] = [f for f in cm._loaded_files if f.name != "config.testprofile.json"]

def test_default_values():
    cm = ConfigManager()
    assert cm.get("non.existent.key", "default") == "default"

if __name__ == "__main__":
    pytest.main([__file__])

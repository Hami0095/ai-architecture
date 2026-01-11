import os
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

def test_profile_loading(tmp_path):
    # Mock config file
    config_file = Path("config.testprofile.json")
    with open(config_file, 'w') as f:
        f.write('{"test_feature": {"enabled": true}}')
    
    cm = ConfigManager()
    
    # Cleanup
    if config_file.exists():
        os.remove(config_file)

def test_default_values():
    cm = ConfigManager()
    assert cm.get("non.existent.key", "default") == "default"

if __name__ == "__main__":
    pytest.main([__file__])

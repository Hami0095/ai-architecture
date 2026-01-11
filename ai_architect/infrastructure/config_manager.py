import os
import json
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from .logging_utils import logger, ConfigurationError

class ConfigManager:
    """Manages system configuration from files and environment variables."""
    
    _instance = None
    _config: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance

    def load_config(self, config_path: Optional[str] = None):
        """Loads configuration from a YAML or JSON file."""
        # Default paths
        search_paths = [
            Path(config_path) if config_path else None,
            Path("archai_config.yaml"),
            Path("archai_config.json"),
            Path.home() / ".archai" / "config.yaml"
        ]

        for path in filter(None, search_paths):
            if path.exists():
                try:
                    if path.suffix in ['.yaml', '.yml']:
                        with open(path, 'r') as f:
                            self._config = yaml.safe_load(f) or {}
                    elif path.suffix == '.json':
                        with open(path, 'r') as f:
                            self._config = json.load(f)
                    logger.info(f"Configuration loaded from {path}")
                    return self._config
                except Exception as e:
                    logger.error(f"Failed to load config from {path}: {e}")
                    raise ConfigurationError(f"Malformed config file: {path}")

        logger.warning("No configuration file found. Using defaults.")
        return self._config

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a config value, checking env vars first."""
        # Check environment variable (ARCHAI_KEY_NAME)
        env_key = f"ARCHAI_{key.upper().replace('.', '_')}"
        if env_key in os.environ:
            return os.environ[env_key]
        
        # Check dictionary
        keys = key.split('.')
        val = self._config
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

# Singleton instance
config = ConfigManager()

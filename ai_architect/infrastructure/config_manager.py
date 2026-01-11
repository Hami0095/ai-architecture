import os
import json
import yaml
from pathlib import Path
from typing import Any, Dict, Optional, List
from dotenv import load_dotenv
from .logging_utils import logger, ConfigurationError

class ConfigManager:
    """Manages system configuration from files, environment variables, and profiles."""
    
    _instance = None
    _config: Dict[str, Any] = {}
    _loaded_files: List[Path] = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._init_manager()
        return cls._instance

    def _init_manager(self):
        """Initializes the manager, loading .env by default."""
        load_dotenv() # Load from .env if present
        env = os.getenv("ARCHAI_ENV", "dev").lower()
        self.load_config(profile=env)

    def load_config(self, config_path: Optional[str] = None, profile: Optional[str] = None):
        """
        Loads configuration from YAML/JSON files.
        If profile is provided, it tries to load config.{profile}.yaml.
        """
        search_paths = []
        
        # 1. Direct path if provided
        if config_path:
            search_paths.append(Path(config_path))
            
        # 2. Profile-specific config (e.g. config.prod.yaml)
        if profile:
            search_paths.append(Path(f"config.{profile}.yaml"))
            search_paths.append(Path(f"config.{profile}.json"))

        # 3. Base defaults
        search_paths.extend([
            Path("archai_config.yaml"),
            Path("archai_config.json"),
            Path.home() / ".archai" / "config.yaml"
        ])

        for path in search_paths:
            if path and path.exists() and path not in self._loaded_files:
                try:
                    loaded_data = {}
                    if path.suffix in ['.yaml', '.yml']:
                        with open(path, 'r') as f:
                            loaded_data = yaml.safe_load(f) or {}
                    elif path.suffix == '.json':
                        with open(path, 'r') as f:
                            loaded_data = json.load(f)
                    
                    # Deep merge or simple update? Simple update for now
                    self._config.update(loaded_data)
                    self._loaded_files.append(path)
                    logger.info(f"Configuration profile/file loaded: {path}")
                except Exception as e:
                    logger.error(f"Failed to load config from {path}: {e}")
                    raise ConfigurationError(f"Malformed config file: {path}")

        return self._config

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a config value, checking env vars first."""
        # 1. Check environment variable (ARCHAI_KEY_NAME)
        env_key = f"ARCHAI_{key.upper().replace('.', '_')}"
        if env_key in os.environ:
            return os.environ[env_key]
        
        # 2. Check layered dictionary config
        keys = key.split('.')
        val = self._config
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    def get_secret(self, key: str) -> Optional[str]:
        """Specific getter for secrets, ensuring they aren't accidentally logged."""
        val = self.get(key)
        if not val:
            logger.warning(f"Secret '{key}' not found in configuration or environment.")
        return val

# Singleton instance
config = ConfigManager()

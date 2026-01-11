"""
Centralized Global Variables for ArchAI.
Exposes configuration values initialized from environment and config files.
"""

from .config_manager import config

# AI Model settings
AI_MODEL = config.get("model", "glm-4.6:cloud")
AI_PROVIDER = config.get("ai.provider", "ollama")

# Infrastructure settings
DB_URL = config.get("database.url", "sqlite:///archai_data.db")
CACHE_TYPE = config.get("cache.type", "local") # 'local' or 'redis'
REDIS_URL = config.get("redis.url", "redis://localhost:6379/0")

# Security & API Keys (Secrets)
OLLAMA_HOST = config.get("ollama.host", "http://localhost:11434")

# Environmental context
ENV = config.get("env", "dev")
VERBOSE = config.get("verbose", False)

def reload_globals():
    """Reloads variables if config changes at runtime."""
    global AI_MODEL, AI_PROVIDER, DB_URL, CACHE_TYPE, REDIS_URL, ENV
    AI_MODEL = config.get("model", "glm-4.6:cloud")
    AI_PROVIDER = config.get("ai.provider", "ollama")
    DB_URL = config.get("database.url", "sqlite:///archai_data.db")
    CACHE_TYPE = config.get("cache.type", "local")
    REDIS_URL = config.get("redis.url", "redis://localhost:6379/0")
    ENV = config.get("env", "dev")

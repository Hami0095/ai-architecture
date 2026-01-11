from typing import Optional
from .base import BaseAIModel
from .ollama_model import OllamaModel
from ..infrastructure.config_manager import config

def get_model(provider: Optional[str] = None, model_name: Optional[str] = None) -> BaseAIModel:
    """
    Factory function to retrieve a model instance.
    Defaults to values in the global config.
    """
    provider = provider or config.get("ai.provider", "ollama")
    model_name = model_name or config.get("model", "qwen3-coder:480b-cloud")
    
    if provider.lower() == "ollama":
        return OllamaModel(model_name)
    else:
        # Fallback or future providers (OpenAI, Anthropic, etc.)
        raise ValueError(f"Unsupported AI provider: {provider}")

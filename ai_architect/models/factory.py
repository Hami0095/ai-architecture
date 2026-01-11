from typing import Optional
from .base import BaseAIModel
from .ollama_model import OllamaModel
from ..infrastructure.globals import AI_PROVIDER, AI_MODEL

def get_model(provider: Optional[str] = None, model_name: Optional[str] = None) -> BaseAIModel:
    """
    Factory function to retrieve a model instance.
    """
    provider = provider or AI_PROVIDER
    model_name = model_name or AI_MODEL
    
    if provider.lower() == "ollama":
        return OllamaModel(model_name)
    else:
        # Fallback or future providers (OpenAI, Anthropic, etc.)
        raise ValueError(f"Unsupported AI provider: {provider}")

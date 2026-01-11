import json
import ollama
from typing import List, Dict, Any, Optional
from .base import BaseAIModel
from ..infrastructure.logging_utils import logger

class OllamaModel(BaseAIModel):
    """
    Concrete implementation of BaseAIModel using the Ollama library.
    """
    
    def chat(self, messages: List[Dict[str, str]], format: Optional[str] = None) -> str:
        """
        Interacts with Ollama and handles response parsing.
        """
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=messages,
                format=format if format == 'json' else ''
            )
            content = response['message']['content']
            
            # If we requested JSON but the model didn't use the 'format' param (legacy models),
            # we might need to strip markdown backticks.
            if format == 'json' and "```" in content:
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                else:
                    content = content.split("```")[1].split("```")[0].strip()
                    
            return content
        except Exception as e:
            logger.error(f"Ollama Model Error ({self.model_name}): {e}")
            raise

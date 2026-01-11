import json
import ollama
from typing import List, Dict, Any, Optional
from .base import BaseAIModel
from ..infrastructure.logging_utils import logger, retry, LLMProviderError

class OllamaModel(BaseAIModel):
    """
    Concrete implementation of BaseAIModel using the Ollama library.
    """
    
    @retry(retries=3, delay=2.0, backoff=2.0, exceptions=(Exception,))
    def chat(self, messages: List[Dict[str, str]], format: Optional[str] = None) -> str:
        """
        Interacts with Ollama and handles response parsing.
        Includes automatic retries for transient failures.
        """
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=messages,
                format=format if format == 'json' else ''
            )
            content = response['message']['content']
            
            # Legacy/Fallback JSON parsing
            if format == 'json' and "```" in content:
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                else:
                    content = content.split("```")[1].split("```")[0].strip()
                    
            return content
        except Exception as e:
            logger.error(f"Ollama Provider Error ({self.model_name}): {e}")
            raise LLMProviderError(f"Ollama failed: {str(e)}")

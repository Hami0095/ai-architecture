from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseAIModel(ABC):
    """
    Abstract base class for all AI model providers.
    """
    
    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], format: Optional[str] = None) -> str:
        """
        Sends a list of messages to the model and returns the response content.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'.
            format: Optional format specification (e.g., 'json').
            
        Returns:
            The text content of the model's response.
        """
        pass

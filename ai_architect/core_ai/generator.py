from typing import Optional
from .prompts import BASE_SYSTEM_PROMPT
from ..models.base import BaseAIModel
from ..models.factory import get_model

class CoreAI:
    def __init__(self, model: Optional[BaseAIModel] = None, system_prompt=BASE_SYSTEM_PROMPT):
        self.model = model or get_model()
        self.system_prompt = system_prompt

    def update_prompt(self, new_prompt):
        """Updates the system prompt dynamically based on improvements."""
        self.system_prompt = new_prompt
        print(f"CoreAI: System prompt updated.")

    def generate_tests(self, target_code: str) -> str:
        """
        Generates pytest code for the given target code.
        """
        try:
            content = self.model.chat(
                messages=[
                    {'role': 'system', 'content': self.system_prompt},
                    {'role': 'user', 'content': f"Generate pytest tests for the following code:\n\n{target_code}"}
                ]
            )
            
            # Basic cleanup if the model creates markdown blocks
            if "```python" in content:
                content = content.split("```python")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            return content
        except Exception as e:
            print(f"CoreAI Error: {e}")
            return ""

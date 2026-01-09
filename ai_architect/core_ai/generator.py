import ollama
from .prompts import BASE_SYSTEM_PROMPT

class CoreAI:
    def __init__(self, model="qwen3-coder:480b-cloud", system_prompt=BASE_SYSTEM_PROMPT):
        self.model = model
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
            response = ollama.chat(model=self.model, messages=[
                {'role': 'system', 'content': self.system_prompt},
                {'role': 'user', 'content': f"Generate pytest tests for the following code:\n\n{target_code}"}
            ])
            # Basic cleanup if the model creates markdown blocks
            content = response['message']['content']
            if "```python" in content:
                content = content.split("```python")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            return content
        except Exception as e:
            print(f"Error calling Ollama: {e}")
            return ""

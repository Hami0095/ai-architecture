import ollama
from ..core_ai.prompts import RECONCILER_SYSTEM_PROMPT
from ..data.models import ImprovementSuggestion, ReconciliationResult

class Reconciler:
    def __init__(self, model="gemma3:1b"):
        self.model = model

    def reconcile(self, suggestions: list[ImprovementSuggestion]) -> ReconciliationResult:
        """
        Selects the best strategy using LLM.
        """
        options_text = ""
        for i, s in enumerate(suggestions):
            options_text += f"Option {i+1}: {s.strategy_name}\nDescription: {s.description}\nXAI: {s.xai_explanation}\n\n"
            
        prompt = f"""
        Review the following improvement options and select the best one.
        
        {options_text}
        
        Output just the Option Number and the Rationale.
        """
        
        response = ollama.chat(model=self.model, messages=[
            {'role': 'system', 'content': RECONCILER_SYSTEM_PROMPT},
            {'role': 'user', 'content': prompt}
        ])
        
        decision_text = response['message']['content']
        
        # Simple parsing logic (in production we'd use structured output again)
        # Assuming the LLM follows instructions reasonably well.
        # We will map back to the object.
        selected = suggestions[0] # Default fallback
        
        if "Option 2" in decision_text:
            selected = suggestions[1]
        elif "Option 3" in decision_text and len(suggestions) > 2:
            selected = suggestions[2]
            
        return ReconciliationResult(
            selected_strategy=selected.strategy_name,
            rationale=decision_text
        )

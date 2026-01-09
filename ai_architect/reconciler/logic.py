import ollama
import json
from ..core_ai.prompts import RECONCILER_SYSTEM_PROMPT
from ..data.models import ImprovementSuggestion, ReconciliationResult

class Reconciler:
    def __init__(self, model="qwen3-coder:480b-cloud"):
        self.model = model

    def reconcile(self, suggestions: list[ImprovementSuggestion]) -> ReconciliationResult:
        """
        Selects the best strategy from suggestions using LLM reasoning.
        """
        # Prepare context for LLM
        strategies_text = ""
        for i, s in enumerate(suggestions):
            strategies_text += f"\nStrategy {i+1}: {s.strategy_name}\nDescription: {s.description}\nXAI: {s.xai_explanation}\n"

        prompt = f"""
        Available Strategies:
        {strategies_text}
        
        Analyze these recommendations and select the best one. 
        Focus on high impact with manageable risk.
        Return ONLY valid JSON with keys: 'selected_strategy', 'rationale'.
        """

        try:
            response = ollama.chat(model=self.model, format='json', messages=[
                {'role': 'system', 'content': RECONCILER_SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt}
            ])
            
            content = response['message']['content']
            # Basic cleanup for JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            data = json.loads(content)
            
            return ReconciliationResult(
                selected_strategy=data.get('selected_strategy', suggestions[0].strategy_name),
                rationale=data.get('rationale', "Model selected this as the highest impact strategy.")
            )
        except Exception as e:
            print(f"Reconciler Error: {e}")
            # Fallback to first suggestion if LLM fails
            return ReconciliationResult(
                selected_strategy=suggestions[0].strategy_name,
                rationale="Fallback to first suggestion due to internal error."
            )

import ollama
import json
from typing import List, Any
from ..core_ai.prompts import IMPROVEMENT_SYSTEM_PROMPT
from ..data.models import ImprovementSuggestion
from ..xai.explainer import XAI

class ImprovementEngine:
    def __init__(self, model="qwen3-coder:480b-cloud"):
        self.model = model
        self.xai = XAI(model=model)

    def generate_suggestions(self, source_code, failure_details) -> list[ImprovementSuggestion]:
        """
        Analyzes metrics and generates 3 improvement strategies with XAI explanations.
        """
        prompt = f"""
        Source Code:
        {source_code}
        
        Failure Details:
        {failure_details}
        
        Provide 3 distinct improvement strategies in JSON.
        """
        
        try:
            response = ollama.chat(model=self.model, format='json', messages=[
                {'role': 'system', 'content': IMPROVEMENT_SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt}
            ])
            
            # Parse JSON
            content = response['message']['content']
            # Basic cleanup for JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            data = json.loads(content)
            strategies_data = data.get('strategies', [])
            
            suggestions = []
            for s in strategies_data:
                # Generate XAI for each
                explanation = self.xai.explain_suggestion(s['description'], failure_details)
                
                s_obj = ImprovementSuggestion(
                    strategy_name=s['name'],
                    description=s['description'],
                    suggested_prompt_modification=s.get('prompt_change'),
                    suggested_code_example=s.get('code_example'),
                    xai_explanation=explanation
                )
                suggestions.append(s_obj)
                
            return suggestions
            
        except Exception as e:
            print(f"Improvement Engine Error: {e}")
            # Ensure response is defined before access to avoid further errors
            return []
class ProactiveStabilityAnalyzer:
    def __init__(self, model="qwen3-coder:480b-cloud"):
        self.model = model

    def analyze_stability_risks(self, agent_history: List[Any]) -> List[str]:
        """
        Analyzes agent history (latency, errors) to predict potential stability failures.
        """
        history_summary = "\n".join([f"{r.agent_name}: {'Success' if r.success else 'Failed'} ({r.latency_ms}ms)" for r in agent_history])
        
        prompt = f"""
        Recent Agent Execution History:
        {history_summary}
        
        Identify potential cascading risks or performance bottlenecks.
        Return a list of 3-5 stability recommendations.
        """
        
        try:
            response = ollama.chat(model=self.model, messages=[
                {'role': 'system', 'content': "You are an AI Stability Monitor."},
                {'role': 'user', 'content': prompt}
            ])
            return response['message']['content'].split('\n')
        except:
            return ["Maintain current resource limits.", "Monitor upstream latency."]

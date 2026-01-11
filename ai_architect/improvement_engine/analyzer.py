import json
from typing import List, Any, Optional
from ..core_ai.prompts import IMPROVEMENT_SYSTEM_PROMPT
from ..data.models import ImprovementSuggestion
from ..xai.explainer import XAI
from ..models.base import BaseAIModel
from ..models.factory import get_model

class ImprovementEngine:
    def __init__(self, model: Optional[BaseAIModel] = None):
        self.model = model or get_model()
        self.xai = XAI(model=self.model)

    def generate_suggestions(self, source_code, failure_details) -> List[ImprovementSuggestion]:
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
            content = self.model.chat(
                messages=[
                    {'role': 'system', 'content': IMPROVEMENT_SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt}
                ],
                format='json'
            )
            
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
            return []

class ProactiveStabilityAnalyzer:
    def __init__(self, model: Optional[BaseAIModel] = None):
        self.model = model or get_model()

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
            content = self.model.chat(
                messages=[
                    {'role': 'system', 'content': "You are an AI Stability Monitor."},
                    {'role': 'user', 'content': prompt}
                ]
            )
            return content.split('\n')
        except Exception as e:
            print(f"Stability Analyzer Error: {e}")
            return ["Maintain current resource limits.", "Monitor upstream latency."]

from typing import Optional
from ..core_ai.prompts import XAI_SYSTEM_PROMPT
from ..models.base import BaseAIModel
from ..models.factory import get_model

class XAI:
    def __init__(self, model: Optional[BaseAIModel] = None):
        self.model = model or get_model()

    def explain_suggestion(self, suggestion, failure_context):
        """
        Generates an explanation for why a suggestion helps.
        """
        prompt = f"""
        Context: The previous test generation failed.
        Failure Details: {failure_context}
        Suggestion: {suggestion}
        
        Explain WHY this suggestion will fix the issue and estimate its impact.
        """
        content = self.model.chat(
            messages=[
                {'role': 'system', 'content': XAI_SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt}
            ]
        )
        return content

    def explain_decision(self, chosen_strategy, alternatives):
        """
        Explains why one strategy was chosen over others.
        """
        prompt = f"""
        Chosen Strategy: {chosen_strategy}
        Alternatives: {alternatives}
        
        Explain the reasoning for this choice, highlighting advantages over the alternatives.
        """
        content = self.model.chat(
            messages=[
                {'role': 'system', 'content': XAI_SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt}
            ]
        )
        return content

from enum import Enum

class StrategyType(Enum):
    PROMPT_MODIFICATION = "prompt_modification"
    CODE_EXAMPLE = "code_example"
    FEW_SHOT_LEARNING = "few_shot_learning"
    CHAIN_OF_THOUGHT = "chain_of_thought"
    CONSTRAINT_RELAXATION = "constraint_relaxation"

class ImprovementStrategy:
    """
    Base class for improvement strategies if we want to implement rule-based ones later.
    """
    def apply(self, core_ai_instance):
        raise NotImplementedError

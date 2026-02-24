"""
AI Service — stub for future LLM integration (e.g. Claude API via Anthropic SDK).
All AI features should be routed through this service.

Planned features:
- Workout summary: generate a natural language summary of a completed workout
- Program feedback: analyse a full program and give coaching notes
- Progress insights: spot trends in PR history and volume over time
- Autoregulation suggestions: recommend weight adjustments based on RPE logs
- Program generation: suggest a new program based on goals and history
"""


class AIService:
    def __init__(self) -> None:
        # Future: load API key from env, initialise Anthropic client here
        pass

    async def summarise_workout(self, workout_data: dict) -> str:
        # Future: send workout to Claude, return summary string
        raise NotImplementedError("AI service not yet configured")

    async def analyse_program(self, program_data: dict) -> str:
        raise NotImplementedError("AI service not yet configured")

    async def progress_insights(self, pr_history: dict, volume_history: dict) -> str:
        raise NotImplementedError("AI service not yet configured")

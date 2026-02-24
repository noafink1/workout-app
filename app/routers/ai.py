"""
AI router — stub for future LLM integration.
No active endpoints yet. Planned endpoints:
  POST /ai/summarise-workout
  POST /ai/programme-feedback
  GET  /ai/insights
"""
from fastapi import APIRouter

router = APIRouter(prefix="/ai", tags=["ai"])

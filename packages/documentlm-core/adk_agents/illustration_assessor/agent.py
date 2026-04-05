"""ADK web wrapper for Illustration Assessor — exposes root_agent for `adk web`."""

from documentlm_core.agents.illustration_assessor import _ASSESSMENT_INSTRUCTION
from documentlm_core.config import settings
from google.adk.agents import Agent

root_agent = Agent(
    name="illustration_assessor",
    model=settings.gemini_model,
    instruction=_ASSESSMENT_INSTRUCTION,
)

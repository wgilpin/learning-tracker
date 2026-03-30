"""ADK web wrapper for Syllabus Architect — exposes root_agent for `adk web`."""

from google.adk.agents import Agent

from documentlm_core.agents.syllabus_architect import _INSTRUCTION
from documentlm_core.config import settings

root_agent = Agent(
    name="syllabus_architect",
    model=settings.gemini_model,
    instruction=_INSTRUCTION,
)

"""ADK web wrapper for Chapter Scribe — exposes root_agent for `adk web`."""

from google.adk.agents import Agent

from documentlm_core.agents.chapter_scribe import _CHAPTER_INSTRUCTION, _COMMENT_INSTRUCTION
from documentlm_core.config import settings

root_agent = Agent(
    name="chapter_scribe",
    model=settings.gemini_model,
    instruction=_CHAPTER_INSTRUCTION,
)

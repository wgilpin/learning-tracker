"""Illustration Assessor: determines whether a paragraph needs an illustration.

Uses the text generation model (settings.gemini_model) via Google ADK.
Returns a ParagraphAssessment indicating whether an image is required and,
if so, a description suitable for the image generator.
"""

from __future__ import annotations

import json
import logging
import re

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from documentlm_core.config import settings
from documentlm_core.schemas import ParagraphAssessment

logger = logging.getLogger(__name__)

_APP_NAME = "illustration_assessor"

_ASSESSMENT_INSTRUCTION = """You are an assistant for an educational content system.

Your job is to decide whether a given paragraph of lesson text would be meaningfully
enhanced by the addition of a small illustration.

Respond ONLY with a JSON object — no explanation, no markdown, no extra text — in exactly
this format:

{"requires_image": true, "image_description": "A clear description of the image"}

or:

{"requires_image": false, "image_description": ""}

Rules:
- Set requires_image to true only when a visual would genuinely aid comprehension
  (e.g. diagrams, processes, anatomical structures, physical phenomena, timelines).
- Set requires_image to false for abstract text, references sections, or introductory prose
  that would not benefit from a visual.
- image_description must be a clear, standalone description that an illustrator can act on
  without further context. Write it as a directive: "A diagram showing X", "A cross-section of Y".
- Never include text, labels, or callouts in your description — the image must be text-free.
"""

_FENCE_RE = re.compile(r"^```[a-z]*\n(.*?)\n?```$", re.DOTALL)


async def _run_assessor(prompt: str) -> str:
    """Run the ADK agent and return the raw text reply."""
    agent = Agent(
        name=_APP_NAME,
        model=settings.gemini_model,
        instruction=_ASSESSMENT_INSTRUCTION,
    )
    session_service: InMemorySessionService = InMemorySessionService()  # type: ignore[no-untyped-call]
    session = await session_service.create_session(
        app_name=_APP_NAME, user_id="system"
    )
    runner = Runner(agent=agent, app_name=_APP_NAME, session_service=session_service)

    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=prompt)],
    )

    reply_text: str | None = None
    async for event in runner.run_async(
        user_id="system",
        session_id=session.id,
        new_message=user_message,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            reply_text = event.content.parts[0].text
            break

    return reply_text or ""


def _parse_assessment(raw: str) -> ParagraphAssessment:
    """Parse JSON from the LLM response, stripping markdown fences if present."""
    text = raw.strip()
    fence_match = _FENCE_RE.match(text)
    if fence_match:
        text = fence_match.group(1).strip()

    data = json.loads(text)
    return ParagraphAssessment(
        requires_image=bool(data.get("requires_image", False)),
        image_description=str(data.get("image_description", "")),
    )


async def assess_paragraph(
    paragraph_title: str, paragraph_text: str
) -> ParagraphAssessment:
    """Assess whether a paragraph needs an illustration.

    Returns a ParagraphAssessment. On any failure, returns a safe default
    (requires_image=False) and logs the error — never raises.
    """
    prompt = (
        "<lesson text>\n"
        f"{paragraph_title} {paragraph_text}\n"
        "</lesson text>"
    )
    logger.debug(
        "IllustrationAssessor: assessing paragraph title=%r length=%d",
        paragraph_title[:60],
        len(paragraph_text),
    )
    try:
        raw = await _run_assessor(prompt)
        logger.debug("IllustrationAssessor: raw response=%r", raw[:200])
        result = _parse_assessment(raw)
        logger.debug(
            "IllustrationAssessor: requires_image=%s description=%r",
            result.requires_image,
            result.image_description[:80],
        )
        return result
    except json.JSONDecodeError as exc:
        logger.warning(
            "IllustrationAssessor: JSON parse failed for paragraph title=%r: %s",
            paragraph_title[:60],
            exc,
        )
        return ParagraphAssessment(requires_image=False, image_description="")
    except Exception:
        logger.exception(
            "IllustrationAssessor: unexpected error for paragraph title=%r",
            paragraph_title[:60],
        )
        return ParagraphAssessment(requires_image=False, image_description="")

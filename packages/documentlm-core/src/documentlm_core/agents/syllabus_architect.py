"""Syllabus Architect: generates a hierarchical syllabus for a topic using Gemini."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Protocol

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from documentlm_core.config import settings

logger = logging.getLogger(__name__)

_APP_NAME = "syllabus_architect"

_INSTRUCTION = """You are an academic curriculum designer.
Given a topic, generate a structured syllabus as a JSON array.

The syllabus must be a two-level hierarchy:
- Top-level items are broad sections (e.g. "Foundations", "Core Theory", "Applications")
- Each section has children that are specific, learnable sub-topics

Rules:
- Generate 4-6 top-level sections appropriate for the topic
- Each section should have 3-6 child items
- Titles should be specific and meaningful, not generic
- Descriptions should be one sentence explaining what the item covers
- Children must reference their parent's title in the "parent" field

Respond with ONLY valid JSON in this exact format, no other text:
[
  {
    "title": "Section Title",
    "description": "What this section covers.",
    "parent": null
  },
  {
    "title": "Child Topic Title",
    "description": "What this child topic covers.",
    "parent": "Section Title"
  }
]
"""


class SyllabusToolsProtocol(Protocol):
    async def create_syllabus_item(
        self,
        topic_id: uuid.UUID,
        title: str,
        description: str | None,
        parent_id: uuid.UUID | None,
    ) -> uuid.UUID:
        """Persist a syllabus item and return its ID."""
        ...


async def run_syllabus_architect(
    topic_id: uuid.UUID,
    topic_title: str,
    tools: SyllabusToolsProtocol,
    primary_source_texts: list[str] | None = None,
) -> list[uuid.UUID]:
    logger.info(
        "Syllabus Architect starting for topic_id=%s title=%r primary_sources=%d",
        topic_id,
        topic_title,
        len(primary_source_texts) if primary_source_texts else 0,
    )

    agent = Agent(
        name="syllabus_architect",
        model=settings.gemini_model,
        instruction=_INSTRUCTION,
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name=_APP_NAME, user_id="system")
    runner = Runner(agent=agent, app_name=_APP_NAME, session_service=session_service)

    # Build user message — inject primary source content when provided
    if primary_source_texts:
        if len(primary_source_texts) == 1:
            source_block = (
                "Use the following provided course material exactly as the syllabus structure "
                "(do not invent new sections, preserve the provided structure):\n\n"
                f"{primary_source_texts[0]}"
            )
        else:
            joined = "\n\n---\n\n".join(primary_source_texts)
            source_block = (
                "Synthesise a single coherent syllabus structure from the following provided "
                "course materials, resolving overlaps and filling gaps. Do not copy any one "
                "source verbatim — produce one unified structure:\n\n"
                f"{joined}"
            )
        prompt = (
            f"Generate a syllabus for the topic: {topic_title}\n\n"
            f"{source_block}"
        )
    else:
        prompt = f"Generate a syllabus for the topic: {topic_title}"

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

    if not reply_text:
        raise RuntimeError("Syllabus Architect returned no response")

    # Strip markdown code fences if present
    text = reply_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    items = json.loads(text)
    logger.info("Syllabus Architect parsed %d items for topic=%r", len(items), topic_title)

    # First pass: create all parent (null-parent) items and record title → id
    title_to_id: dict[str, uuid.UUID] = {}
    created_ids: list[uuid.UUID] = []

    for item in items:
        if item.get("parent") is None:
            item_id = await tools.create_syllabus_item(
                topic_id=topic_id,
                title=item["title"],
                description=item.get("description"),
                parent_id=None,
            )
            title_to_id[item["title"]] = item_id
            created_ids.append(item_id)

    # Second pass: create children
    for item in items:
        parent_title = item.get("parent")
        if parent_title is not None:
            parent_id = title_to_id.get(parent_title)
            item_id = await tools.create_syllabus_item(
                topic_id=topic_id,
                title=item["title"],
                description=item.get("description"),
                parent_id=parent_id,
            )
            created_ids.append(item_id)

    logger.info(
        "Syllabus Architect complete: %d items created for topic_id=%s",
        len(created_ids),
        topic_id,
    )
    return created_ids

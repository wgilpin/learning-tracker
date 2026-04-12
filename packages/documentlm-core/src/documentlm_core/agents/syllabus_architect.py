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

_LEVEL_GUIDANCE: dict[str, str] = {
    "beginner": (
        "a complete beginner with no prior knowledge. "
        "Build from first principles, avoid heavy jargon, and sequence concepts "
        "so each one follows naturally from the last."
    ),
    "intermediate": (
        "a learner with some background knowledge. "
        "Assume familiarity with fundamentals and build on them meaningfully."
    ),
    "advanced": (
        "an expert or specialist. Assume strong prior knowledge; "
        "apply rigorous treatment, nuanced distinctions, and include cutting-edge topics."
    ),
}

_EXTENDER_INSTRUCTION = """You are an academic curriculum designer extending an existing syllabus.
Given the topic, an extension request, and existing section titles, generate ONLY NEW sections.

Rules:
- Do NOT reproduce or paraphrase any existing section title
- Generate 1-3 new top-level sections that satisfy the extension request
- Each section should have 3-6 child items
- Children must reference their parent's title in the "parent" field
- Titles should be specific and meaningful, not generic
- Descriptions should be one sentence explaining what the item covers

Respond with ONLY valid JSON in this exact format, no other text:
[
  {
    "title": "New Section Title",
    "description": "What this section covers.",
    "parent": null
  },
  {
    "title": "Child Topic Title",
    "description": "What this child topic covers.",
    "parent": "New Section Title"
  }
]
"""

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


_BLOOM_LEVELS_BY_TOPIC_LEVEL: dict[str, str] = {
    "beginner": "remember and understand",
    "intermediate": "apply and analyse",
    "advanced": "evaluate and create",
}

_OBJECTIVES_INSTRUCTION = """You are an educational designer writing learning objectives using Bloom's Taxonomy.

Given a chapter title and description, generate 2-5 learning objectives using measurable Bloom's verbs.

Output ONLY valid JSON — no prose, no code fences — in this exact format:
[
  {
    "text": "Objective text beginning with a measurable Bloom's verb",
    "bloom_level": "remember"
  }
]

Valid bloom_level values (choose the best fit): remember | understand | apply | analyse | evaluate | create

Measurable verbs by level:
- remember: define, list, recall, identify, name, state
- understand: explain, summarise, describe, classify, paraphrase
- apply: solve, use, demonstrate, calculate, execute, implement
- analyse: compare, differentiate, trace, break down, distinguish, organise
- evaluate: justify, critique, assess, judge, defend, evaluate
- create: design, construct, synthesise, formulate, compose, produce

Rules:
- Each objective must begin with one of these verbs
- Objectives must be specific enough that a tutor can assess them in conversation
- Generate between 2 and 5 objectives (lean toward 3-4)
- Output only the JSON array, nothing else"""


async def generate_chapter_objectives(
    topic_title: str,
    topic_level: str,
    item_title: str,
    item_description: str | None,
) -> list[dict]:
    """Generate 2-5 Bloom's Taxonomy learning objectives for a chapter.

    Returns a list of dicts with 'text' and 'bloom_level' keys.
    On failure, returns an empty list so callers can proceed without objectives.
    """
    bloom_guidance = _BLOOM_LEVELS_BY_TOPIC_LEVEL.get(topic_level, "apply and analyse")
    desc_line = f"\nDescription: {item_description}" if item_description else ""
    prompt = (
        f"Topic: {topic_title}\n"
        f"Chapter: {item_title}{desc_line}\n\n"
        f"Target audience level: {topic_level} — focus objectives at the "
        f"{bloom_guidance} cognitive levels."
    )

    agent = Agent(
        name="objectives_generator",
        model=settings.gemini_model,
        instruction=_OBJECTIVES_INSTRUCTION,
    )
    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name=_APP_NAME, user_id="system")
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

    if not reply_text:
        logger.warning(
            "generate_chapter_objectives: no response for item=%r — skipping", item_title
        )
        return []

    text = reply_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    try:
        objectives = json.loads(text)
        if not isinstance(objectives, list):
            raise ValueError("Expected a JSON array")
        logger.info(
            "generate_chapter_objectives: %d objectives for %r", len(objectives), item_title
        )
        return objectives
    except Exception:
        logger.exception(
            "generate_chapter_objectives: JSON parse failed for item=%r — skipping", item_title
        )
        return []


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
    level: str = "intermediate",
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

    # Build user message — inject level guidance and optional primary source content
    level_description = _LEVEL_GUIDANCE.get(level, _LEVEL_GUIDANCE["intermediate"])
    level_line = f"Target audience: {level_description}"

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
            f"{level_line}\n\n"
            f"{source_block}"
        )
    else:
        prompt = f"Generate a syllabus for the topic: {topic_title}\n\n{level_line}"

    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=prompt)],
    )

    logger.info("Syllabus Architect calling LLM (model=%s)", settings.gemini_model)
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

    logger.info("Syllabus Architect received LLM response — parsing JSON")

    # Strip markdown code fences if present
    text = reply_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    items = json.loads(text)
    parents = [i for i in items if i.get("parent") is None]
    children = [i for i in items if i.get("parent") is not None]
    logger.info(
        "Syllabus Architect parsed %d items (%d sections, %d sub-topics) for topic=%r",
        len(items),
        len(parents),
        len(children),
        topic_title,
    )

    # First pass: create all parent (null-parent) items and record title → id
    title_to_id: dict[str, uuid.UUID] = {}
    created_ids: list[uuid.UUID] = []

    logger.info("Syllabus Architect persisting %d top-level sections", len(parents))
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
    logger.info("Syllabus Architect persisting %d sub-topics", len(children))
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


async def run_syllabus_extender(
    topic_id: uuid.UUID,
    topic_title: str,
    extension_prompt: str,
    existing_section_titles: list[str],
    tools: SyllabusToolsProtocol,
    level: str = "intermediate",
) -> list[uuid.UUID]:
    logger.info(
        "Syllabus Extender starting for topic_id=%s prompt=%r existing=%d",
        topic_id,
        extension_prompt,
        len(existing_section_titles),
    )

    agent = Agent(
        name="syllabus_extender",
        model=settings.gemini_model,
        instruction=_EXTENDER_INSTRUCTION,
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name=_APP_NAME, user_id="system")
    runner = Runner(agent=agent, app_name=_APP_NAME, session_service=session_service)

    level_description = _LEVEL_GUIDANCE.get(level, _LEVEL_GUIDANCE["intermediate"])
    existing_block = "\n".join(f"- {t}" for t in existing_section_titles)
    prompt = (
        f"Extend the syllabus for: {topic_title}\n\n"
        f"Target audience: {level_description}\n\n"
        f"Extension request: {extension_prompt}\n\n"
        f"Existing sections (do NOT duplicate):\n{existing_block}"
    )

    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=prompt)],
    )

    logger.info("Syllabus Extender calling LLM (model=%s)", settings.gemini_model)
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
        raise RuntimeError("Syllabus Extender returned no response")

    logger.info("Syllabus Extender received LLM response — parsing JSON")

    text = reply_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    items = json.loads(text)
    parents = [i for i in items if i.get("parent") is None]
    children = [i for i in items if i.get("parent") is not None]
    logger.info(
        "Syllabus Extender parsed %d items (%d sections, %d sub-topics)",
        len(items),
        len(parents),
        len(children),
    )

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
        "Syllabus Extender complete: %d items created for topic_id=%s",
        len(created_ids),
        topic_id,
    )
    return created_ids

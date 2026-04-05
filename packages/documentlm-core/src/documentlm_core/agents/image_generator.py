"""Image Generator: produces illustrations via the Gemini image generation model.

Uses google.genai directly (not Google ADK) since image generation is a
stateless single API call, not a multi-turn agent conversation.
"""

from __future__ import annotations

import logging

from google import genai
from google.genai import types as genai_types

from documentlm_core.config import settings

logger = logging.getLogger(__name__)

_IMAGE_PROMPT_PREFIX = (
    "For use in an academic textbook, create the following as a simple image only. "
    "Use a white background. Use colours and shading to make the image clear and visually engaging "
    "when appropriate for clarity. "
    "Only include descriptive text if the image cannot be understood without it, as "
    "the image will be displayed alongside an explanatory paragraph. "
    "The image will be displayed at a maximum width of 600px. "
)


def _get_client() -> genai.Client:
    """Return a configured google.genai client."""
    return genai.Client(api_key=settings.google_api_key)


async def generate_image(
    image_description: str, model: str, paragraph_text: str = ""
) -> tuple[bytes, str] | None:
    """Generate an illustration for the given description using the specified model.

    Args:
        image_description: A clear description of the image to generate.
        model: The Gemini image generation model name to use.

    Returns:
        A tuple of (image_bytes, mime_type) on success, or None on failure.
        Never raises — all exceptions are caught and logged.
    """
    para_context = (
        f" This is the paragraph the image is illustrating: {paragraph_text}"
        if paragraph_text
        else ""
    )
    prompt = _IMAGE_PROMPT_PREFIX + image_description + para_context
    logger.info(
        "ImageGenerator: full prompt model=%r prompt=%r",
        model,
        prompt,
    )
    try:
        client = _get_client()
        response = await client.aio.models.generate_content(
            model=model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"]
            ),
        )

        if not response.candidates:
            logger.warning(
                "ImageGenerator: no candidates in response for description=%r",
                image_description[:80],
            )
            return None

        candidate = response.candidates[0]
        if candidate.content is None or candidate.content.parts is None:
            logger.warning(
                "ImageGenerator: candidate has no content/parts for description=%r",
                image_description[:80],
            )
            return None

        for part in candidate.content.parts:
            if part.inline_data is not None and part.inline_data.data is not None:
                image_bytes: bytes = bytes(part.inline_data.data)
                mime_type: str = str(part.inline_data.mime_type or "image/png")
                logger.debug(
                    "ImageGenerator: success bytes=%d mime_type=%r",
                    len(image_bytes),
                    mime_type,
                )
                return image_bytes, mime_type

        logger.warning(
            "ImageGenerator: response contained no image part for description=%r",
            image_description[:80],
        )
        return None

    except Exception:
        logger.exception(
            "ImageGenerator: failed to generate image for description=%r",
            image_description[:80],
        )
        return None

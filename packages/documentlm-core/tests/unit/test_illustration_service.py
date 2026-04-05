"""Unit tests for illustration_service orchestration and section parsing.

All LLM calls (assess_paragraph, generate_image) are mocked.
DB session is mocked — persistence is tested in integration tests.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from documentlm_core.schemas import ParagraphAssessment


# ---------------------------------------------------------------------------
# _split_into_sections
# ---------------------------------------------------------------------------


class TestSplitIntoSections:
    def test_single_section_no_body(self) -> None:
        from documentlm_core.services.illustration import _split_into_sections

        content = "## Introduction"
        sections = _split_into_sections(content)
        assert len(sections) == 1
        idx, title, body = sections[0]
        assert idx == 1
        assert title == "Introduction"
        assert body == ""

    def test_single_section_with_body_paragraphs(self) -> None:
        from documentlm_core.services.illustration import _split_into_sections

        content = "## Introduction\n\nThis is the intro.\n\nMore intro text."
        sections = _split_into_sections(content)
        assert len(sections) == 1
        idx, title, body = sections[0]
        assert idx == 1
        assert title == "Introduction"
        assert "This is the intro." in body
        assert "More intro text." in body

    def test_two_sections_correct_indices(self) -> None:
        from documentlm_core.services.illustration import _split_into_sections

        content = (
            "## Section One\n\nFirst body.\n\n"
            "## Section Two\n\nSecond body."
        )
        sections = _split_into_sections(content)
        assert len(sections) == 2
        # "## Section One" is para 1, its body "First body." is para 2
        # "## Section Two" is para 3
        assert sections[0][0] == 1   # heading at \n\n-para index 1
        assert sections[0][1] == "Section One"
        assert sections[1][0] == 3   # heading at \n\n-para index 3
        assert sections[1][1] == "Section Two"

    def test_content_before_first_heading_is_skipped(self) -> None:
        from documentlm_core.services.illustration import _split_into_sections

        content = "Preamble text.\n\n## First Heading\n\nBody."
        sections = _split_into_sections(content)
        assert len(sections) == 1
        idx, title, body = sections[0]
        assert idx == 2   # "## First Heading" is the second \n\n para
        assert title == "First Heading"

    def test_empty_content_returns_no_sections(self) -> None:
        from documentlm_core.services.illustration import _split_into_sections

        assert _split_into_sections("") == []
        assert _split_into_sections("No headings here.") == []

    def test_inline_text_after_heading_included_in_body(self) -> None:
        from documentlm_core.services.illustration import _split_into_sections

        content = "## Key Concepts\nDefinition inline.\n\nMore detail."
        sections = _split_into_sections(content)
        assert len(sections) == 1
        _, _, body = sections[0]
        assert "Definition inline." in body
        assert "More detail." in body

    def test_three_sections(self) -> None:
        from documentlm_core.services.illustration import _split_into_sections

        content = (
            "## A\n\nBody A.\n\n"
            "## B\n\nBody B.\n\n"
            "## C\n\nBody C."
        )
        sections = _split_into_sections(content)
        assert len(sections) == 3
        assert [s[1] for s in sections] == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# run_illustration_pipeline
# ---------------------------------------------------------------------------

# Standard two-section content for pipeline tests
_TWO_SECTION_CONTENT = (
    "## Neural Networks\n\nA neural network is a computational model.\n\n"
    "## References\n\n[1] Smith et al."
)


class TestRunIllustrationPipeline:
    @pytest.mark.asyncio
    async def test_generates_image_for_section_requiring_one(self) -> None:
        from documentlm_core.services.illustration import run_illustration_pipeline

        chapter_id = uuid.uuid4()
        content = "## Neural Networks\nA neural network explanation."
        mock_session = AsyncMock()

        assessment = ParagraphAssessment(
            requires_image=True, image_description="A neural network diagram"
        )

        with (
            patch(
                "documentlm_core.services.illustration.assess_paragraph",
                new=AsyncMock(return_value=assessment),
            ),
            patch(
                "documentlm_core.services.illustration.generate_image",
                new=AsyncMock(return_value=(b"IMGDATA", "image/png")),
            ) as mock_gen,
        ):
            await run_illustration_pipeline(chapter_id, content, mock_session)

        mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_generation_when_not_required(self) -> None:
        from documentlm_core.services.illustration import run_illustration_pipeline

        chapter_id = uuid.uuid4()
        content = "## References\n\n[1] Smith et al."
        mock_session = AsyncMock()

        assessment = ParagraphAssessment(requires_image=False, image_description="")

        with (
            patch(
                "documentlm_core.services.illustration.assess_paragraph",
                new=AsyncMock(return_value=assessment),
            ),
            patch(
                "documentlm_core.services.illustration.generate_image",
                new=AsyncMock(return_value=(b"IMGDATA", "image/png")),
            ) as mock_gen,
        ):
            await run_illustration_pipeline(chapter_id, content, mock_session)

        mock_gen.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_db_write_when_generate_returns_none(self) -> None:
        from documentlm_core.services.illustration import run_illustration_pipeline

        chapter_id = uuid.uuid4()
        content = "## Topic\n\nSome content."
        mock_session = AsyncMock()

        assessment = ParagraphAssessment(
            requires_image=True, image_description="A diagram"
        )

        with (
            patch(
                "documentlm_core.services.illustration.assess_paragraph",
                new=AsyncMock(return_value=assessment),
            ),
            patch(
                "documentlm_core.services.illustration.generate_image",
                new=AsyncMock(return_value=None),
            ),
        ):
            await run_illustration_pipeline(chapter_id, content, mock_session)

        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_processes_multiple_sections(self) -> None:
        from documentlm_core.services.illustration import run_illustration_pipeline

        chapter_id = uuid.uuid4()
        mock_session = AsyncMock()

        needs_image = ParagraphAssessment(
            requires_image=True, image_description="A diagram"
        )
        no_image = ParagraphAssessment(requires_image=False, image_description="")

        with (
            patch(
                "documentlm_core.services.illustration.assess_paragraph",
                new=AsyncMock(side_effect=[needs_image, no_image]),
            ),
            patch(
                "documentlm_core.services.illustration.generate_image",
                new=AsyncMock(return_value=(b"IMG", "image/png")),
            ) as mock_gen,
        ):
            await run_illustration_pipeline(chapter_id, _TWO_SECTION_CONTENT, mock_session)

        # Only the first section required an image
        mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_continues_after_assessment_failure(self) -> None:
        from documentlm_core.services.illustration import run_illustration_pipeline

        chapter_id = uuid.uuid4()
        mock_session = AsyncMock()

        good_assessment = ParagraphAssessment(
            requires_image=True, image_description="A chart"
        )

        with (
            patch(
                "documentlm_core.services.illustration.assess_paragraph",
                new=AsyncMock(side_effect=[RuntimeError("LLM down"), good_assessment]),
            ),
            patch(
                "documentlm_core.services.illustration.generate_image",
                new=AsyncMock(return_value=(b"IMG", "image/png")),
            ) as mock_gen,
        ):
            # Must not raise
            await run_illustration_pipeline(chapter_id, _TWO_SECTION_CONTENT, mock_session)

        # Second section still processed
        mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_continues_after_generation_failure(self) -> None:
        from documentlm_core.services.illustration import run_illustration_pipeline

        chapter_id = uuid.uuid4()
        mock_session = AsyncMock()

        needs_image = ParagraphAssessment(
            requires_image=True, image_description="A chart"
        )

        with (
            patch(
                "documentlm_core.services.illustration.assess_paragraph",
                new=AsyncMock(return_value=needs_image),
            ),
            patch(
                "documentlm_core.services.illustration.generate_image",
                new=AsyncMock(side_effect=[RuntimeError("API down"), (b"IMG", "image/png")]),
            ) as mock_gen,
        ):
            await run_illustration_pipeline(chapter_id, _TWO_SECTION_CONTENT, mock_session)

        # Both sections attempted; second succeeded
        assert mock_gen.call_count == 2

    @pytest.mark.asyncio
    async def test_does_not_raise_when_all_sections_fail(self) -> None:
        from documentlm_core.services.illustration import run_illustration_pipeline

        chapter_id = uuid.uuid4()
        content = "## Para\n\nSome text."
        mock_session = AsyncMock()

        with patch(
            "documentlm_core.services.illustration.assess_paragraph",
            new=AsyncMock(side_effect=RuntimeError("LLM down")),
        ):
            # Must not propagate
            await run_illustration_pipeline(chapter_id, content, mock_session)

    @pytest.mark.asyncio
    async def test_content_without_headings_produces_no_illustrations(self) -> None:
        from documentlm_core.services.illustration import run_illustration_pipeline

        chapter_id = uuid.uuid4()
        content = "Just some text.\n\nMore text. No headings."
        mock_session = AsyncMock()

        with patch(
            "documentlm_core.services.illustration.assess_paragraph",
            new=AsyncMock(return_value=ParagraphAssessment(
                requires_image=True, image_description="A diagram"
            )),
        ) as mock_assess:
            await run_illustration_pipeline(chapter_id, content, mock_session)

        # No ## sections found — assessor should never be called
        mock_assess.assert_not_called()

"""Unit tests for illustration_assessor: JSON parsing and edge cases.

All ADK Runner calls are mocked — no live LLM calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from documentlm_core.schemas import ParagraphAssessment, TokenUsage


class TestAssessParagraph:
    @pytest.mark.asyncio
    async def test_returns_requires_image_true_with_description(self) -> None:
        from documentlm_core.agents.illustration_assessor import assess_paragraph

        raw_json = '{"requires_image": true, "image_description": "A diagram of a neural network"}'
        with patch(
            "documentlm_core.agents.illustration_assessor._run_assessor",
            new=AsyncMock(return_value=(raw_json, TokenUsage())),
        ):
            result, _usage = await assess_paragraph("Neural Networks", "A neural network is...")
        assert isinstance(result, ParagraphAssessment)
        assert result.requires_image is True
        assert result.image_description == "A diagram of a neural network"

    @pytest.mark.asyncio
    async def test_returns_requires_image_false(self) -> None:
        from documentlm_core.agents.illustration_assessor import assess_paragraph

        raw_json = '{"requires_image": false, "image_description": ""}'
        with patch(
            "documentlm_core.agents.illustration_assessor._run_assessor",
            new=AsyncMock(return_value=(raw_json, TokenUsage())),
        ):
            result, _usage = await assess_paragraph("References", "[1] Smith et al. 2020...")
        assert result.requires_image is False
        assert result.image_description == ""

    @pytest.mark.asyncio
    async def test_strips_markdown_fences_before_parsing(self) -> None:
        from documentlm_core.agents.illustration_assessor import assess_paragraph

        fenced = '```json\n{"requires_image": true, "image_description": "A chart"}\n```'
        with patch(
            "documentlm_core.agents.illustration_assessor._run_assessor",
            new=AsyncMock(return_value=(fenced, TokenUsage())),
        ):
            result, _usage = await assess_paragraph("Charts", "Here is chart data...")
        assert result.requires_image is True
        assert result.image_description == "A chart"

    @pytest.mark.asyncio
    async def test_malformed_json_returns_no_image(self) -> None:
        from documentlm_core.agents.illustration_assessor import assess_paragraph

        with patch(
            "documentlm_core.agents.illustration_assessor._run_assessor",
            new=AsyncMock(return_value=("not valid json {{{", TokenUsage())),
        ):
            result, _usage = await assess_paragraph("Title", "Body text")
        assert result.requires_image is False
        assert result.image_description == ""

    @pytest.mark.asyncio
    async def test_empty_response_returns_no_image(self) -> None:
        from documentlm_core.agents.illustration_assessor import assess_paragraph

        with patch(
            "documentlm_core.agents.illustration_assessor._run_assessor",
            new=AsyncMock(return_value=("", TokenUsage())),
        ):
            result, _usage = await assess_paragraph("", "")
        assert result.requires_image is False
        assert result.image_description == ""

    @pytest.mark.asyncio
    async def test_runner_exception_returns_no_image(self) -> None:
        from documentlm_core.agents.illustration_assessor import assess_paragraph

        with patch(
            "documentlm_core.agents.illustration_assessor._run_assessor",
            new=AsyncMock(side_effect=RuntimeError("LLM unavailable")),
        ):
            result, _usage = await assess_paragraph("Topic", "Text")
        assert result.requires_image is False
        assert result.image_description == ""

"""Unit tests for image_generator: byte extraction and error handling.

All google.genai.Client calls are mocked — no live API calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_image_response(image_bytes: bytes, mime_type: str) -> MagicMock:
    """Build a mock response object mimicking the google.genai response structure."""
    inline_data = MagicMock()
    inline_data.data = image_bytes
    inline_data.mime_type = mime_type

    part = MagicMock()
    part.inline_data = inline_data

    content = MagicMock()
    content.parts = [part]

    candidate = MagicMock()
    candidate.content = content

    response = MagicMock()
    response.candidates = [candidate]
    return response


class TestGenerateImage:
    @pytest.mark.asyncio
    async def test_returns_bytes_and_mime_type_on_success(self) -> None:
        from documentlm_core.agents.image_generator import generate_image

        fake_bytes = b"\x89PNG\r\n\x1a\n"
        mock_response = _make_image_response(fake_bytes, "image/png")

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch(
            "documentlm_core.agents.image_generator._get_client",
            return_value=mock_client,
        ):
            result = await generate_image("A diagram of a cell", "gemini-3.1-flash-image-preview")

        assert result is not None
        image_bytes, mime_type = result
        assert image_bytes == fake_bytes
        assert mime_type == "image/png"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_image_part(self) -> None:
        from documentlm_core.agents.image_generator import generate_image

        part = MagicMock()
        part.inline_data = None

        content = MagicMock()
        content.parts = [part]

        candidate = MagicMock()
        candidate.content = content

        response = MagicMock()
        response.candidates = [candidate]

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=response)

        with patch(
            "documentlm_core.agents.image_generator._get_client",
            return_value=mock_client,
        ):
            result = await generate_image("Some description", "gemini-3.1-flash-image-preview")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_api_exception(self) -> None:
        from documentlm_core.agents.image_generator import generate_image

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("API error")
        )

        with patch(
            "documentlm_core.agents.image_generator._get_client",
            return_value=mock_client,
        ):
            result = await generate_image("A diagram", "gemini-3.1-flash-image-preview")

        assert result is None

    @pytest.mark.asyncio
    async def test_passes_model_argument_to_api(self) -> None:
        from documentlm_core.agents.image_generator import generate_image

        fake_bytes = b"JPEG"
        mock_response = _make_image_response(fake_bytes, "image/jpeg")

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch(
            "documentlm_core.agents.image_generator._get_client",
            return_value=mock_client,
        ):
            await generate_image("A chart", "my-custom-model")

        call_kwargs = mock_client.aio.models.generate_content.call_args
        # model should be passed through — check positional or keyword
        called_model = (
            call_kwargs.kwargs.get("model")
            or (call_kwargs.args[0] if call_kwargs.args else None)
        )
        assert called_model == "my-custom-model"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_candidates(self) -> None:
        from documentlm_core.agents.image_generator import generate_image

        response = MagicMock()
        response.candidates = []

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=response)

        with patch(
            "documentlm_core.agents.image_generator._get_client",
            return_value=mock_client,
        ):
            result = await generate_image("A diagram", "gemini-3.1-flash-image-preview")

        assert result is None

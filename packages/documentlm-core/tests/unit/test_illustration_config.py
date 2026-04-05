"""Unit tests verifying illustration model configuration.

Ensures settings.illustration_model is configurable and passed through to
the image generator rather than being hardcoded.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestIllustrationModelConfig:
    def test_default_illustration_model(self) -> None:
        from documentlm_core.config import Settings

        s = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert s.illustration_model == "gemini-3.1-flash-image-preview"

    def test_illustration_model_overridable_via_env(self, monkeypatch) -> None:
        import importlib

        monkeypatch.setenv("ILLUSTRATION_MODEL", "my-custom-model")
        from documentlm_core.config import Settings

        s = Settings()
        assert s.illustration_model == "my-custom-model"

    @pytest.mark.asyncio
    async def test_generate_image_passes_model_arg_not_hardcoded(self) -> None:
        """generate_image must accept model as a parameter — not read settings internally."""
        from documentlm_core.agents.image_generator import generate_image

        fake_bytes = b"IMGDATA"

        inline_data = MagicMock()
        inline_data.data = fake_bytes
        inline_data.mime_type = "image/png"

        part = MagicMock()
        part.inline_data = inline_data

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
            result = await generate_image("A chart", "custom-model-xyz")

        assert result is not None
        call_kwargs = mock_client.aio.models.generate_content.call_args
        called_model = (
            call_kwargs.kwargs.get("model")
            or (call_kwargs.args[0] if call_kwargs.args else None)
        )
        assert called_model == "custom-model-xyz"

    @pytest.mark.asyncio
    async def test_pipeline_passes_settings_illustration_model_to_generator(self) -> None:
        """run_illustration_pipeline must pass settings.illustration_model to generate_image."""
        from documentlm_core.services.illustration import run_illustration_pipeline
        from documentlm_core.schemas import ParagraphAssessment

        chapter_id_val = __import__("uuid").uuid4()
        content = "## Topic\n\nSome text that needs an image."
        mock_session = AsyncMock()

        assessment = ParagraphAssessment(
            requires_image=True, image_description="A chart of data"
        )

        captured_model: list[str] = []

        async def fake_generate(desc: str, model: str, body: str) -> tuple[bytes, str] | None:
            captured_model.append(model)
            return b"IMG", "image/png"

        with (
            patch(
                "documentlm_core.services.illustration.assess_paragraph",
                new=AsyncMock(return_value=assessment),
            ),
            patch(
                "documentlm_core.services.illustration.generate_image",
                new=fake_generate,
            ),
            patch(
                "documentlm_core.services.illustration.settings"
            ) as mock_settings,
        ):
            mock_settings.illustration_model = "test-illustration-model"
            mock_session.add = MagicMock()
            mock_session.flush = AsyncMock()
            await run_illustration_pipeline(chapter_id_val, content, mock_session)

        assert captured_model == ["test-illustration-model"]

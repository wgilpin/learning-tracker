"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://tracker:tracker@localhost:5432/tracker"
    google_api_key: str = Field(
        default="", alias="GOOGLE_API_KEY", validation_alias="GOOGLE_API_KEY"
    )
    gemini_model: str = "gemini-3-flash-preview"
    chroma_path: str = Field(default="./chroma_data", alias="CHROMA_PATH")
    debug: bool = Field(default=False, alias="DEBUG")
    session_secret_key: str = Field(
        default="dev-insecure-change-in-production",
        alias="SESSION_SECRET_KEY",
    )
    dev_password: str = Field(default="", alias="DEV_PASSWORD")
    illustration_model: str = Field(
        default="gemini-3.1-flash-image-preview", alias="ILLUSTRATION_MODEL"
    )
    # Pricing for cost display (USD per million tokens / per image)
    # Calibrated for gemini-3-flash-preview (text) and gemini-3.1-flash-image-preview (images)
    cost_input_per_m: float = Field(default=0.50, alias="COST_INPUT_PER_M")
    cost_output_per_m: float = Field(default=3.00, alias="COST_OUTPUT_PER_M")
    # gemini-3.1-flash-image-preview charges per output tokens ($60/M ≈ $0.045–$0.151/image)
    cost_per_image: float = Field(default=0.10, alias="COST_PER_IMAGE")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "env_ignore_empty": True,
        "extra": "ignore",
    }


settings = Settings()

if settings.google_api_key:
    os.environ["GOOGLE_API_KEY"] = settings.google_api_key

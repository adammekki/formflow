"""
FormFlow - Application Configuration

Centralized configuration using Pydantic Settings.
Supports environment variables and .env files.
"""

from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode
from typing import Annotated, Literal, Optional
import json


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # App settings
    app_name: str = "FormFlow"
    app_version: str = "0.1.0"
    app_env: str = "development"

    # Inference settings
    inference_provider: Literal["ollama", "vllm"] = "ollama"
    inference_base_url: str = "http://localhost:11434"
    inference_model: str = "ministral-3:8b"
    inference_timeout: int = 120  # seconds

    # Paths
    configs_dir: str = "/app/configs"
    templates_dir: str = "/app/templates"
    feedback_dir: str = "/app/feedback"

    # API
    api_prefix: str = "/api"
    # NoDecode keeps pydantic-settings from JSON-parsing the env value itself,
    # so CORS_ORIGINS can be written as a plain comma-separated list.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value):
        """Accept "a,b", '["a","b"]', or an already-parsed list."""
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                return json.loads(stripped)
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()

"""Typed application settings loaded from environment variables and an optional `.env` file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required
    mongodb_uri: SecretStr = Field(description="MongoDB connection string.")

    # Database
    db_name: str = Field(default="adaptive_diagnostic", min_length=1, max_length=63)
    mongodb_timeout_ms: int = Field(default=5000, ge=500, le=60000)
    seed_on_startup: bool = False

    # Optional AI provider
    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-120b"
    ai_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    ai_max_retries: int = Field(default=1, ge=0, le=3)
    study_plan_max_ai_attempts: int = Field(default=3, ge=1, le=10)

    # Assessment behaviour
    assessment_ttl_minutes: int = Field(default=120, ge=5, le=60 * 24 * 7)
    se_target: float = Field(default=0.40, gt=0.1, lt=1.0)
    min_questions: int = Field(default=6, ge=1, le=50)

    # HTTP
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    rate_limit_create_per_minute: int = Field(default=30, ge=1, le=10000)
    rate_limit_answer_per_minute: int = Field(default=300, ge=1, le=100000)
    rate_limit_study_plan_per_minute: int = Field(default=6, ge=1, le=1000)
    serve_frontend: bool = True
    frontend_dist: Path = REPO_ROOT / "frontend" / "dist"
    log_level: str = "INFO"

    @field_validator("mongodb_uri")
    @classmethod
    def _check_uri(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value().strip()
        if not raw.startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError("must start with mongodb:// or mongodb+srv://")
        return SecretStr(raw)

    @field_validator("groq_api_key")
    @classmethod
    def _blank_key_is_none(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None or not value.get_secret_value().strip():
            return None
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("db_name")
    @classmethod
    def _check_db_name(cls, value: str) -> str:
        if any(char in value for char in '/\\. "$'):
            raise ValueError("contains characters MongoDB does not allow in database names")
        return value

    @model_validator(mode="after")
    def _check_log_level(self) -> Settings:
        self.log_level = self.log_level.upper()
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL")
        return self

    @property
    def ai_enabled(self) -> bool:
        return self.groq_api_key is not None


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@lru_cache
def get_settings() -> Settings:
    from pydantic import ValidationError

    try:
        return Settings()
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in err['loc']).upper() or 'settings'}: {err['msg']}" for err in exc.errors()
        )
        raise ConfigurationError(
            f"Invalid configuration ({problems}). Copy .env.example to .env and fill in the required values."
        ) from None

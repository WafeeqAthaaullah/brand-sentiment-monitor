from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings and environment variable validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    GROQ_API_KEY: Optional[str] = Field(default=None, description="Groq API key for inference")
    LLM_PROVIDER: str = Field(default="groq", description="Selected LLM provider")
    DATABASE_URL: str = Field(
        default="sqlite:///./sentiment_monitor.db",
        description="Database connection URL",
    )
    SLACK_WEBHOOK_URL: Optional[str] = Field(
        default=None,
        description="Slack incoming webhook URL for alert notifications",
    )
    YOUTUBE_API_KEY: str = Field(
        default="",
        description="Google / YouTube Data API v3 key",
    )
    GROQ_MODEL: str = Field(
        default="openai/gpt-oss-20b",
        description="Groq model ID to use for inference",
    )


settings = Settings()


"""
Application configuration module using pydantic-settings.
"""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application Settings
    app_name: str = "PDF Comparison Service"
    app_version: str = "1.0.0"
    debug: bool = False

    # File Upload Settings
    max_upload_size_mb: int = 50
    upload_dir: str = "./uploads"
    output_dir: str = "./outputs"
    comparison_dpi: int = 300
    max_pages_per_job: int = 100

    # CORS Settings
    allowed_origins: List[str] = [
        "http://localhost:8000",
        "http://localhost:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:3000"
    ]

    # Comparison Settings
    similarity_threshold: float = 0.85

    # LLM Default Settings (optional fallbacks - UI config takes precedence)
    default_llm_provider: str = "openai"
    default_openai_model: str = "gpt-4-turbo-preview"
    default_anthropic_model: str = "claude-3-sonnet-20240229"
    default_temperature: float = 0.1

    # Storage and Cleanup
    cache_results_hours: int = 24
    auto_cleanup: bool = True


# Global settings instance
settings = Settings()

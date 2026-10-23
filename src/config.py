"""Settings loaded from environment variables or .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "image-pipeline-api"
    host: str = "0.0.0.0"
    port: int = 8000
    max_upload_bytes: int = 10 * 1024 * 1024
    max_pixels: int = 40_000_000
    max_output_side: int = 8192
    default_quality: int = 90
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()

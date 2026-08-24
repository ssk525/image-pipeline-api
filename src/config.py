"""Application settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    max_upload_bytes: int = 10 * 1024 * 1024
    default_jpeg_quality: int = 85
    host: str = "0.0.0.0"
    port: int = 8000
    service_name: str = "image-pipeline-api"


@lru_cache
def get_settings() -> Settings:
    return Settings()

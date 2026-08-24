from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_token: str = Field(alias="ARCHIVIST_API_TOKEN")
    public_base_url: str = Field(alias="ARCHIVIST_PUBLIC_BASE_URL")
    storage_root: Path = Field(alias="ARCHIVIST_STORAGE_ROOT")
    max_upload_mb: int = Field(alias="ARCHIVIST_MAX_UPLOAD_MB")
    database_url: str = Field(alias="ARCHIVIST_DATABASE_URL")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

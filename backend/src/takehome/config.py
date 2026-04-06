from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://orbital:orbital@db:5432/orbital_takehome"
    anthropic_api_key: str = ""
    upload_dir: str = "uploads"
    max_upload_size: int = 25 * 1024 * 1024  # 25MB

    model_config = {"env_file": ".env"}


settings = Settings()

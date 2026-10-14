
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# Locate the .env file inside the backend directory.
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    DATABASE_URL: str

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)


class Settings:
    app_name: str = "Finder Image Service"
    secret_key: str = os.getenv("APP_SECRET_KEY", "super-secret-key")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MIN", "360"))

    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://root:Admin2025@db:5452/finder_image",
    )

    google_cse_id: str | None = os.getenv("GOOGLE_CSE_ID")
    google_api_key: str | None = os.getenv("GOOGLE_API_KEY")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()

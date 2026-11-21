from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Env-driven settings. Everything is optional at import time; callers check what they need (e.g. DATABASE_URL)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str | None = None
    LLM_BASE_URL: str | None = None
    LLM_API_KEY: str = ""
    CRON_SECRET: str | None = None
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_HOST: str | None = None
    UPSTASH_REDIS_REST_URL: str | None = None
    UPSTASH_REDIS_REST_TOKEN: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()

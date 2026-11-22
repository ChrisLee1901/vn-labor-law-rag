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


# Giới hạn thời gian / kích thước của /api/chat (Vercel dừng function ở 120 s nên ngân sách tổng là 100 s).
CHAT_MAX_TOKENS = 1024  # max_tokens gửi cho LLM, chặn đầu ra lặp vô hạn
CHAT_BUDGET_S = 100.0  # tổng thời gian một request chat
CONDENSE_TIMEOUT_S = 8.0
EMBED_TIMEOUT_S = 8.0
RERANK_TIMEOUT_S = 8.0
LANGFUSE_FLUSH_TIMEOUT_S = (
    5.0  # tối đa chờ Langfuse flush (span, score) sau khi response đã đóng
)

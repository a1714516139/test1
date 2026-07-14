"""Application configuration loaded from environment variables."""
from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    """Application settings with env-var fallback."""

    # LLM Provider
    LLM_PROVIDER: str = "claude"  # "claude" or "tongyi"

    # Claude API
    CLAUDE_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"

    # Tongyi / DashScope API
    TONGYI_API_KEY: str = ""
    TONGYI_MODEL: str = "qwen-plus"

    # Redis (optional)
    REDIS_URL: Optional[str] = None

    # CORS
    CORS_ORIGINS: str = "*"

    # Limits
    MAX_FILE_SIZE_MB: int = 10

    # Cache
    CACHE_TTL_SECONDS: int = 3600

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

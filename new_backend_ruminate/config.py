# new_backend/config.py
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class _Settings(BaseSettings):
    """
    Runtime configuration.

    All variables can be supplied as environment variables or in a .env file
    sitting at the project root.  Field names map 1-to-1 to env-var names
    unless an alias is declared.
    """

    # ------------------------------------------------------------------ #
    # Database (PostgreSQL only for production; SQLite allowed in tests) #
    # ------------------------------------------------------------------ #
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "campfire"
    db_password: str = "campfire"
    db_name: str = "campfire"
    db_url: Optional[str] = None                 # full DSN wins if provided
    pool_size: int = 5
    max_overflow: int = 10
    sql_echo: bool = False

    # ------------------------------------------------------------------ #
    # Object Storage                                                     #
    # ------------------------------------------------------------------ #
    s3_bucket: str = Field(..., alias="S3_BUCKET")
    aws_access_key: str = Field(..., alias="AWS_ACCESS_KEY_ID")
    aws_secret_key: str = Field(..., alias="AWS_SECRET_ACCESS_KEY")
    aws_region: str = "aws-west-2"

    # ------------------------------------------------------------------ #
    # LLM provider                                                       #
    # ------------------------------------------------------------------ #
    openai_api_key: str
    openai_model: str = "gpt-4o"

    # ------------------------------------------------------------------ #
    # Misc                                                                #
    # ------------------------------------------------------------------ #
    env: str = "dev"                            # dev | staging | prod
    log_level: str = "INFO"
    deepgram_api_key: str = Field(..., alias="DEEPGRAM_API_KEY")
    video_service_url: str = Field(..., alias="VIDEO_SERVICE_URL")
    
    # ------------------------------------------------------------------ #
    # Celery/Redis Configuration                                         #
    # ------------------------------------------------------------------ #
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for Celery broker and result backend"
    )
    api_base_url: str = Field(
        default="http://localhost:8000",
        description="Base URL for worker callbacks to the API"
    )

    model_config = SettingsConfigDict(
        env_file=(".env", "new_backend_ruminate/.env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ #
    # Derived properties                                                 #
    # ------------------------------------------------------------------ #
    @validator("db_url", always=True)
    def _assemble_url(cls, v, values):
        if v:                                   # already a full DSN
            return v
        if values.get("env") == "test":         # pytest overrides later
            path = Path.cwd() / "test.sqlite"
            return f"sqlite+aiosqlite:///{path}"
        return (
            "postgresql+asyncpg://"
            f"{values['db_user']}:{values['db_password']}"
            f"@{values['db_host']}:{values['db_port']}/{values['db_name']}"
        )

    @property
    def db_dialect(self) -> str:
        """Return the database dialect based on the db_url."""
        url = self.db_url or ""
        if url.startswith("sqlite"):
            return "sqlite"
        if url.startswith("postgresql"):
            return "postgresql"
        return None


@lru_cache
def settings() -> _Settings:
    """Singleton accessor; import this everywhere."""
    return _Settings()

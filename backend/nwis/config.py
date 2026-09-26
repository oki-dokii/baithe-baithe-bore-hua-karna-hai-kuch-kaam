from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NWIS_", extra="ignore")

    database_url: str = Field(min_length=1)
    environment: str = Field(default="local", pattern=r"^(local|test|production)$")
    viewer_token: str = Field(min_length=16)
    engineer_token: str = Field(min_length=16)
    reviewer_token: str = Field(min_length=16)
    admin_token: str = Field(min_length=16)
    storage_root: Path = Path("storage")
    upload_max_bytes: int = Field(default=25 * 1024 * 1024, ge=1, le=100 * 1024 * 1024)
    document_max_pages: int = Field(default=50, ge=1, le=200)
    page_max_characters: int = Field(default=30000, ge=1000, le=100000)
    worker_poll_s: float = Field(default=2, ge=0.1, le=60)
    job_lease_s: int = Field(default=180, ge=120, le=3600)
    job_max_attempts: int = Field(default=3, ge=1, le=5)
    extraction_provider: Literal["local_rules", "openai_compatible"] = "local_rules"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = ""
    llm_api_key: SecretStr = SecretStr("")

    @model_validator(mode="after")
    def unique_tokens(self) -> "Settings":
        tokens = [self.viewer_token, self.engineer_token, self.reviewer_token, self.admin_token]
        if len(set(tokens)) != len(tokens):
            raise ValueError("Role tokens must be unique")
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("Database URL must use postgresql+psycopg")
        if self.extraction_provider == "openai_compatible":
            if not self.llm_model or not self.llm_api_key.get_secret_value():
                raise ValueError("A model and API key are required for remote extraction")
            if not self.llm_base_url.startswith("https://"):
                raise ValueError("Remote extraction requires an HTTPS endpoint")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

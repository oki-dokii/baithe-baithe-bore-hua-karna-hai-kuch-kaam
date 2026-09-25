from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NWIS_", extra="ignore")

    database_url: str = Field(min_length=1)
    environment: str = Field(default="local", pattern=r"^(local|test|production)$")
    viewer_token: str = Field(min_length=16)
    engineer_token: str = Field(min_length=16)
    reviewer_token: str = Field(min_length=16)
    admin_token: str = Field(min_length=16)

    @model_validator(mode="after")
    def unique_tokens(self) -> "Settings":
        tokens = [self.viewer_token, self.engineer_token, self.reviewer_token, self.admin_token]
        if len(set(tokens)) != len(tokens):
            raise ValueError("Role tokens must be unique")
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("Database URL must use postgresql+psycopg")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GILBIC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Gilbic API"
    environment: str = "development"
    api_prefix: str = "/api"
    database_url: str = Field(
        default="postgresql://127.0.0.1:5432/gilbic_dev",
        repr=False,
    )
    supabase_url: str = ""
    supabase_publishable_key: str = Field(default="", repr=False)
    supabase_secret_key: str = Field(default="", repr=False)
    staff_invite_redirect_url: str = ""
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    mobile_android_minimum_version: str = ""
    mobile_ios_minimum_version: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def supabase_auth_configured(self) -> bool:
        return bool(self.supabase_url.strip() and self.supabase_publishable_key.strip())

    @property
    def supabase_admin_configured(self) -> bool:
        return bool(self.supabase_url.strip() and self.supabase_secret_key.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

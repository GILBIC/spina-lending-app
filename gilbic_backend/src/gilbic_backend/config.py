from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GILBIC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Gilbic API"
    environment: str = "development"
    api_prefix: str = "/api"
    database_url: str = Field(
        default="postgresql://127.0.0.1:5432/gilbic_dev",
        validation_alias=AliasChoices(
            "GILBIC_DATABASE_URL",
            "POSTGRES_URL",
            "POSTGRES_URL_NON_POOLING",
            "DATABASE_URL",
        ),
        repr=False,
    )
    supabase_url: str = Field(
        default="",
        validation_alias=AliasChoices(
            "GILBIC_SUPABASE_URL",
            "SUPABASE_URL",
            "NEXT_PUBLIC_SUPABASE_URL",
        ),
    )
    supabase_publishable_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "GILBIC_SUPABASE_PUBLISHABLE_KEY",
            "SUPABASE_PUBLISHABLE_KEY",
            "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
            "SUPABASE_ANON_KEY",
            "NEXT_PUBLIC_SUPABASE_ANON_KEY",
        ),
        repr=False,
    )
    supabase_secret_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "GILBIC_SUPABASE_SECRET_KEY",
            "SUPABASE_SECRET_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
        ),
        repr=False,
    )
    staff_invite_redirect_url: str = ""
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    mobile_android_minimum_version: str = ""
    mobile_ios_minimum_version: str = ""

    # Provider-neutral GCash boundary. Credentials stay on the backend only.
    # V1 defaults to disabled until Management receives a business provider API.
    gcash_mode: str = "disabled"
    gcash_provider: str = "unconfigured"
    gcash_api_base_url: str = ""
    gcash_checkout_path: str = "/payment-intents"
    gcash_api_key: str = Field(default="", repr=False)
    gcash_webhook_secret: str = Field(default="", repr=False)
    gcash_return_url: str = ""
    gcash_timeout_seconds: float = 10.0

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

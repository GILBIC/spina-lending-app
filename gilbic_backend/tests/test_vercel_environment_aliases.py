from __future__ import annotations

from gilbic_backend.config import Settings


_ENV_NAMES = (
    "GILBIC_DATABASE_URL",
    "POSTGRES_URL",
    "POSTGRES_URL_NON_POOLING",
    "DATABASE_URL",
    "GILBIC_SUPABASE_URL",
    "SUPABASE_URL",
    "NEXT_PUBLIC_SUPABASE_URL",
    "GILBIC_SUPABASE_PUBLISHABLE_KEY",
    "SUPABASE_PUBLISHABLE_KEY",
    "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
    "SUPABASE_ANON_KEY",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY",
    "GILBIC_SUPABASE_SECRET_KEY",
    "SUPABASE_SECRET_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
)


def _clear_environment(monkeypatch) -> None:
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_settings_accept_vercel_supabase_environment(monkeypatch) -> None:
    _clear_environment(monkeypatch)
    monkeypatch.setenv(
        "POSTGRES_URL",
        "postgresql://pooler.example.internal:6543/postgres?sslmode=require",
    )
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_example")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_example")

    settings = Settings(_env_file=None)

    assert settings.database_url.startswith("postgresql://pooler.example.internal")
    assert settings.supabase_url == "https://project.supabase.co"
    assert settings.supabase_publishable_key == "sb_publishable_example"
    assert settings.supabase_secret_key == "sb_secret_example"
    assert settings.supabase_auth_configured is True
    assert settings.supabase_admin_configured is True


def test_gilbic_environment_names_override_marketplace_aliases(monkeypatch) -> None:
    _clear_environment(monkeypatch)
    monkeypatch.setenv("GILBIC_DATABASE_URL", "postgresql://custom/spina")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://marketplace/postgres")
    monkeypatch.setenv("GILBIC_SUPABASE_URL", "https://custom.supabase.co")
    monkeypatch.setenv("SUPABASE_URL", "https://marketplace.supabase.co")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql://custom/spina"
    assert settings.supabase_url == "https://custom.supabase.co"


def test_settings_still_accept_explicit_field_values() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql://explicit/spina",
        supabase_url="https://explicit.supabase.co",
        supabase_publishable_key="publishable",
        supabase_secret_key="secret",
    )

    assert settings.database_url == "postgresql://explicit/spina"
    assert settings.supabase_url == "https://explicit.supabase.co"
    assert settings.supabase_publishable_key == "publishable"
    assert settings.supabase_secret_key == "secret"

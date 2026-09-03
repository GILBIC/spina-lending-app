from __future__ import annotations

from urllib.parse import parse_qsl, unquote, urlsplit

from gilbic_backend.database import normalize_database_url_for_psycopg


def test_removes_vercel_supabase_workaround_parameter() -> None:
    source = (
        "postgres://postgres.project:p%40ssword@"
        "aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
        "?sslmode=require&workaround=supabase-pooler.vercel"
    )

    normalized = normalize_database_url_for_psycopg(source)
    parsed = urlsplit(normalized)

    assert parsed.hostname == "aws-0-ap-southeast-1.pooler.supabase.com"
    assert parsed.port == 6543
    assert parsed.username == "postgres.project"
    assert parsed.password == "p%40ssword"
    assert unquote(parsed.password) == "p@ssword"
    assert parse_qsl(parsed.query, keep_blank_values=True) == [("sslmode", "require")]


def test_preserves_normal_postgresql_connection_parameters() -> None:
    source = (
        "postgresql://user:secret@db.example.com:5432/spina"
        "?sslmode=require&connect_timeout=9&application_name=spina"
    )

    assert normalize_database_url_for_psycopg(source) == source

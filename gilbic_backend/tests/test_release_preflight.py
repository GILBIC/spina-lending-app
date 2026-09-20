from __future__ import annotations

import importlib.util
import json

import pytest
from gilbic_backend.config import Settings


def module():
    spec = importlib.util.find_spec("gilbic_backend.release_preflight")
    assert spec is not None, "A sanitized production preflight is required"
    from gilbic_backend import release_preflight

    return release_preflight


def settings(**changes):
    values = {
        "environment": "production",
        "database_url": "postgresql://staff:private-password@db.invalid/spina?sslmode=require",
        "supabase_url": "https://auth.invalid",
        "supabase_publishable_key": "private-public-key",
        "supabase_secret_key": "private-service-key",
        "cors_origins": "https://spina.invalid",
        "gcash_mode": "disabled",
    }
    values.update(changes)
    return Settings(_env_file=None, **values)


def test_preflight_never_reports_private_connection_or_configuration(monkeypatch):
    preflight = module()
    monkeypatch.setattr(
        preflight, "probe_database", lambda _: {"schema": True, "private_grants": True}
    )
    result = preflight.check_runtime(settings())
    assert result["status"] == "passed"
    text = json.dumps(result)
    assert "private-" not in text
    assert "db.invalid" not in text
    assert "auth.invalid" not in text
    assert result["activation_proven"] is False


@pytest.mark.parametrize(
    ("changes", "failed_check"),
    [
        (
            {"database_url": "postgresql://staff:private-password@db.invalid/spina"},
            "database_tls",
        ),
        ({"cors_origins": "*"}, "https_origins"),
        ({"cors_origins": "https://spina.invalid/path"}, "https_origins"),
        ({"supabase_url": "http://auth.invalid"}, "auth_configuration"),
        ({"gcash_mode": "live"}, "verified_payment_mode"),
        ({"environment": "development"}, "production_environment"),
    ],
)
def test_runtime_rejects_unsafe_configuration(monkeypatch, changes, failed_check):
    preflight = module()
    monkeypatch.setattr(
        preflight, "probe_database", lambda _: {"schema": True, "private_grants": True}
    )
    result = preflight.check_runtime(settings(**changes))
    assert result["status"] == "blocked"
    assert result["checks"][failed_check] is False


def test_missing_schema_or_exposed_private_tables_block_runtime(monkeypatch):
    preflight = module()
    monkeypatch.setattr(
        preflight,
        "probe_database",
        lambda _: {"schema": False, "private_grants": False},
    )
    result = preflight.check_runtime(settings())
    assert result["status"] == "blocked"
    assert result["checks"]["schema"] is False
    assert result["checks"]["private_grants"] is False


@pytest.mark.parametrize(
    "origin",
    [
        "https://example.invalid:99999",
        "https://example.invalid:bad",
        "https://example.invalid:0",
        "https://invalid host",
        "https://invalid\thost",
        "\nhttps://example.invalid",
        "https://invalid_host",
        "https://-invalid.example",
        "https://invalid-.example",
        "https://invalid..example",
        "https://999.0.0.1",
        "https://127.1",
        "https://[::1]:bad",
        "https://[fe80::1%25eth0]",
        "https://example.invalid:",
        "https://example.invalid?",
        "https://example.invalid#",
        "https://@example.invalid",
        "https://user@example.invalid",
        "https://" + "a" * 64 + ".invalid",
        "https://[2001:db8:::1]",
    ],
)
def test_malformed_https_endpoints_are_blocked_without_a_database_probe(
    monkeypatch, origin
):
    preflight = module()

    def unexpected_probe(_):
        pytest.fail("Invalid endpoints must fail before any database connection")

    monkeypatch.setattr(preflight, "probe_database", unexpected_probe)
    result = preflight.check_runtime(settings(supabase_url=origin))
    assert result["status"] == "blocked"
    assert result["checks"]["auth_configuration"] is False


@pytest.mark.parametrize(
    "origin",
    [
        "https://spina.invalid/",
        "https://SPINA.invalid",
        "HTTPS://spina.invalid",
        "https://spina.invalid:443",
        "https://spina.invalid:08443",
        "https://[0:0:0:0:0:0:0:1]",
    ],
)
def test_cors_requires_the_exact_origin_a_browser_sends(monkeypatch, origin):
    preflight = module()
    monkeypatch.setattr(
        preflight, "probe_database", lambda _: {"schema": True, "private_grants": True}
    )
    result = preflight.check_runtime(settings(cors_origins=origin))
    assert result["status"] == "blocked"
    assert result["checks"]["https_origins"] is False


@pytest.mark.parametrize(
    "origin",
    [
        "https://spina.invalid",
        "https://spina.invalid:8443",
        "https://192.0.2.1",
        "https://192.0.2.1:65535",
        "https://[::1]",
        "https://[2001:db8::1]:8443",
        "https://xn--bcher-kva.example",
    ],
)
def test_valid_dns_ipv4_and_ipv6_origins_pass_configuration_checks(monkeypatch, origin):
    preflight = module()
    monkeypatch.setattr(
        preflight, "probe_database", lambda _: {"schema": True, "private_grants": True}
    )
    result = preflight.check_runtime(settings(cors_origins=origin))
    assert result["status"] == "passed"


def test_auth_base_url_can_have_a_trailing_slash_and_default_port(monkeypatch):
    preflight = module()
    monkeypatch.setattr(
        preflight, "probe_database", lambda _: {"schema": True, "private_grants": True}
    )
    result = preflight.check_runtime(settings(supabase_url="https://AUTH.invalid:443/"))
    assert result["status"] == "passed"


def test_activation_blocks_missing_private_inputs_without_creating_directories(
    monkeypatch, tmp_path
):
    preflight = module()
    missing = tmp_path / "must-not-be-created"
    for name in (
        "GILBIC_PRIVACY_PACKAGE_MANIFEST",
        "GILBIC_FIRST_LOAN_TEMPLATE_MANIFEST",
        "GILBIC_OFFICE_DOCUMENT_CONVERTER",
        "SPINA_EMPLOYEE_OWNER_USER_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GILBIC_OFFICE_REVIEW_EVIDENCE_ROOT", str(missing))
    monkeypatch.setattr(
        preflight, "probe_database", lambda _: {"schema": True, "private_grants": True}
    )
    result = preflight.check_activation(settings())
    assert result["status"] == "blocked"
    assert not missing.exists()
    assert result["checks"]["private_evidence_storage"] is False
    assert result["checks"]["employee_owner"] is False
    assert result["checks"]["privacy_package"] is False
    assert result["checks"]["legal_templates"] is False
    assert result["activation_proven"] is False

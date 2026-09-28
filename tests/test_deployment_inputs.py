"""Exercise trusted deployment inputs without reaching a server or credentials."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "deployment_helper", ROOT / "ops/digitalocean/workflow_helper.py"
)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def target():
    return {
        "run_id": 12345,
        "droplet_id": 67890,
        "host": "159.223.39.43",
        "hostname": "spina.com.ph",
        "aliases": [
            "app.spina.com.ph",
            "api.spina.com.ph",
            "www.spina.com.ph",
            "spina.159-223-39-43.sslip.io",
        ],
        "cors_origins": ["https://spina.com.ph", "https://app.spina.com.ph"],
        "staff_invite_redirect_url": "https://app.spina.com.ph/",
    }


def write_target(tmp_path, data=None):
    path = tmp_path / "target.json"
    path.write_text(json.dumps(target() if data is None else data), encoding="utf-8")
    return path


def test_declared_domains_and_independent_invite_origin_survive_env_generation(
    tmp_path,
):
    path = write_target(tmp_path)
    secrets = tmp_path / "secrets.json"
    secrets.write_text(
        json.dumps(
            {
                "database_pooler_url": "postgresql://user:test-secret@pooler.example:5432/postgres?sslmode=require",
                "supabase_url": "https://project.example",
                "supabase_publishable_key": "synthetic-publishable",
                "supabase_secret_key": "synthetic-secret",
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "runtime.env"
    helper.write_env(secrets_path=secrets, target_path=path, output_path=output)
    values = output.read_text(encoding="utf-8")
    assert (
        'GILBIC_CORS_ORIGINS="https://spina.com.ph,https://app.spina.com.ph"' in values
    )
    assert 'GILBIC_STAFF_INVITE_REDIRECT_URL="https://app.spina.com.ph/"' in values
    assert helper.load_target(path)["aliases"] == target()["aliases"]


@pytest.mark.parametrize(
    "changes",
    [
        {"hostname": "example.com;touch /tmp/untrusted"},
        {"aliases": ["https://app.spina.com.ph"]},
        {"cors_origins": ["https://unlisted.example"]},
        {"cors_origins": ["http://spina.com.ph"]},
        {"staff_invite_redirect_url": "https://unlisted.example/"},
        {"aliases": []},
    ],
)
def test_target_rejects_unsafe_or_inconsistent_declarations(tmp_path, changes):
    with pytest.raises(ValueError):
        helper.load_target(write_target(tmp_path, dict(target(), **changes)))


def test_caddy_candidate_must_retain_every_declared_hostname(tmp_path):
    config = tmp_path / "caddy.json"
    config.write_text(
        json.dumps(
            {
                "apps": {
                    "http": {
                        "servers": {
                            "public": {
                                "routes": [{"match": [{"host": ["spina.com.ph"]}]}]
                            }
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="domain"):
        helper.validate_caddy(target_path=write_target(tmp_path), config_path=config)
    config.write_text(
        json.dumps({"match": [{"host": ["spina.com.ph", *target()["aliases"]]}]}),
        encoding="utf-8",
    )
    helper.validate_caddy(target_path=write_target(tmp_path), config_path=config)


@pytest.mark.parametrize(
    "override",
    [
        {"GITHUB_REF": "refs/heads/topic"},
        {"GITHUB_REF_PROTECTED": "false"},
        {"GITHUB_EVENT_NAME": "pull_request"},
        {
            "GITHUB_WORKFLOW_REF": "example/spina/.github/workflows/other.yml@refs/heads/main"
        },
    ],
)
def test_prepare_inputs_rejects_untrusted_source_before_writing_files(
    tmp_path, monkeypatch, override
):
    env = {
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_REF_PROTECTED": "true",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REPOSITORY": "example/spina",
        "GITHUB_WORKFLOW_REF": "example/spina/.github/workflows/spina-digitalocean-deploy.yml@refs/heads/main",
        "GITHUB_SHA": "a" * 40,
        "GITHUB_RUN_ID": "12345",
    }
    for key, value in dict(env, **override).items():
        monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match="protected main"):
        helper.prepare_inputs(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_protected_main_prepares_only_declared_inputs_and_missing_secrets_fail_closed(
    tmp_path, monkeypatch
):
    env = {
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_REF_PROTECTED": "true",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REPOSITORY": "example/spina",
        "GITHUB_WORKFLOW_REF": "example/spina/.github/workflows/spina-digitalocean-deploy.yml@refs/heads/main",
        "GITHUB_SHA": "a" * 40,
        "GITHUB_RUN_ID": "12345",
        "SPINA_DEPLOY_TARGET_JSON": json.dumps(target()),
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("SPINA_RUNTIME_SECRETS_JSON", raising=False)
    with pytest.raises(ValueError, match="missing"):
        helper.prepare_inputs(tmp_path)
    assert list(tmp_path.iterdir()) == []
    monkeypatch.setenv(
        "SPINA_RUNTIME_SECRETS_JSON",
        json.dumps(
            {
                "database_pooler_url": "postgresql://user:synthetic-secret@pooler.example:5432/postgres?sslmode=require",
                "supabase_url": "https://project.example",
                "supabase_publishable_key": "synthetic-publishable",
                "supabase_secret_key": "synthetic-secret",
            }
        ),
    )
    helper.prepare_inputs(tmp_path)
    assert (
        helper.load_target(tmp_path / "spina-target.json", expected_run_id=12345)[
            "hostname"
        ]
        == "spina.com.ph"
    )
    assert "https://app.spina.com.ph/" in (tmp_path / "spina.env").read_text()

"""Recovery guards and real private-file integrity checks, without a database."""

import sys
from pathlib import Path

import pytest

from tools import run_release_recovery_drill as drill


@pytest.mark.parametrize(
    "dsn",
    [
        "host=example.com port=5432 dbname=postgres user=postgres",
        "host=127.0.0.1 hostaddr=192.0.2.1 port=5432 dbname=postgres user=postgres",
        "host=127.0.0.1 port=5432 dbname=spina_production user=postgres",
        "port=5432 dbname=postgres user=postgres",
        "host=127.0.0.1 dbname=postgres user=postgres",
        "host=127.0.0.1 port=5432 dbname=postgres",
        "host=127.0.0.1 port=5432 dbname=postgres user=postgres service=remote",
        "host=127.0.0.1 port=5432 dbname=postgres user=postgres options='-c search_path=unsafe'",
        "host=127.0.0.1,example.com port=5432 dbname=postgres user=postgres",
    ],
)
def test_rejects_remote_implicit_or_non_administrative_endpoint(dsn):
    with pytest.raises(drill.DrillError):
        drill.safe_admin_params(dsn)


def test_loopback_is_pinned_and_secrets_never_enter_pg_arguments(monkeypatch):
    monkeypatch.setenv("PGHOST", "production.example")
    monkeypatch.setenv("PGSERVICE", "production")
    monkeypatch.setenv("PGOPTIONS", "-c search_path=unsafe")
    params = drill.safe_admin_params(
        "host=localhost port=5432 dbname=postgres user=postgres password=secret"
    )
    environment = drill.pg_environment(params, "spina_recovery_source_" + "a" * 24)
    assert environment["PGHOSTADDR"] == "127.0.0.1"
    assert environment["PGPASSWORD"] == "secret"
    assert "PGSERVICE" not in environment
    assert "PGOPTIONS" not in environment
    assert "production.example" not in environment.values()


def test_missing_disposable_opt_in_never_connects(monkeypatch, tmp_path):
    def unexpected(*args, **kwargs):
        pytest.fail("An unapproved drill must not connect")

    monkeypatch.setattr(drill.psycopg, "connect", unexpected)
    with pytest.raises(drill.DrillError, match="explicit"):
        drill.run_drill("", allow_disposable=False, pg_bin=tmp_path)


def test_file_restore_requires_nonempty_exact_bytes_and_detects_corruption(tmp_path):
    original = tmp_path / "original"
    original.mkdir()
    (original / "proof.bin").write_bytes(b"synthetic private evidence")
    expected = drill.file_manifest(original)
    restored = tmp_path / "restored"
    restored.mkdir()
    (restored / "proof.bin").write_bytes(b"synthetic private evidence")
    drill.verify_files(restored, expected)
    (restored / "proof.bin").write_bytes(b"synthetic PRIVATE evidence")
    with pytest.raises(drill.DrillError, match="integrity"):
        drill.verify_files(restored, expected)
    (restored / "proof.bin").unlink()
    with pytest.raises(drill.DrillError, match="integrity"):
        drill.verify_files(restored, expected)


def test_file_restore_rejects_extra_files_and_empty_backup(tmp_path):
    with pytest.raises(drill.DrillError, match="nonempty"):
        drill.file_manifest(tmp_path)
    (tmp_path / "empty.bin").write_bytes(b"")
    with pytest.raises(drill.DrillError, match="nonempty"):
        drill.file_manifest(tmp_path)
    (tmp_path / "empty.bin").write_bytes(b"synthetic")
    expected = drill.file_manifest(tmp_path)
    (tmp_path / "unexpected.bin").write_bytes(b"unexpected")
    with pytest.raises(drill.DrillError, match="integrity"):
        drill.verify_files(tmp_path, expected)


def test_unsafe_cleanup_target_is_rejected_before_sql():
    class Admin:
        def execute(self, *args):
            pytest.fail("No SQL may run for an unsafe cleanup target")

    with pytest.raises(drill.DrillError, match="owned"):
        drill.drop_owned_database(Admin(), "spina_production", {"spina_production"})
    with pytest.raises(drill.DrillError, match="owned"):
        drill.drop_owned_database(Admin(), "spina_recovery_source_" + "a" * 24, set())


def test_command_failure_does_not_expose_credentials_or_tool_output(
    monkeypatch, tmp_path
):
    def fail(*args, **kwargs):
        return drill.subprocess.CompletedProcess(
            args[0], 1, b"secret", b"password=secret"
        )

    monkeypatch.setattr(drill.subprocess, "run", fail)
    with pytest.raises(drill.DrillError) as caught:
        drill.run_pg(Path(tmp_path / "pg_dump"), [], {})
    assert "secret" not in str(caught.value)
    assert "pg_dump failed" in str(caught.value)


def test_schema_digest_ignores_only_dump_restrict_nonce():
    first = b"\\restrict nonce1\nCREATE TABLE core.test(id int);\n\\unrestrict nonce1\n"
    second = (
        b"\\restrict nonce2\nCREATE TABLE core.test(id int);\n\\unrestrict nonce2\n"
    )
    assert drill.schema_digest(first) == drill.schema_digest(second)
    assert drill.schema_digest(first) != drill.schema_digest(
        second.replace(b"int", b"text")
    )


def test_schema_digest_uses_postgres_view_deparse_but_preserves_acl_and_predicates():
    nested = " SELECT a FROM core.example WHERE ((a > 0 AND b > 0) AND c > 0);"
    flat = " SELECT a FROM core.example WHERE (a > 0 AND b > 0 AND c > 0);"
    canonical = " SELECT a FROM core.example\n  WHERE a > 0 AND b > 0 AND c > 0;"
    prefix = "CREATE VIEW core.example_view AS\n"
    acl = "\nREVOKE ALL ON TABLE core.example_view FROM PUBLIC;\n"
    left = (prefix + nested + acl).encode()
    right = (prefix + flat + acl).encode()
    left_views = [("core.example_view", nested, canonical)]
    right_views = [("core.example_view", flat, canonical)]
    assert drill.schema_digest(left, left_views) == drill.schema_digest(
        right, right_views
    )
    assert drill.schema_digest(left, left_views) != drill.schema_digest(
        right.replace(b"REVOKE", b"GRANT"), right_views
    )
    changed = canonical.replace("c > 0", "c > 1")
    assert drill.schema_digest(left, left_views) != drill.schema_digest(
        right, [("core.example_view", flat, changed)]
    )
    with pytest.raises(drill.DrillError, match="view definition"):
        drill.schema_digest(left, right_views)


def test_partial_drill_failure_cleans_only_created_databases_and_temporary_files(
    monkeypatch, tmp_path
):
    for name in ("pg_dump", "pg_restore"):
        (tmp_path / (name + (".exe" if drill.os.name == "nt" else ""))).touch()
    created, dropped, temporary = [], [], []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, statement):
            created.append(statement.as_string())

    original_temporary = drill.tempfile.TemporaryDirectory

    def capture_temporary(*args, **kwargs):
        directory = original_temporary(*args, **kwargs)
        temporary.append(Path(directory.name))
        return directory

    def fail_bootstrap(dsn):
        raise drill.DrillError("Injected migration failure")

    monkeypatch.setattr(drill.tempfile, "TemporaryDirectory", capture_temporary)
    monkeypatch.setattr(drill.psycopg, "connect", lambda *args, **kwargs: Connection())
    monkeypatch.setattr(drill, "bootstrap", fail_bootstrap)
    monkeypatch.setattr(
        drill.disposable, "_drop_database", lambda admin, name: dropped.append(name)
    )
    monkeypatch.setattr(drill.disposable, "_database_exists", lambda admin, name: False)
    with pytest.raises(drill.DrillError, match="Injected migration"):
        drill.run_drill(
            "host=127.0.0.1 port=5432 dbname=postgres user=postgres",
            allow_disposable=True,
            pg_bin=tmp_path,
        )
    assert len(created) == len(dropped) == 2
    assert all(drill.DATABASE_NAME.fullmatch(name) for name in dropped)
    assert all(any(name in statement for statement in created) for name in dropped)
    assert temporary and all(not path.exists() for path in temporary)


def test_output_cannot_overwrite_private_dsn(monkeypatch, tmp_path):
    dsn = tmp_path / "admin.txt"
    dsn.write_text("password=secret", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "drill",
            "--admin-dsn-file",
            str(dsn),
            "--output",
            str(dsn),
            "--pg-bin",
            str(tmp_path),
        ],
    )
    with pytest.raises(SystemExit):
        drill.main()
    assert dsn.read_text(encoding="utf-8") == "password=secret"

"""Opt-in committed native renewal recovery in disposable copies of preserved history.

The supplied history database is read-only. Only newly named task databases may
be committed or dropped; original source dates and private capture stay intact.
"""

import json
import os
import re
import shutil
from contextlib import nullcontext
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
import run_release_recovery_drill as recovery
import run_stage5d17_disposable_postgres_validation as bootstrap
from gilbic_backend.loan_payout_accounting_repository import (
    PostgresLoanPayoutAccountingRepository,
)
from gilbic_backend.native_regular_evidence import verify_native_regular_files
from gilbic_backend.office_review_evidence_storage import (
    EvidenceFileError,
    PrivateEvidenceStore,
)
from gilbic_backend.treasury_authorization import TreasuryDenied
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from test_native_current_schema_cycle_postgres import report
from test_native_regular_historical_postgres import dated_native as captured_fixture
from test_native_renewal_lifecycle_postgres import (
    close_completed_native_renewal,
    completed_native_renewal,
)
from test_native_renewal_lifecycle_postgres import dated_native as final_fixture
from test_native_renewal_measurement_postgres import dated_native as measurement_fixture


@pytest.fixture
def isolated_native_recovery(monkeypatch, tmp_path):
    if os.getenv("SPINA_ALLOW_NATIVE_RENEWAL_RESTORE") != "1":
        pytest.skip(
            "Explicit opt-in for committed native renewal dump/restore required"
        )
    assert os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") == "1"
    assert shutil.disk_usage(tmp_path).free >= 250 * 1024**2
    params = bootstrap._safe_local_connection_params(
        os.environ["GILBIC_TEST_DATABASE_URL"]
    )
    assert not {"options", "passfile", "service", "servicefile"}.intersection(params)
    assert re.fullmatch(r"spina_treasury_validation_[a-f0-9]{24}", params["dbname"])
    manifest = json.loads(Path(os.environ["SPINA_NATIVE_HISTORY_MANIFEST"]).read_text())
    with psycopg.connect(make_conninfo(**params), row_factory=dict_row) as history:
        assert history.execute(
            "SELECT kind FROM accounting.book_identity"
        ).fetchone() == {"kind": "synthetic"}
        assert history.execute(
            "SELECT status FROM treasury.loan_payouts WHERE id=%s AND loan_id=%s",
            (UUID(manifest["payout_id"]), UUID(manifest["loan_id"])),
        ).fetchone() == {"status": "completed"}
    token = uuid4().hex[:24]
    names = [
        "spina_treasury_validation_" + token,
        "spina_accounting_current_restore_" + token,
    ]
    assert params["dbname"] not in names
    created = []
    with psycopg.connect(
        make_conninfo(**(params | {"dbname": "postgres"})), autocommit=True
    ) as admin:
        try:
            admin.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                    sql.Identifier(names[0]), sql.Identifier(params["dbname"])
                )
            )
            created.append(names[0])
            admin.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                    sql.Identifier(names[1])
                )
            )
            created.append(names[1])
            source = make_conninfo(**(params | {"dbname": names[0]}))
            monkeypatch.setenv("GILBIC_TEST_DATABASE_URL", source)
            monkeypatch.setenv("GILBIC_DATABASE_URL", source)
            yield {
                "params": params,
                "names": names,
                "source": source,
                "restore": make_conninfo(**(params | {"dbname": names[1]})),
            }
        finally:
            for name in reversed(created):
                assert re.fullmatch(
                    r"spina_(treasury_validation|accounting_current_restore)_[a-f0-9]{24}",
                    name,
                )
                assert name != params["dbname"]
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def build_committed_renewal(case, monkeypatch, tmp_path):
    """Build through real source writers, commit only the newly created clone."""
    captured = captured_fixture.__wrapped__()
    try:
        source = next(captured)
        assert source["conn"].info.dbname == case["names"][0]
        source = measurement_fixture.__wrapped__(source)
        source = final_fixture.__wrapped__(source)
        f = completed_native_renewal(source, monkeypatch, tmp_path, close_prefix=True)
        close_completed_native_renewal(f, monkeypatch)
        f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")
        f["conn"].commit()
        return f
    finally:
        captured.close()


def renewal_recovery_invariants(conn, f):
    """Read current source, close and report proofs without exposing private rows."""
    with conn.cursor(row_factory=dict_row) as cursor:
        claims = cursor.execute(
            "SELECT stage,exact_posted,correction_pending FROM accounting.loan_payout_accounting_posting_status "
            "WHERE payout_id=%s ORDER BY stage",
            (f["payout_id"],),
        ).fetchall()
        assert len(claims) == 2 and all(
            row["exact_posted"] and not row["correction_pending"] for row in claims
        )
        assert cursor.execute(
            "SELECT accounting.native_renewal_structural_exact(%s) AS exact",
            (f["journal_id"],),
        ).fetchone()["exact"]
        for period, loan in (
            (f["period_id"], f["old_loan_id"]),
            (f["application_period_id"], f["old_loan_id"]),
            (f["application_period_id"], f["loan_id"]),
        ):
            assert cursor.execute(
                "SELECT accounting.period_elapsed_loan_assessment_exact(%s,%s) AS exact",
                (period, loan),
            ).fetchone()["exact"]
        for period in (f["period_id"], f["application_period_id"]):
            assert (
                cursor.execute(
                    "SELECT status FROM accounting.fiscal_periods WHERE id=%s",
                    (period,),
                ).fetchone()["status"]
                == "closed"
            )
            assert cursor.execute(
                "SELECT accounting.period_review_manifest_state(%s) AS state", (period,)
            ).fetchone()["state"]["current"]
        source = cursor.execute(
            "SELECT accounting.native_regular_segment_origin(%s,%s) AS source",
            (f["loan_id"], f["today"]),
        ).fetchone()["source"]
        assert source["ready"]
    return {
        "current_report": report(f | {"conn": conn}, f["application_period_id"]),
        "prefix_report": report(f | {"conn": conn}, f["period_id"]),
        "source_digest": source["source_digest"],
    }


def test_completed_native_renewal_restores_rows_private_files_close_and_retries(
    isolated_native_recovery, monkeypatch, tmp_path
):
    case = isolated_native_recovery
    f = build_committed_renewal(case, monkeypatch, tmp_path)
    private = f["private_store"].root
    expected_files = recovery.file_manifest(private)
    assert expected_files
    with psycopg.connect(case["source"]) as conn:
        expected_rows = recovery.database_snapshot(conn)
        expected = renewal_recovery_invariants(conn, f)
    assert expected_rows["accounting.native_regular_asset_lineage"]["rows"] == 1
    assert expected_rows["accounting.period_close_postings"]["rows"] == 2
    suffix = ".exe" if os.name == "nt" else ""
    binary = Path(os.environ["SPINA_POSTGRES_BIN"]) / ("pg_dump" + suffix)
    restore = binary.with_name("pg_restore" + suffix)
    assert binary.is_file() and restore.is_file()
    expected_schema = recovery.schema_snapshot(
        binary,
        recovery.pg_environment(case["params"], case["names"][0]),
        case["source"],
    )
    archive = tmp_path / "completed-native-renewal.dump"
    recovery.run_pg(
        binary,
        ["--format=custom", "--file", str(archive)],
        recovery.pg_environment(case["params"], case["names"][0]),
    )
    assert archive.stat().st_size > 0
    restored_private = tmp_path / "restored-private"
    shutil.copytree(private, restored_private)
    recovery.run_pg(
        restore,
        ["--exit-on-error", "--no-owner", "--dbname", case["names"][1], str(archive)],
        recovery.pg_environment(case["params"], case["names"][1]),
    )
    recovery.verify_files(restored_private, expected_files)
    assert (
        recovery.schema_snapshot(
            binary,
            recovery.pg_environment(case["params"], case["names"][1]),
            case["restore"],
        )
        == expected_schema
    )
    with psycopg.connect(case["restore"]) as conn:
        recovery.verify_database(conn, expected_rows)
        assert renewal_recovery_invariants(conn, f) == expected
        conn.row_factory = dict_row
        store = PrivateEvidenceStore(restored_private)
        origin = conn.execute(
            "SELECT accounting.native_regular_segment_origin(%s,%s) AS source",
            (f["loan_id"], f["today"]),
        ).fetchone()["source"]
        verify_native_regular_files(origin, store=store)
        repository = PostgresLoanPayoutAccountingRepository(
            connection_factory=lambda: nullcontext(conn),
            evidence_store=store,
            office_evidence_store=store,
        )
        actor = f["actor"]
        assert repository.post(actor, **f["posting_args"]) == f["posted"]
        bundle = restored_private / f"{UUID(str(f['measurement_bundle_id'])).hex}.bin"
        original = bundle.read_bytes()
        try:
            bundle.write_bytes(b"Independent restored private-file corruption")
            with pytest.raises(EvidenceFileError):
                verify_native_regular_files(origin, store=store)
            assert repository.post(actor, **f["posting_args"]) == f["posted"]
            assert (
                repository.retain_renewal_measurement(actor, **f["retention_args"])
                == f["renewal_review"]
            )
        finally:
            bundle.write_bytes(original)
        with pytest.raises(TreasuryDenied), conn.transaction():
            conn.execute(
                "DELETE FROM core.role_permissions rp USING core.user_roles ur "
                "WHERE ur.role_id=rp.role_id AND ur.user_id=%s "
                "AND rp.permission_code='accounting.renewal_treatment_decision.manage'",
                (actor.user_id,),
            )
            repository.post(actor, **f["posting_args"])
        conn.rollback()
        conn.row_factory = psycopg.rows.tuple_row
        recovery.verify_database(conn, expected_rows)
    recovery.verify_files(private, expected_files)
    recovery.verify_files(restored_private, expected_files)

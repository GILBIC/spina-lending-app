"""Original Regular cash boundaries retain exact origin, prefix and liability proof."""

from contextlib import contextmanager
from datetime import datetime, time, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest
import test_ecl_read_only_measurement_postgres as measurement
from psycopg.rows import dict_row, tuple_row
from psycopg.types.json import Jsonb
from test_elapsed_period_assessment_postgres import _collection
from test_regular_treasury_application_postgres import (
    MIGRATION,
    actual_regular_source,
    coordinates,
    posted,
    retained,
)
from test_regular_treasury_application_postgres import (
    regular_application as _regular_application,
)
from test_source_close_guard_postgres import _connect
from test_treasury_receipt_accounting_postgres import seed
from treasury_application_accounting_test_support import (
    additional_loan_gl,
    application_coordinates,
    application_post,
    application_prepare,
    create_application_source,
)

regular_application = _regular_application


def append_collection(f, day):
    f["conn"].row_factory = tuple_row
    try:
        return _collection(f | {"actor": f["actor_id"]}, day)
    finally:
        f["conn"].row_factory = dict_row


def status(f):
    return (
        f["conn"]
        .execute(
            "SELECT exact_posted,correction_pending FROM "
            "accounting.treasury_application_posting_status WHERE application_id=%s",
            (f["application"],),
        )
        .fetchone()
    )


def test_original_bank_release_uses_the_existing_protected_cash_identity(
    monkeypatch, tmp_path
):
    def record_bank_release(conn, *, loan_id, actor_id, business_date, reference):
        return conn.execute(
            "SELECT accounting.record_loan_disbursement_evidence("
            "%s,%s,'new_loan_release',%s,%s,5000,0,0,'cash_bank_gcash',%s,%s)",
            (
                loan_id,
                actor_id,
                business_date,
                datetime.combine(
                    business_date, time(10), tzinfo=timezone(timedelta(hours=8))
                ),
                reference,
                "Synthetic original bank-funded protected release",
            ),
        ).fetchone()[0]

    monkeypatch.setattr(measurement, "_record_release", record_bank_release)
    with _connect() as conn:
        try:
            f = actual_regular_source(conn, monkeypatch, tmp_path)
            source = coordinates(f)
            anchor = source["origin"]["anchor"]
            assert (
                conn.execute(
                    "SELECT a.system_key FROM accounting.journal_lines l "
                    "JOIN accounting.accounts a ON a.id=l.account_id "
                    "WHERE l.journal_entry_id=%s AND l.credit>0",
                    (anchor["journal_entry_id"],),
                ).fetchone()["system_key"]
                == "cash_bank_gcash"
            )
            posted(f, retained(f))
            assert status(f) == {
                "exact_posted": True,
                "correction_pending": False,
            }
            conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        finally:
            conn.rollback()


@pytest.mark.parametrize("regular_application", [True], indirect=True)
@pytest.mark.parametrize("permission", ["private_history", "journal"])
def test_prefix_application_rechecks_current_authority(regular_application, permission):
    f = regular_application
    prepared = retained(f)
    if permission == "private_history":
        f["conn"].execute(
            "UPDATE treasury.account_access SET private_history=false "
            "WHERE account_id=%s AND user_id=%s",
            (f["wallet"], f["actor_id"]),
        )
    else:
        f["conn"].execute(
            "DELETE FROM core.role_permissions WHERE permission_code='accounting.journal.manage'"
        )
    with pytest.raises(psycopg.Error), f["conn"].transaction():
        posted(f, prepared)
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) n FROM accounting.treasury_application_postings WHERE application_id=%s",
            (f["application"],),
        )
        .fetchone()["n"]
        == 0
    )


@pytest.mark.parametrize("regular_application", [True], indirect=True)
def test_prefix_does_not_admit_unrelated_manual_loan_controls(regular_application):
    f = regular_application
    with (
        pytest.raises(psycopg.Error, match="prefix-aware"),
        f["conn"].transaction(),
    ):
        additional_loan_gl(f, code="1100")
    posted(f, retained(f))
    assert status(f) == {"exact_posted": True, "correction_pending": False}


@pytest.mark.parametrize("change", ["loan_control", "borrower_liability"])
def test_regular_application_rejects_unknown_authoritative_ledger_sources(
    regular_application, change
):
    f = regular_application
    prepared = retained(f)
    additional_loan_gl(
        f,
        code="1100" if change == "loan_control" else "2200",
        loan=change == "loan_control",
    )
    with (
        pytest.raises(psycopg.Error, match="GL|liability|reconcil"),
        f["conn"].transaction(),
    ):
        posted(f, prepared)


@pytest.mark.parametrize("code", ["2200", "1100"])
def test_offsetting_unknown_controls_cannot_hide_behind_equal_net_balance(
    regular_application, code
):
    f = regular_application
    additional_loan_gl(f, code=code, loan=code == "1100")
    reverse = (
        f["conn"]
        .execute(
            "SELECT accounting.create_manual_journal_draft(%s,%s,%s,%s) id",
            (
                f["day"],
                "Synthetic offsetting unsupported borrower liability",
                f["actor_id"],
                Jsonb(
                    [
                        {"account_code": "3000", "debit": "1.00", "credit": "0.00"},
                        {"account_code": code, "debit": "0.00", "credit": "1.00"},
                    ]
                ),
            ),
        )
        .fetchone()["id"]
    )
    f["conn"].execute(
        "UPDATE accounting.journal_lines SET client_id=%s,loan_id=%s WHERE journal_entry_id=%s "
        "AND account_id=(SELECT id FROM accounting.accounts WHERE code=%s)",
        (f["client"], f["loan"] if code == "1100" else None, reverse, code),
    )
    f["conn"].execute(
        "SELECT accounting.post_manual_journal_entry(%s,%s)",
        (reverse, f["actor_id"]),
    )
    with pytest.raises(psycopg.Error, match="GL|liability|reconcil"):
        coordinates(f)


@pytest.mark.parametrize("field", ["normal_balance", "is_posting"])
def test_original_cash_account_meaning_must_remain_compatible(
    regular_application, field
):
    f = regular_application
    if field == "normal_balance":
        f["conn"].execute(
            "UPDATE accounting.accounts SET normal_balance='credit' WHERE code='1010'"
        )
    else:
        f["conn"].execute(
            "UPDATE accounting.accounts SET is_posting=false WHERE code='1010'"
        )
    with pytest.raises(psycopg.Error, match="cash chart|meaning|origin"):
        coordinates(f)


@pytest.mark.parametrize("timing", ["earlier", "later"])
def test_late_actual_cash_is_retained_with_cutoff_sensitive_correction_status(
    regular_application, timing
):
    f = regular_application
    prepared = retained(f)
    journal = posted(f, prepared)
    # Discharge this posting's deferred audit before a separately recorded fact.
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")
    day = f["day"] + timedelta(days=-1 if timing == "earlier" else 1)
    assert append_collection(f, day) is not None
    assert status(f) == {
        "exact_posted": True,
        "correction_pending": timing == "earlier",
    }
    assert posted(f, prepared) == journal


def test_source_changed_before_same_transaction_commit_cannot_certify_original_proof(
    regular_application,
):
    f = regular_application
    posted(f, retained(f))
    append_collection(f, f["day"] - timedelta(days=1))
    with pytest.raises(psycopg.Error, match="source or fiscal prefix changed"):
        f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")


@pytest.mark.parametrize("change", ["semantic", "display_and_retirement"])
def test_historical_regular_proof_tracks_chart_meaning_not_display_state(
    regular_application, change
):
    f = regular_application
    prepared = retained(f)
    journal = posted(f, prepared)
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")
    if change == "semantic":
        f["conn"].execute(
            "UPDATE accounting.accounts SET normal_balance='debit' WHERE code='4000'"
        )
    else:
        f["conn"].execute(
            "UPDATE accounting.accounts SET name=name||' retired',is_active=false "
            "WHERE code IN('1100','1120','4000')"
        )
    assert status(f) == {
        "exact_posted": True,
        "correction_pending": change == "semantic",
    }
    assert posted(f, prepared) == journal


@pytest.mark.parametrize("regular_application", [True], indirect=True)
def test_generic_native_journal_still_requires_exact_prefix_admission_and_audit(
    regular_application,
):
    f = regular_application
    prepared = retained(f)
    snapshot = prepared["snapshot"]
    conn = f["conn"]
    conn.execute(
        "SELECT set_config('accounting.treasury_application_post',%s,true)",
        (str(prepared["id"]),),
    )
    entry = conn.execute(
        "INSERT INTO accounting.journal_entries(fiscal_period_id,posting_date,description,"
        "source_type,source_reference,source_event_key,created_by_user_id) "
        "VALUES(%s,%s,'Synthetic exact source-key attempt','treasury_receipt_application',%s,%s,%s) RETURNING id",
        (
            f["period"],
            f["day"],
            str(f["application"]),
            snapshot["source_event_key"],
            f["actor_id"],
        ),
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO accounting.journal_lines(journal_entry_id,line_number,account_id,debit,credit,client_id,loan_id) "
        "SELECT %s,x.line_number,x.account_id,x.debit,x.credit,x.client_id,x.loan_id "
        "FROM jsonb_to_recordset(%s) x(line_number INT,account_id UUID,debit NUMERIC,credit NUMERIC,client_id UUID,loan_id UUID)",
        (entry, Jsonb(snapshot["lines"])),
    )
    # Exact lines can pass admission, but a generic call cannot manufacture the
    # immutable posting audit. The deferred original146 guard still applies.
    conn.execute("SELECT accounting.post_journal_entry(%s,%s)", (entry, f["actor_id"]))
    with pytest.raises(psycopg.Error, match="audit"):
        conn.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_regular_origin_is_timezone_stable_and_migration_replay_preserves_review(
    regular_application,
):
    f = regular_application
    source = coordinates(f)
    f["conn"].execute("SET LOCAL timezone='Pacific/Honolulu'")
    assert coordinates(f) == source
    prepared = retained(f)
    migration = MIGRATION.read_text(encoding="utf-8").strip()
    f["conn"].execute(migration[len("BEGIN;") : -len("COMMIT;")])
    assert coordinates(f) == source
    posted(f, prepared)
    assert status(f) == {"exact_posted": True, "correction_pending": False}


def test_unrelated_product_cannot_use_retained_regular_admission(regular_application):
    f = regular_application
    prepared = retained(f)
    f["conn"].execute(
        "UPDATE lending.loan_types SET calculation_mode='seven_by_seven' "
        "WHERE id=(SELECT loan_type_id FROM lending.loans WHERE id=%s)",
        (f["loan"],),
    )
    with pytest.raises(psycopg.Error), f["conn"].transaction():
        posted(f, prepared)
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) n FROM accounting.treasury_application_postings WHERE application_id=%s",
            (f["application"],),
        )
        .fetchone()["n"]
        == 0
    )


def test_regular_confirmation_cannot_reuse_another_actor(
    regular_application,
):
    f = regular_application
    prepared = retained(f)
    with pytest.raises(psycopg.Error), f["conn"].transaction():
        f["conn"].execute(
            "SELECT accounting.post_treasury_application(%s,%s,%s,%s)",
            (
                prepared["id"],
                prepared["source_digest"],
                prepared["confirmation_token"],
                uuid4(),
            ),
        )
    assert posted(f, prepared)


def test_regular_repository_checks_actual_evidence_bytes_and_preserves_exact_retry(
    regular_application, tmp_path
):
    from gilbic_backend.office_review_evidence_storage import PrivateEvidenceStore
    from gilbic_backend.treasury_application_accounting_repository import (
        PostgresTreasuryApplicationAccountingRepository,
    )
    from gilbic_backend.treasury_authorization import TreasuryUnavailable
    from treasury_test_support import PDF

    f = regular_application

    @contextmanager
    def transaction():
        with f["conn"].transaction():
            yield f["conn"]

    store = PrivateEvidenceStore(tmp_path / "regular-private")
    repository = PostgresTreasuryApplicationAccountingRepository(
        connection_factory=transaction, evidence_store=store
    )
    source = repository.review(f["actor"], application_id=f["application"])
    assert source["product_model"] == "fixed_daily"
    assert not {"origin", "prefix_claims", "liability_ledger_evidence"}.intersection(
        source
    )
    preparation = repository.prepare(
        f["actor"],
        application_id=f["application"],
        source_digest=source["source_digest"],
        request_id=uuid4(),
    )["preparation"]
    arguments = {
        "preparation_id": preparation["id"],
        "source_digest": preparation["source_digest"],
        "confirmation_token": preparation["confirmation_token"],
    }
    evidence = tmp_path / "regular-private" / f"{f['evidence'].hex}.bin"
    evidence.write_bytes(b"changed")
    with pytest.raises(TreasuryUnavailable, match="evidence"):
        repository.post(f["actor"], **arguments)
    evidence.write_bytes(PDF)
    result = repository.post(f["actor"], **arguments)
    assert result["posting"]["exact_posted"] is True
    evidence.unlink()
    assert (
        repository.post(f["actor"], **arguments)["journal_entry_id"]
        == result["journal_entry_id"]
    )


def test_existing_seven_by_seven_audit_and_digest_survive_regular_migration_replay(
    monkeypatch,
):
    with _connect() as conn:
        try:
            conn.row_factory = dict_row
            migration = MIGRATION.read_text(encoding="utf-8").strip()
            conn.execute(migration[len("BEGIN;") : -len("COMMIT;")])
            f = create_application_source(
                seed(conn, install_migrations=False), monkeypatch
            )
            source = application_coordinates(f)
            assert "product_model" not in source
            alias = conn.execute(
                "SELECT accounting.treasury_application_7x7_coordinates(%s) source",
                (f["application"],),
            ).fetchone()["source"]
            assert alias == source
            preparation = application_prepare(f)
            journal = application_post(f, preparation)
            original = conn.execute(
                "SELECT snapshot FROM accounting.treasury_application_preparations WHERE id=%s",
                (preparation["id"],),
            ).fetchone()["snapshot"]
            conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
            conn.execute(migration[len("BEGIN;") : -len("COMMIT;")])
            assert status(f) == {"exact_posted": True, "correction_pending": False}
            assert application_post(f, preparation) == journal
            assert (
                conn.execute(
                    "SELECT snapshot FROM accounting.treasury_application_preparations WHERE id=%s",
                    (preparation["id"],),
                ).fetchone()["snapshot"]
                == original
            )
        finally:
            conn.rollback()

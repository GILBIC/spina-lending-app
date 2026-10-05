from uuid import UUID

import test_collector_liability_accounting_postgres as base
from collector_accounting_test_support import (
    MIGRATION,
    SQL_ROOT,
    accepted,
    post,
    prepare,
)
from psycopg import sql
from test_treasury_receipt_accounting_postgres import install

from gilbic_backend import collector_surplus

collector_accounting = base.collector_accounting


def test_installed_adapter_capability_preserves_operational_unidentified_source_state(
    collector_accounting,
):
    f = collector_accounting
    accepted(f)
    source = collector_surplus.source_summary(f["conn"], f["wallet"])
    assert source["gl_posting_available"] is True
    assert source["source_resolved"] is False
    assert source["pending_identification_amount"] == "10.00"
    assert source["accounting"]["automatic_posting"] is False
    assert source["accounting"]["comprehensive_source_coverage"] is False


def test_collector_hook_preserves_prior_manifest_extensions_and_retains_exact_dated_proof(
    collector_accounting,
):
    f = collector_accounting
    conn = f["conn"]
    install(conn, SQL_ROOT / "0150_add_treasury_transfer_accounting.sql")
    install(conn, SQL_ROOT / "0151_add_retained_period_review_manifests.sql")
    # On a current schema 0152 already captured its predecessor. Replaying 0151
    # does not make a replacement public function that original predecessor.
    # Seed the exact prior hook in either schema, then prove its evidence survives.
    captured = conn.execute(
        "SELECT to_regprocedure('accounting.period_review_before_collector_evidence(uuid)') IS NOT NULL AS present"
    ).fetchone()["present"]
    predecessor = (
        "period_review_before_collector_evidence"
        if captured
        else "period_review_additional_evidence"
    )
    conn.execute(
        sql.SQL(
            "CREATE OR REPLACE FUNCTION accounting.{}(p_period uuid) RETURNS jsonb LANGUAGE sql AS $$ SELECT '{{\"prior_extension\":true}}'::jsonb $$"
        ).format(sql.Identifier(predecessor))
    )
    install(conn, MIGRATION)
    empty = conn.execute(
        "SELECT accounting.period_review_additional_evidence(%s) AS result",
        (f["period"],),
    ).fetchone()["result"]
    assert empty == {"prior_extension": True}
    acceptance = accepted(f)
    prepared = prepare(f, "settlement", UUID(acceptance["settlement"]["id"]))
    journal = post(f, prepared)
    conn.execute("SELECT accounting.lock_period_review_additional_sources()")
    snapshot = conn.execute(
        "SELECT accounting.period_review_source_snapshot(%s) AS result", (f["period"],)
    ).fetchone()["result"]
    extra = snapshot["additional_evidence"]
    assert extra["prior_extension"] is True
    assert len(extra["collector_liability"]) == 1
    proof = extra["collector_liability"][0]
    assert proof["posting"]["journal_entry_id"] == str(journal)
    assert proof["preparation"]["source_digest"] == prepared["source_digest"]
    assert proof["preparation"]["snapshot"]["posting_date"] == str(f["day"])
    # The stable public union must still include the separate 0151 manifest gate.
    definition = conn.execute(
        "SELECT pg_get_functiondef('accounting.period_source_blockers(uuid)'::regprocedure) AS body"
    ).fetchone()["body"]
    assert "period_review_manifest_blockers" in definition

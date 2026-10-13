"""Keep selected native fixtures from replaying predecessors over current head."""

import pytest
from test_treasury_receipt_accounting_postgres import install

NATIVE_SCHEMA_BASELINE = pytest.StashKey[dict[str, str] | None]()
CURRENT_HEAD = (
    "accounting.retain_current_credit_risk_review(uuid,uuid,uuid,text,jsonb,uuid)"
)
REQUIRED_CURRENT_HELPERS = (
    "accounting.native_renewal_inherited_credit_review(uuid)",
    "accounting.native_impaired_cash_candidate(uuid,uuid,uuid)",
    "accounting.native_credit_impaired_chain(date,numeric,numeric,numeric,date,date,jsonb)",
)
NATIVE_FIXTURE_MIGRATIONS = {
    "0153_add_treasury_transfer_accounting.sql",
    "0157_add_loan_payout_accounting.sql",
    "0159_add_native_regular_origins.sql",
    "0163_add_native_regular_assessment_integration.sql",
    "0164_bound_accounting_close_lock_waits.sql",
    "0165_add_regular_chronological_cash.sql",
    "0167_add_regular_payoff_accounting.sql",
    "0168_add_native_credit_risk_assessments.sql",
    "0170_add_reporting_source_proof.sql",
}


def current_native_head(conn):
    installed = conn.execute(
        "SELECT to_regprocedure(%s) IS NOT NULL AS installed", (CURRENT_HEAD,)
    ).fetchone()["installed"]
    if installed:
        for signature in REQUIRED_CURRENT_HELPERS:
            assert conn.execute(
                "SELECT to_regprocedure(%s) IS NOT NULL AS installed", (signature,)
            ).fetchone()["installed"], f"Incomplete current native schema: {signature}"
    return installed


def native_schema_definitions(conn):
    # Exact pg_proc bytes include bodies, volatility, configuration and ACLs.
    return {
        row["signature"]: row["digest"]
        for row in conn.execute(
            "SELECT p.oid::regprocedure::text AS signature,md5(to_jsonb(p)::text) AS digest "
            "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname IN ('accounting','lending','treasury','core') "
            "ORDER BY p.oid::regprocedure::text"
        ).fetchall()
    }


def install_native_fixture_migration(conn, path):
    # This is deliberately confined to this fixture chain. Other migration
    # tests keep their explicit replay behavior and cannot silently skip SQL.
    assert path.name in NATIVE_FIXTURE_MIGRATIONS, path.name
    if not current_native_head(conn):
        install(conn, path)


def assert_native_schema_preserved(conn, request):
    before = request.node.stash.get(NATIVE_SCHEMA_BASELINE, None)
    if before is not None:
        assert current_native_head(conn)
        after = native_schema_definitions(conn)
        changed = sorted(
            key
            for key in before.keys() | after.keys()
            if before.get(key) != after.get(key)
        )
        assert not changed, (
            f"Native fixture replaced current-schema pg_proc rows: {changed}"
        )

"""Read-only captured opening plus actual-day operations for the aged proof."""

import json
import os
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext
from pathlib import Path
from uuid import UUID

import psycopg
import pytest
from gilbic_backend.native_regular_evidence import verify_native_regular_files
from gilbic_backend.office_review_evidence_storage import PrivateEvidenceStore
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from run_native_stage3_elapsed_validation import OWNED_NAME, elapsed_gate, read_capture
from test_native_credit_risk_assessment_postgres import lifetime_scenarios


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def independent_interest(gross, allowance, rate, days):
    with localcontext() as context:
        context.prec = 60
        factor = (Decimal(1) + Decimal(str(rate))) ** days - 1
        gross_interest = money(Decimal(str(gross)) * factor)
        net_interest = money((Decimal(str(gross)) - Decimal(str(allowance))) * factor)
        return gross_interest, gross_interest - net_interest


def independent_loss(source, scenarios):
    with localcontext() as context:
        context.prec = 60
        rate = Decimal(str(source["eir"]["daily_eir"]))
        cutoff = date.fromisoformat(source["cutoff_date"])
        weighted = sum(
            Decimal(scenario["probability"])
            * sum(
                Decimal(flow["amount"])
                / (1 + rate)
                ** max((date.fromisoformat(flow["cash_date"]) - cutoff).days, 0)
                for flow in scenario["expected_cash_flows"]
            )
            for scenario in scenarios
        )
        return money(
            max(Decimal(str(source["gross_carrying_amount"])) - weighted, Decimal(0))
        )


def verify_opening(f):
    conn = f["conn"]
    assert conn.execute(
        "SELECT accounting.period_elapsed_loan_assessment_exact(%s,%s) AS exact",
        (f["period_id"], f["loan_id"]),
    ).fetchone()["exact"]
    assert conn.execute(
        "SELECT accounting.period_review_manifest_state(%s) AS value", (f["period_id"],)
    ).fetchone()["value"]["current"]
    row = conn.execute(
        "SELECT as_of_date,confirmation_digest,source_digest FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
        (f["assessment_id"],),
    ).fetchone()
    assert row["as_of_date"] == f["cutoff"]
    assert (
        row["confirmation_digest"] == f["capture"]["assessment"]["confirmation_digest"]
    )
    assert row["source_digest"] == f["capture"]["assessment"]["source_digest"]


@pytest.fixture
def aged_stage3(monkeypatch, tmp_path):
    if os.getenv("SPINA_STAGE3_ELAPSED_PROOF") != "1":
        pytest.skip(
            "NOT VERIFIED: use the dedicated genuine Stage 3 elapsed-proof runner"
        )
    path = Path(os.environ["SPINA_STAGE3_HISTORY_MANIFEST"])
    manifest = read_capture(path)
    dsn = os.environ["GILBIC_TEST_DATABASE_URL"]
    params = conninfo_to_dict(dsn)
    assert params.get("host") == params.get("hostaddr") == "127.0.0.1"
    assert params.get("port") == "55442" and OWNED_NAME.fullmatch(
        params.get("dbname", "")
    )
    assert params["dbname"] != manifest["source_database"]
    assert not set(params) - {
        "host",
        "hostaddr",
        "port",
        "dbname",
        "user",
        "password",
        "sslmode",
        "connect_timeout",
    }
    private = Path(os.environ["SPINA_STAGE3_RESTORED_PRIVATE"])
    store = PrivateEvidenceStore(tmp_path / "private")
    for relative in manifest["private_files"]:
        source = private / relative
        if source.suffix != ".bin":
            continue
        target = store.root / source.name
        if target.exists():
            assert target.read_bytes() == source.read_bytes()
        else:
            target.write_bytes(source.read_bytes())
    monkeypatch.setenv("GILBIC_OFFICE_REVIEW_EVIDENCE_ROOT", str(store.root))
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        try:
            conn.execute("SET LOCAL timezone='UTC'")
            today = conn.execute(
                "SELECT (clock_timestamp() AT TIME ZONE 'Asia/Manila')::date AS day"
            ).fetchone()["day"]
            assert elapsed_gate(manifest, today), (
                "NOT VERIFIED: the actual Manila day has not elapsed"
            )
            f = {
                key: UUID(manifest[key])
                for key in (
                    "loan_id",
                    "client_id",
                    "payout_id",
                    "period_id",
                    "actor_id",
                    "device_id",
                    "wallet_id",
                    "assessment_id",
                )
            }
            f.update(
                conn=conn,
                capture=manifest,
                today=today,
                cutoff=date.fromisoformat(manifest["captured_day"]),
                release_day=date.fromisoformat(manifest["release_date"]),
                private_store=store,
            )
            f["installments"] = conn.execute(
                "SELECT i.due_date,i.contractual_amount FROM lending.first_loan_releases r JOIN lending.loan_contract_installments i ON i.schedule_id=r.schedule_id WHERE r.funding_payout_id=%s ORDER BY i.installment_number",
                (f["payout_id"],),
            ).fetchall()
            assert f["installments"] and today <= max(
                row["due_date"] for row in f["installments"]
            ), "NOT VERIFIED: capture has aged beyond this partial-cash acceptance case"
            verify_opening(f)
            origin = conn.execute(
                "SELECT accounting.regular_original_origin(%s,%s) AS value",
                (f["loan_id"], f["cutoff"]),
            ).fetchone()["value"]
            assert origin["ready"], origin.get("blockers")
            verify_native_regular_files(origin, store=store)
            yield f
        finally:
            conn.rollback()


def retained_cash_review(f, application_id, period_id):
    conn = f["conn"]
    candidate = conn.execute(
        "SELECT accounting.native_impaired_cash_candidate(%s,%s,%s) AS value",
        (period_id, f["loan_id"], application_id),
    ).fetchone()["value"]
    assert candidate["ready"], candidate["blockers"]
    scenarios = lifetime_scenarios(f, candidate)
    expected = independent_loss(candidate["snapshot"], scenarios)
    args = (
        period_id,
        f["loan_id"],
        application_id,
        f["actor_id"],
        candidate["source_digest"],
        Jsonb(scenarios),
        "Actual current expected cash receipts reviewed after the exact protected cash application.",
    )
    statement = "SELECT accounting.record_native_impaired_cash_review(%s,%s,%s,%s,%s,%s,%s) AS id"
    review_id = conn.execute(statement, args).fetchone()["id"]
    assert conn.execute(statement, args).fetchone()["id"] == review_id
    row = conn.execute(
        "SELECT * FROM accounting.native_impaired_cash_reviews WHERE id=%s",
        (review_id,),
    ).fetchone()
    assert money(row["measurement_snapshot"]["ecl_amount"]) == expected
    assert conn.execute(
        "SELECT accounting.native_impaired_cash_review_exact(%s) AS exact", (review_id,)
    ).fetchone()["exact"]
    return candidate, row, expected


def emit_public(name, value):
    root = Path(os.environ["SPINA_STAGE3_PUBLIC_OUTPUT"])
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")

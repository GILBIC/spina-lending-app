"""Historical economic cutoff, actual retention time, and exact EIR/ECL claims."""

import os
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, localcontext
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import test_ecl_read_only_measurement_postgres as measurement
import test_regular_journal_posting_postgres as regular
from psycopg.types.json import Jsonb
from test_proven_source_composition_postgres import _install as install_composition
from test_source_close_guard_postgres import _connect

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0153_add_elapsed_period_assessments.sql"
)
CENT = Decimal("0.01")


def _money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def _seed(conn, *, elapsed_days=7):
    if (
        conn.execute(
            "SELECT to_regprocedure('accounting.period_treasury_application_blockers(uuid)')"
        ).fetchone()[0]
        is None
    ):
        install_composition(conn)
    if (
        MIGRATION.exists()
        and os.getenv("SPINA_ELAPSED_ASSESSMENT_BASELINE") != "1"
        and int(os.getenv("SPINA_CURRENT_SCHEMA_THROUGH", "153")) < 155
    ):
        source = MIGRATION.read_text(encoding="utf-8").strip()
        assert source.startswith("BEGIN;") and source.endswith("COMMIT;")
        conn.execute(source[len("BEGIN;") : -len("COMMIT;")])
    suffix = uuid4().hex
    actor = measurement._actor(conn, suffix)
    book = conn.execute("SELECT id FROM accounting.book_identity").fetchone()
    if book is None:
        book = conn.execute(
            "SELECT accounting.configure_book_identity('synthetic',%s,%s,%s,%s)",
            ("Historical " + suffix, "Synthetic historical cutoff", "c" * 64, actor),
        ).fetchone()
    today = conn.execute("SELECT current_date").fetchone()[0]
    cutoff = today - timedelta(days=5)
    release_day = cutoff - timedelta(days=elapsed_days)
    period = conn.execute(
        "INSERT INTO accounting.fiscal_periods(label,start_date,end_date,status) "
        "VALUES(%s,%s,%s,'open') RETURNING id",
        ("Elapsed " + suffix, release_day, cutoff),
    ).fetchone()[0]
    client, loan = measurement._loan(
        conn, suffix=suffix, actor_id=actor, release_date=release_day
    )
    event = measurement._record_release(
        conn,
        loan_id=loan,
        actor_id=actor,
        business_date=release_day,
        reference="ELAPSED-" + suffix,
    )
    measurement._prepare_and_post_release(
        conn, event_id=event, actor_id=actor, token_char="e"
    )
    measurement._register_schedule(
        conn, loan_id=loan, actor_id=actor, release_date=release_day, suffix=suffix
    )
    evidence = conn.execute(
        "SELECT accounting.record_ecl_forward_looking_evidence("
        "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL)",
        (
            "historical-" + suffix,
            "Synthetic dated economic publication",
            "Published source " + suffix,
            cutoff - timedelta(days=30),
            cutoff - timedelta(days=1),
            cutoff,
            cutoff + timedelta(days=180),
            datetime.combine(cutoff, time(10), tzinfo=timezone.utc),
            cutoff,
            "Review retained now of source actually available at the historical cutoff.",
            actor,
        ),
    ).fetchone()[0]
    rate = conn.execute(
        "SELECT daily_eir FROM accounting.greenfield_regular_eir_anchor_readiness "
        "WHERE loan_id=%s AND readiness_status='greenfield_regular_eir_anchor_ready'",
        (loan,),
    ).fetchone()[0]
    assert rate > 0
    return {
        "conn": conn,
        "actor": actor,
        "book": book[0],
        "period": period,
        "loan": loan,
        "client": client,
        "cutoff": cutoff,
        "release_day": release_day,
        "today": today,
        "evidence": evidence,
        "rate": rate,
        "suffix": suffix,
    }


@pytest.fixture
def elapsed_assessment(request):
    with _connect() as conn:
        try:
            yield _seed(conn, elapsed_days=getattr(request, "param", 7))
        finally:
            conn.rollback()


def _candidate(f):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s)",
            (f["period"], f["loan"]),
        )
        .fetchone()[0]
    )


def _risk(f):
    return {
        "as_of_date": f["cutoff"].isoformat(),
        "stage_label": "stage_1_12_month",
        "default_label": False,
        "write_off_label": "none",
        "recovery_label": "none",
        "primary_evidence_basis": "contractual_dpd",
        "evidence_reference": "Verified signed contract " + f["suffix"],
        "review_note": "Historical conditions reviewed against exact dated contractual sources.",
    }


def _scenarios(f, *, full_contract_amounts=False):
    scenarios = []
    for key, probability, amount in (
        ("base", 0.7, 50),
        ("downside", 0.3, 50 if full_contract_amounts else 40),
    ):
        receipts = defaultdict(int)
        for day in range(1, 121):
            receipts[max(f["release_day"] + timedelta(days=day), f["cutoff"])] += amount
        scenarios.append(
            {
                "scenario_key": key,
                "probability": probability,
                "evidence_reference": "Dated " + key + " case " + f["suffix"],
                "management_rationale": "Explicit historical receipt forecast supported by retained dated sources.",
                "forward_evidence_ids": [str(f["evidence"])],
                "expected_cash_flows": [
                    {"cash_date": day.isoformat(), "amount": amount}
                    for day, amount in sorted(receipts.items())
                ],
            }
        )
    return scenarios


def _expected_interest(f):
    with localcontext() as context:
        context.prec = 50
        return _money(
            Decimal(5000)
            * ((1 + f["rate"]) ** (f["cutoff"] - f["release_day"]).days - 1)
        )


def _expected_ecl(f, scenarios):
    with localcontext() as context:
        context.prec = 50
        contractual_pv = sum(
            Decimal(50)
            / (1 + f["rate"])
            ** (f["release_day"] + timedelta(days=day) - f["cutoff"]).days
            for day in range(1, 121)
        )
        total = Decimal(0)
        for scenario in scenarios:
            expected_pv = sum(
                Decimal(str(flow["amount"]))
                / (1 + f["rate"])
                ** (datetime.fromisoformat(flow["cash_date"]).date() - f["cutoff"]).days
                for flow in scenario["expected_cash_flows"]
            )
            total += Decimal(str(scenario["probability"])) * max(
                contractual_pv - expected_pv, Decimal(0)
            )
        return _money(total)


def _prepare(f, *, scenarios=None, risk=None):
    candidate = _candidate(f)
    assert candidate["ready"], candidate["blockers"]
    prepared = (
        f["conn"]
        .execute(
            "SELECT accounting.prepare_elapsed_loan_period_assessment("
            "%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s)",
            (
                f["period"],
                f["loan"],
                f["actor"],
                candidate["source_digest"],
                Jsonb(_risk(f) if risk is None else risk),
                Jsonb(_scenarios(f) if scenarios is None else scenarios),
                "Reviewed historical sources, raw EIR prefix and explicit probability-weighted forecasts.",
            ),
        )
        .fetchone()[0]
    )
    digest = (
        f["conn"]
        .execute(
            "SELECT confirmation_digest FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
            (prepared,),
        )
        .fetchone()[0]
    )
    return prepared, digest


def _post(f, prepared, digest):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.post_elapsed_loan_period_assessment(%s,%s,%s)",
            (prepared, f["actor"], digest),
        )
        .fetchone()[0]
    )


def _exact(f):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.period_loan_assessment_exact(%s,%s)",
            (f["period"], f["loan"]),
        )
        .fetchone()[0]
    )


def _loan_balances(f):
    return dict(
        f["conn"]
        .execute(
            "SELECT a.code,sum(l.debit-l.credit) FROM accounting.journal_lines l "
            "JOIN accounting.journal_entries j ON j.id=l.journal_entry_id "
            "JOIN accounting.accounts a ON a.id=l.account_id "
            "WHERE j.status='posted' AND j.posting_date<=%s AND l.loan_id=%s "
            "GROUP BY a.code",
            (f["cutoff"], f["loan"]),
        )
        .fetchall()
    )


def _collection(f, day):
    device = uuid4()
    f["conn"].execute(
        "INSERT INTO core.devices(id,user_id,device_identifier_hash,platform,status) "
        "VALUES(%s,%s,%s,'web','active')",
        (device, f["actor"], device.hex),
    )
    return regular._create_collection(
        f["conn"],
        suffix=f["suffix"],
        loan_id=f["loan"],
        client_id=f["client"],
        actor_id=f["actor"],
        device_id=device,
        sequence=1,
        collection_date=day,
        amount="1.00",
    )


def test_historical_cutoff_proposes_real_elapsed_interest(elapsed_assessment):
    f = elapsed_assessment
    candidate = _candidate(f)
    assert candidate["ready"], candidate["blockers"]
    assert candidate["as_of_date"] == str(f["cutoff"])
    assert Decimal(str(candidate["eir"]["incremental_interest"])) == _expected_interest(
        f
    )
    assert _expected_interest(f) > 0
    assert not _exact(f)


def test_historical_preparation_retains_actual_calculation_time_without_journals(
    elapsed_assessment,
):
    f = elapsed_assessment
    before = (
        f["conn"]
        .execute("SELECT count(*) FROM accounting.journal_entries")
        .fetchone()[0]
    )
    prepared, digest = _prepare(f)
    row = (
        f["conn"]
        .execute(
            "SELECT as_of_date,calculated_at,confirmation_digest,measurement_snapshot "
            "FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
            (prepared,),
        )
        .fetchone()
    )
    assert row[0] == f["cutoff"]
    assert row[1].date() == f["today"] and row[1].date() > row[0]
    assert row[2] == digest
    assert Decimal(str(row[3]["ecl_amount"])) == _expected_ecl(f, _scenarios(f))
    assert (
        f["conn"]
        .execute("SELECT count(*) FROM accounting.journal_entries")
        .fetchone()[0]
        == before
    )
    assert not _exact(f)


def test_historical_confirmation_posts_exact_interest_and_allowance_once(
    elapsed_assessment,
):
    f = elapsed_assessment
    prepared, digest = _prepare(f)
    posted = _post(f, prepared, digest)
    assert _exact(f)
    assert _post(f, prepared, digest) == posted
    balances = _loan_balances(f)
    assert balances["1100"] == Decimal("5000.00")
    assert balances.get("1110", 0) == 0
    assert balances["1120"] == _expected_interest(f)
    assert balances["4000"] == -_expected_interest(f)
    assert balances["1190"] == -_expected_ecl(f, _scenarios(f))
    assert balances["5000"] == _expected_ecl(f, _scenarios(f))
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) FROM accounting.period_legacy_source_blockers(%s) "
            "WHERE source_id=%s AND source_type IN ('eir_period_end','ecl_period_end')",
            (f["period"], f["loan"]),
        )
        .fetchone()[0]
        == 0
    )


@pytest.mark.parametrize("elapsed_assessment", [1], indirect=True)
def test_calculated_zero_allowance_never_manufactures_zero_journal(elapsed_assessment):
    f = elapsed_assessment
    prepared, digest = _prepare(f, scenarios=_scenarios(f, full_contract_amounts=True))
    posted = _post(f, prepared, digest)
    row = (
        f["conn"]
        .execute(
            "SELECT eir_journal_entry_id,allowance_journal_entry_id "
            "FROM accounting.loan_elapsed_assessment_postings WHERE id=%s",
            (posted,),
        )
        .fetchone()
    )
    assert row[0] is not None and row[1] is None
    assert _loan_balances(f).get("1190", 0) == 0
    assert _exact(f)


def test_delayed_full_receipt_still_has_positive_timing_loss(elapsed_assessment):
    f = elapsed_assessment
    scenarios = _scenarios(f, full_contract_amounts=True)
    assert _expected_ecl(f, scenarios) == Decimal("3.29")
    prepared, digest = _prepare(f, scenarios=scenarios)
    _post(f, prepared, digest)
    assert _loan_balances(f)["1190"] == Decimal("-3.29")
    assert _exact(f)


@pytest.mark.parametrize("elapsed_assessment", [4], indirect=True)
def test_later_period_recognizes_only_cumulative_prefix_difference(elapsed_assessment):
    f = elapsed_assessment
    first = dict(f, cutoff=f["cutoff"] - timedelta(days=2))
    f["conn"].execute(
        "UPDATE accounting.fiscal_periods SET end_date=%s WHERE id=%s",
        (first["cutoff"], first["period"]),
    )
    # The evidence's economic window must include both actual historical cutoffs.
    first["evidence"] = (
        f["conn"]
        .execute(
            "SELECT accounting.record_ecl_forward_looking_evidence("
            "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL)",
            (
                "prefix-" + f["suffix"],
                "Synthetic earlier dated publication",
                "Earlier forecast " + f["suffix"],
                first["cutoff"] - timedelta(days=30),
                first["cutoff"] - timedelta(days=1),
                first["cutoff"],
                f["cutoff"] + timedelta(days=180),
                datetime.combine(first["cutoff"], time(10), tzinfo=timezone.utc),
                first["cutoff"],
                "Exact earlier published evidence retained during current review.",
                f["actor"],
            ),
        )
        .fetchone()[0]
    )
    prepared, digest = _prepare(first)
    _post(first, prepared, digest)
    f["period"] = (
        f["conn"]
        .execute(
            "INSERT INTO accounting.fiscal_periods(label,start_date,end_date,status) "
            "VALUES(%s,%s,%s,'open') RETURNING id",
            (
                "Next prefix " + f["suffix"],
                first["cutoff"] + timedelta(days=1),
                f["cutoff"],
            ),
        )
        .fetchone()[0]
    )
    candidate = _candidate(f)
    assert candidate["ready"], candidate["blockers"]
    assert _expected_interest(f) == Decimal("62.58")
    reset_from_rounded = _money(
        (Decimal(5000) + _expected_interest(first))
        * (1 + f["rate"]) ** (f["cutoff"] - first["cutoff"]).days
        - Decimal(5000)
    )
    assert reset_from_rounded == Decimal("62.57")
    assert Decimal(
        str(candidate["eir"]["prior_recognized_interest"])
    ) == _expected_interest(first)
    assert Decimal(str(candidate["eir"]["incremental_interest"])) == _expected_interest(
        f
    ) - _expected_interest(first)
    prepared, digest = _prepare(f)
    _post(f, prepared, digest)
    assert _loan_balances(f)["1120"] == _expected_interest(f)
    assert _exact(first) and _exact(f)


@pytest.mark.parametrize("late", [False, True])
def test_actual_cash_is_scoped_by_economic_date(elapsed_assessment, late):
    f = elapsed_assessment
    prepared, digest = _prepare(f)
    _post(f, prepared, digest)
    _collection(f, f["cutoff"] + timedelta(days=1 if late else -1))
    assert _exact(f) is late
    if not late:
        assert not _candidate(f)["ready"]


def test_earlier_unposted_collection_does_not_become_elapsed_proof(elapsed_assessment):
    f = elapsed_assessment
    _collection(f, f["cutoff"] - timedelta(days=1))
    candidate = _candidate(f)
    assert not candidate["ready"]
    assert "collection_prefix_adapter_required" in candidate["blockers"]


def test_changed_source_after_prepare_rolls_back_all_posting(elapsed_assessment):
    f = elapsed_assessment
    prepared, digest = _prepare(f)
    _collection(f, f["cutoff"])
    before = (
        f["conn"]
        .execute("SELECT count(*) FROM accounting.journal_entries")
        .fetchone()[0]
    )
    with (
        pytest.raises(psycopg.Error, match="changed|stale|blocked"),
        f["conn"].transaction(),
    ):
        _post(f, prepared, digest)
    assert (
        f["conn"]
        .execute("SELECT count(*) FROM accounting.journal_entries")
        .fetchone()[0]
        == before
    )
    assert not _exact(f)


def test_future_forecast_cannot_be_relabelled_as_cutoff_evidence(elapsed_assessment):
    f = elapsed_assessment
    assert _candidate(f)["ready"]
    evidence = measurement._forward_evidence(
        f["conn"],
        actor_id=f["actor"],
        key="future-" + f["suffix"],
        reference="Future economic information " + f["suffix"],
    )
    scenarios = _scenarios(f)
    for scenario in scenarios:
        scenario["forward_evidence_ids"] = [str(evidence)]
    with (
        pytest.raises(psycopg.Error, match="cutoff|as.of|evidence"),
        f["conn"].transaction(),
    ):
        _prepare(f, scenarios=scenarios)


def test_scenarios_are_required_and_probability_is_not_defaulted(elapsed_assessment):
    f = elapsed_assessment
    assert _candidate(f)["ready"]
    invalid = deepcopy(_scenarios(f))
    invalid[0]["probability"] = 0.6
    with pytest.raises(psycopg.Error, match="probabilit|sum"), f["conn"].transaction():
        _prepare(f, scenarios=invalid)


def test_current_role_and_exact_confirmation_digest_are_required(elapsed_assessment):
    f = elapsed_assessment
    prepared, digest = _prepare(f)
    with (
        pytest.raises(psycopg.Error, match="digest|confirmation"),
        f["conn"].transaction(),
    ):
        _post(f, prepared, "0" * 64)
    f["conn"].execute(
        "UPDATE core.users SET status='inactive' WHERE id=%s", (f["actor"],)
    )
    with (
        pytest.raises(psycopg.Error, match="Management|actor|permission"),
        f["conn"].transaction(),
    ):
        _post(f, prepared, digest)


def test_retained_economic_measurement_and_journals_are_immutable(elapsed_assessment):
    f = elapsed_assessment
    prepared, digest = _prepare(f)
    _post(f, prepared, digest)
    with (
        pytest.raises(psycopg.Error, match="immutable|protected"),
        f["conn"].transaction(),
    ):
        f["conn"].execute(
            "UPDATE accounting.loan_elapsed_assessment_preparations "
            "SET as_of_date=as_of_date-1 WHERE id=%s",
            (prepared,),
        )
    journal = (
        f["conn"]
        .execute(
            "SELECT eir_journal_entry_id FROM accounting.loan_elapsed_assessment_postings "
            "WHERE preparation_id=%s",
            (prepared,),
        )
        .fetchone()[0]
    )
    with (
        pytest.raises(psycopg.Error, match="immutable|protected|posted"),
        f["conn"].transaction(),
    ):
        f["conn"].execute(
            "UPDATE accounting.journal_lines SET debit=debit+1 "
            "WHERE journal_entry_id=%s AND debit>0",
            (journal,),
        )

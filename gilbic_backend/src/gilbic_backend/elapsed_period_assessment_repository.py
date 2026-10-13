"""Authorized historical calculation review without exposing private snapshots."""

from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .accounting_book_repository import book_identity_payload, read_book_identity
from .accounting_query import require_row
from .native_regular_evidence import verify_native_regular_files
from .office_review_evidence_storage import EvidenceFileError, PrivateEvidenceStore
from .retained_cutoff_assessment_repository import (
    CutoffAssessmentConflict,
    _candidate_connection,
    _error,
    _money,
    _require_actor,
)


def _verify_native_files(source):
    try:
        verify_native_regular_files(source.get("native_origin"))
        for review in source.get("impaired_cash_reviews", []):
            _verify_impaired_cash_files(review["source_snapshot"])
    except EvidenceFileError as error:
        raise CutoffAssessmentConflict(
            "The original signed contract or retained payout evidence is unavailable or changed."
        ) from error


def _verify_impaired_cash_files(source):
    _verify_native_files(source)
    evidence = source["application_preparation"]["snapshot"]["evidence"]
    try:
        PrivateEvidenceStore().read(
            UUID(str(evidence["id"])), evidence["sha256"], evidence["byte_count"]
        )
    except EvidenceFileError as error:
        raise CutoffAssessmentConflict(
            "The retained cash receipt evidence is unavailable or changed."
        ) from error


def _impaired_cash_source_payload(candidate):
    ready = candidate.get("ready") is True
    result = {
        "ready": ready,
        "blockers": candidate.get("blockers", []),
        **{
            key: candidate.get(key) if ready else None
            for key in (
                "source_digest",
                "gross_carrying_amount",
                "opening_assessment_id",
                "opening_cutoff_date",
            )
        },
    }
    if "opening_renewal_review_id" in candidate:
        result["opening_renewal_review_id"] = (
            candidate["opening_renewal_review_id"] if ready else None
        )
    return result


def _impaired_cash_review_payload(row):
    source = row["source_snapshot"]
    measured = row["measurement_snapshot"]
    result = {
        "review_id": str(row["id"]),
        "book_id": str(row["book_id"]),
        "period_id": str(row["fiscal_period_id"]),
        "loan_id": str(row["loan_id"]),
        "application_id": str(row["application_id"]),
        "as_of_date": row["as_of_date"].isoformat(),
        "calculated_at": row["calculated_at"].isoformat(),
        "source_digest": row["source_digest"],
        "confirmation_digest": row["confirmation_digest"],
        "policy_version": measured["policy_version"],
        "loss_basis": measured["loss_basis"],
        "opening_assessment_id": source["opening_assessment"]["id"],
        "opening_cutoff_date": source["opening_assessment"]["as_of_date"],
        "gross_carrying_amount": _money(source["gross_carrying_amount"]),
        "expected_cash_present_value": _money(measured["expected_cash_present_value"]),
        "weighted_expected_cash_present_value_raw": measured[
            "weighted_expected_cash_present_value_raw"
        ],
        "currency_rounding_adjustment": _money(
            measured["currency_rounding_adjustment"]
        ),
        "ecl_amount": _money(measured["ecl_amount"]),
        "scenario_count": len(row["scenarios"]),
        "review_inputs": {
            "scenarios": row["scenarios"],
            "review_rationale": row["review_rationale"],
        },
    }
    if source["opening_assessment"].get("renewal_review_id"):
        result["opening_renewal_review_id"] = source["opening_assessment"][
            "renewal_review_id"
        ]
    return result


def _impaired_cash_review_needs(cursor, source, period_id, loan_id):
    opening = max(
        (x["preparation"] for x in source.get("prior_prefixes", [])),
        key=lambda x: x["as_of_date"],
        default=None,
    )
    cursor.execute(
        "SELECT to_regprocedure('accounting.native_impaired_cash_candidate(uuid,uuid,uuid)') IS NOT NULL AS available"
    )
    if not require_row(cursor.fetchone())["available"]:
        return []
    if not opening:
        cursor.execute(
            "SELECT accounting.native_credit_impaired_opening(%s) AS opening",
            (Jsonb(source),),
        )
        opening = require_row(cursor.fetchone())["opening"]
    if (
        not opening
        or opening["measurement_snapshot"]["risk_review"].get("stage_label")
        != "stage_3_credit_impaired"
        or opening.get("renewal_impairment_opening", {}).get("net_interest_established")
        is False
    ):
        return []
    inherited = bool(opening.get("renewal_review_id"))
    cursor.execute(
        "SELECT DISTINCT ON(t.collection_date) p.application_id,t.collection_date "
        "FROM accounting.treasury_application_postings p "
        "JOIN lending.collection_transactions t ON t.id=p.transaction_id "
        "WHERE p.loan_id=%s AND (t.collection_date>%s OR (%s AND t.collection_date=%s)) AND t.collection_date<%s "
        "AND NOT accounting.regular_application_full_payoff(p.application_id) "
        "ORDER BY t.collection_date,t.accepted_at DESC,t.id DESC",
        (
            loan_id,
            opening["as_of_date"],
            inherited,
            opening["as_of_date"],
            source["cutoff_date"],
        ),
    )
    cash_rows = cursor.fetchall()
    result = []
    for cash in cash_rows:
        cursor.execute(
            "SELECT accounting.native_impaired_cash_candidate(%s,%s,%s) AS candidate",
            (period_id, loan_id, cash["application_id"]),
        )
        candidate = require_row(cursor.fetchone())["candidate"]
        if candidate.get("ready"):
            _verify_impaired_cash_files(candidate["snapshot"])
        cursor.execute(
            "SELECT id,accounting.native_impaired_cash_review_exact(id) AS exact "
            "FROM accounting.native_impaired_cash_reviews WHERE application_id=%s "
            "ORDER BY calculated_at DESC,id DESC LIMIT 1",
            (cash["application_id"],),
        )
        review = cursor.fetchone()
        result.append(
            _impaired_cash_source_payload(candidate)
            | {
                "application_id": str(cash["application_id"]),
                "as_of_date": cash["collection_date"].isoformat(),
                "retained_review_id": str(review["id"]) if review else None,
                "current_confirmation": bool(
                    candidate.get("ready") and review and review["exact"]
                ),
            }
        )
    return result


def _impaired_interest_payload(value):
    if not value:
        return None
    result = {
        key: value.get(key)
        for key in (
            "basis",
            "opening_assessment_id",
            "opening_cutoff_date",
            "impairment_boundary_date",
        )
    } | {
        key: _money(value[key])
        for key in ("gross_interest", "net_interest", "allowance_unwind")
    }
    if value.get("opening_renewal_review_id"):
        result["opening_renewal_review_id"] = value["opening_renewal_review_id"]
    if "currency_rounding_adjustment" in value:
        result["currency_rounding_adjustment"] = _money(
            value["currency_rounding_adjustment"]
        )
    return result


def _prepared_payload(row):
    source = row["source_snapshot"]
    measured = row["measurement_snapshot"]
    result = {
        "preparation_id": str(row["id"]),
        "confirmation_digest": row["confirmation_digest"],
        "source_digest": row["source_digest"],
        "book_id": str(row["book_id"]),
        "period_id": str(row["fiscal_period_id"]),
        "loan_id": str(row["loan_id"]),
        "as_of_date": row["as_of_date"].isoformat(),
        "calculated_at": row["calculated_at"].isoformat(),
        "policy_version": measured["policy_version"],
        "incremental_interest": _money(source["eir"]["incremental_interest"]),
        "cumulative_interest": _money(source["eir"]["cumulative_interest"]),
        "ecl_amount": _money(measured["ecl_amount"]),
        "prior_allowance": _money(measured["prior_allowance"]),
        "allowance_delta": _money(measured["allowance_delta"]),
        "scenario_count": len(measured["scenarios"]),
        "review_inputs": {
            "risk_review": {
                key: row["risk_review"][key]
                for key in (
                    "as_of_date",
                    "stage_label",
                    "default_label",
                    "write_off_label",
                    "recovery_label",
                    "primary_evidence_basis",
                    "evidence_reference",
                    "review_note",
                )
                if key in row["risk_review"]
            },
            "scenarios": [
                {
                    "scenario_key": scenario["scenario_key"],
                    "probability": str(scenario["probability"]),
                    "evidence_reference": scenario["evidence_reference"],
                    "management_rationale": scenario["management_rationale"],
                    "forward_evidence_ids": [
                        str(value) for value in scenario["forward_evidence_ids"]
                    ],
                    "expected_cash_flows": [
                        {
                            "cash_date": flow["cash_date"],
                            "amount": _money(flow["amount"]),
                        }
                        for flow in scenario["expected_cash_flows"]
                    ],
                }
                for scenario in row["scenarios"]
            ],
            "review_rationale": row["review_rationale"],
        },
        "comprehensive_source_coverage": False,
    }
    if source.get("settled_by_exact_payoff") is True:
        review_id = row["risk_review"]["evidence_reference"]
        result.update(settled_by_exact_payoff=True, payoff_review_id=review_id)
        result["review_inputs"] = {
            "payoff_review_id": review_id,
            "review_rationale": row["review_rationale"],
        }
    if source.get("settled_by_exact_renewal") is True:
        review_id = row["risk_review"]["evidence_reference"]
        result.update(settled_by_exact_renewal=True, renewal_review_id=review_id)
        result["review_inputs"] = {
            "renewal_review_id": review_id,
            "review_rationale": row["review_rationale"],
        }
    if measured.get("policy_version") in {
        "historical_native_lifetime_cash_shortfall_v1",
        "historical_native_reviewed_12_month_cash_shortfall_v1",
    }:
        review_id = measured["credit_risk_review_id"]
        result.update(
            credit_risk_review_id=review_id,
            stage_label=measured["risk_review"]["stage_label"],
            default_label=measured["risk_review"]["default_label"],
            loss_horizon=measured["loss_horizon"],
        )
        result["review_inputs"].pop("risk_review", None)
        result["review_inputs"]["credit_risk_review_id"] = review_id
        result["loss_basis"] = measured["loss_basis"]
        if measured["risk_review"]["stage_label"] == "stage_3_credit_impaired":
            result["gross_carrying_amount"] = _money(source["gross_carrying_amount"])
            result["expected_cash_present_value"] = _money(
                measured["expected_cash_present_value"]
            )
            result["weighted_expected_cash_present_value_raw"] = measured[
                "weighted_expected_cash_present_value_raw"
            ]
            result["currency_rounding_adjustment"] = _money(
                measured["currency_rounding_adjustment"]
            )
    impaired_interest = _impaired_interest_payload(
        measured.get("credit_impaired_interest")
    )
    if impaired_interest:
        result["credit_impaired_interest"] = impaired_interest
    return result


def _has_native_credit_risk_history(cursor, loan_id, cutoff):
    cursor.execute(
        "SELECT id FROM accounting.ecl_credit_risk_label_reviews "
        "WHERE loan_id=%s AND (created_at AT TIME ZONE 'Asia/Manila')::date<=%s "
        "ORDER BY review_version DESC LIMIT 1",
        (loan_id, cutoff),
    )
    if cursor.fetchone() is not None:
        return True
    cursor.execute(
        "SELECT to_regprocedure('accounting.native_renewal_inherited_credit_review(uuid)') IS NOT NULL AS available"
    )
    if not require_row(cursor.fetchone())["available"]:
        return False
    cursor.execute(
        "SELECT accounting.native_renewal_inherited_credit_review(%s) IS NOT NULL AS inherited",
        (loan_id,),
    )
    return require_row(cursor.fetchone())["inherited"]


class PostgresElapsedPeriodAssessmentRepository:
    def load_candidate(self, *, period_id, loan_id, actor_user_id):
        try:
            with (
                _candidate_connection() as conn,
                conn.cursor(row_factory=dict_row) as cursor,
            ):
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                _require_actor(cursor, actor_user_id, "accounting.view")
                book = book_identity_payload(read_book_identity(cursor))
                cursor.execute(
                    "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS candidate",
                    (period_id, loan_id),
                )
                candidate = require_row(cursor.fetchone())["candidate"]
                cursor.execute(
                    "SELECT accounting.period_elapsed_loan_assessment_exact(%s,%s) AS exact",
                    (period_id, loan_id),
                )
                exact = require_row(cursor.fetchone())["exact"]
                ready = candidate.get("ready") is True
                source = candidate.get("snapshot", {}) if ready else {}
                if ready:
                    _verify_native_files(source)
                impaired_cash_reviews = _impaired_cash_review_needs(
                    cursor, source, period_id, loan_id
                )
                eligible_risk = None
                impaired_interest = None
                settled = bool(
                    source.get("settled_by_exact_payoff")
                    or source.get("settled_by_exact_renewal")
                )
                if ready and not settled:
                    cursor.execute(
                        "SELECT to_regprocedure('accounting.native_cutoff_credit_risk_review(jsonb,bigint)') IS NOT NULL AS available"
                    )
                    risk = None
                    if require_row(cursor.fetchone())["available"]:
                        cursor.execute(
                            "SELECT accounting.native_cutoff_credit_risk_review(%s) AS review",
                            (Jsonb(source),),
                        )
                        risk = require_row(cursor.fetchone())["review"]
                    if risk and risk["stage_label"] in {
                        "stage_1_12_month",
                        "stage_2_lifetime",
                        "stage_3_credit_impaired",
                    }:
                        eligible_risk = {
                            key: risk[key]
                            for key in (
                                "id",
                                "stage_label",
                                "default_label",
                                "write_off_label",
                                "recovery_label",
                                "evidence_reference",
                                "primary_evidence_basis",
                            )
                        } | {
                            "reviewed_at": risk["created_at"],
                            "as_of_date": candidate.get("as_of_date"),
                        }
                    if (
                        not eligible_risk
                        and source.get("native_origin")
                        and _has_native_credit_risk_history(
                            cursor, loan_id, candidate.get("as_of_date")
                        )
                    ):
                        ready = False
                        candidate["blockers"] = [
                            *candidate.get("blockers", []),
                            "dated_native_credit_risk_review_required",
                        ]
                if (
                    ready
                    and source.get("native_origin")
                    and not source.get("settled_by_exact_renewal")
                ):
                    cursor.execute(
                        "SELECT to_regprocedure('accounting.native_credit_impaired_interest(jsonb)') IS NOT NULL AS available"
                    )
                    if require_row(cursor.fetchone())["available"]:
                        try:
                            with conn.transaction():
                                cursor.execute(
                                    "SELECT accounting.native_credit_impaired_interest(%s) AS interest",
                                    (Jsonb(source),),
                                )
                                impaired_interest = _impaired_interest_payload(
                                    require_row(cursor.fetchone())["interest"]
                                )
                        except psycopg.errors.CheckViolation:
                            ready = False
                            eligible_risk = None
                            candidate["blockers"] = [
                                *candidate.get("blockers", []),
                                "dated_impaired_cash_measurement_required",
                            ]
                payoff_review_id = None
                if source.get("settled_by_exact_payoff") is True:
                    cursor.execute(
                        "SELECT p.snapshot#>>'{measurement,payoff_review_id}' AS id "
                        "FROM accounting.treasury_application_postings a "
                        "JOIN accounting.treasury_application_preparations p ON p.id=a.preparation_id "
                        "WHERE a.loan_id=%s AND p.snapshot->>'accounting_policy_version'="
                        "'treasury_regular_original_full_payoff_v1' "
                        "AND (p.snapshot->>'posting_date')::date<=%s",
                        (loan_id, candidate.get("as_of_date")),
                    )
                    payoff = cursor.fetchone()
                    payoff_review_id = payoff["id"] if payoff else None
                cursor.execute(
                    "SELECT * FROM accounting.loan_elapsed_assessment_preparations "
                    "WHERE fiscal_period_id=%s AND loan_id=%s AND source_digest=%s "
                    "ORDER BY calculated_at DESC,id DESC LIMIT 1",
                    (period_id, loan_id, candidate.get("source_digest")),
                )
                prepared = cursor.fetchone()
                if (
                    prepared
                    and eligible_risk
                    and (
                        prepared["measurement_snapshot"].get("policy_version")
                        != (
                            "historical_native_reviewed_12_month_cash_shortfall_v1"
                            if eligible_risk["stage_label"] == "stage_1_12_month"
                            else "historical_native_lifetime_cash_shortfall_v1"
                        )
                        or prepared["measurement_snapshot"].get("credit_risk_review_id")
                        != eligible_risk["id"]
                    )
                ):
                    prepared = None
                    exact = False
                return {
                    "book": book,
                    "period_id": str(period_id),
                    "loan_id": str(loan_id),
                    "ready": ready,
                    "blockers": candidate.get("blockers", []),
                    "as_of_date": candidate.get("as_of_date"),
                    "source_digest": candidate.get("source_digest") if ready else None,
                    "current_confirmation": bool(ready and exact),
                    "eir": {
                        key: _money(source["eir"][key])
                        for key in (
                            "cumulative_interest",
                            "prior_recognized_interest",
                            "incremental_interest",
                        )
                    }
                    if ready
                    else None,
                    "gross_carrying_amount": _money(source.get("gross_carrying_amount"))
                    if ready
                    else None,
                    "prior_allowance": _money(source.get("prior_allowance"))
                    if ready
                    else None,
                    "days_past_due": source.get("dpd") if ready else None,
                    "settled_by_exact_payoff": source.get("settled_by_exact_payoff")
                    is True,
                    "payoff_review_id": payoff_review_id,
                    "settled_by_exact_renewal": source.get("settled_by_exact_renewal")
                    is True,
                    "renewal_review_id": source.get("renewal_review", {}).get("id")
                    if source.get("settled_by_exact_renewal") is True
                    else None,
                    "eligible_credit_risk_review": eligible_risk,
                    "credit_impaired_interest": impaired_interest,
                    "impaired_cash_reviews": impaired_cash_reviews,
                    "preparation": _prepared_payload(prepared)
                    if ready and prepared
                    else None,
                    "comprehensive_source_coverage": False,
                    "notice": "The economic cutoff is distinct from actual calculation time. Explicit historical risk and forecast inputs are required; unsupported source transitions remain blocked.",
                }
        except psycopg.Error as error:
            raise _error(error) from error

    def prepare(
        self,
        *,
        period_id,
        loan_id,
        expected_book_id,
        source_digest,
        risk_review,
        scenarios,
        review_rationale,
        actor_user_id,
    ):
        try:
            with (
                _candidate_connection() as conn,
                conn.cursor(row_factory=dict_row) as cursor,
            ):
                self._write_authority(
                    cursor,
                    actor_user_id,
                    expected_book_id,
                    "accounting.period.close.prepare",
                )
                cursor.execute(
                    "SELECT accounting.prepare_elapsed_loan_period_assessment(%s,%s,%s,%s,%s,%s,%s) AS id",
                    (
                        period_id,
                        loan_id,
                        actor_user_id,
                        source_digest,
                        Jsonb(risk_review),
                        Jsonb(scenarios),
                        review_rationale,
                    ),
                )
                prepared = require_row(cursor.fetchone())["id"]
                cursor.execute(
                    "SELECT * FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
                    (prepared,),
                )
                row = require_row(cursor.fetchone())
                _verify_native_files(row["source_snapshot"])
                return _prepared_payload(row)
        except psycopg.Error as error:
            raise _error(error) from error

    def confirm(
        self, *, preparation_id, expected_book_id, confirmation_digest, actor_user_id
    ) -> UUID:
        try:
            with (
                _candidate_connection() as conn,
                conn.cursor(row_factory=dict_row) as cursor,
            ):
                self._write_authority(
                    cursor,
                    actor_user_id,
                    expected_book_id,
                    "accounting.period.close.post",
                )
                cursor.execute(
                    "SELECT source_snapshot FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
                    (preparation_id,),
                )
                source = require_row(cursor.fetchone())["source_snapshot"]
                _verify_native_files(source)
                cursor.execute(
                    "SELECT accounting.post_elapsed_loan_period_assessment(%s,%s,%s) AS id",
                    (preparation_id, actor_user_id, confirmation_digest),
                )
                return require_row(cursor.fetchone())["id"]
        except psycopg.Error as error:
            raise _error(error) from error

    def prepare_settled(
        self,
        *,
        period_id,
        loan_id,
        expected_book_id,
        source_digest,
        payoff_review_id,
        review_rationale,
        actor_user_id,
    ):
        return self._prepare_settlement(
            period_id=period_id,
            loan_id=loan_id,
            expected_book_id=expected_book_id,
            source_digest=source_digest,
            evidence_reference=payoff_review_id,
            evidence_basis="exact_payoff",
            review_rationale=review_rationale,
            actor_user_id=actor_user_id,
        )

    def prepare_renewed(
        self,
        *,
        period_id,
        loan_id,
        expected_book_id,
        source_digest,
        renewal_review_id,
        review_rationale,
        actor_user_id,
    ):
        return self._prepare_settlement(
            period_id=period_id,
            loan_id=loan_id,
            expected_book_id=expected_book_id,
            source_digest=source_digest,
            evidence_reference=renewal_review_id,
            evidence_basis="exact_renewal",
            review_rationale=review_rationale,
            actor_user_id=actor_user_id,
        )

    def _prepare_settlement(
        self,
        *,
        period_id,
        loan_id,
        expected_book_id,
        source_digest,
        evidence_reference,
        evidence_basis,
        review_rationale,
        actor_user_id,
    ):
        try:
            with (
                _candidate_connection() as conn,
                conn.cursor(row_factory=dict_row) as cursor,
            ):
                self._write_authority(
                    cursor,
                    actor_user_id,
                    expected_book_id,
                    "accounting.period.close.prepare",
                )
                cursor.execute(
                    "SELECT end_date FROM accounting.fiscal_periods WHERE id=%s",
                    (period_id,),
                )
                period = cursor.fetchone()
                if period is None:
                    raise CutoffAssessmentConflict("The fiscal period is unavailable.")
                risk = {
                    "as_of_date": period["end_date"].isoformat(),
                    "primary_evidence_basis": evidence_basis,
                    "evidence_reference": str(evidence_reference),
                    "review_note": review_rationale,
                }
                cursor.execute(
                    "SELECT accounting.prepare_elapsed_loan_period_assessment(%s,%s,%s,%s,%s,%s,%s) AS id",
                    (
                        period_id,
                        loan_id,
                        actor_user_id,
                        source_digest,
                        Jsonb(risk),
                        Jsonb([]),
                        review_rationale,
                    ),
                )
                prepared = require_row(cursor.fetchone())["id"]
                cursor.execute(
                    "SELECT * FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
                    (prepared,),
                )
                row = require_row(cursor.fetchone())
                _verify_native_files(row["source_snapshot"])
                return _prepared_payload(row)
        except psycopg.Error as error:
            raise _error(error) from error

    def prepare_risk(
        self,
        *,
        period_id,
        loan_id,
        expected_book_id,
        source_digest,
        credit_risk_review_id,
        scenarios,
        review_rationale,
        actor_user_id,
    ):
        try:
            with (
                _candidate_connection() as conn,
                conn.cursor(row_factory=dict_row) as cursor,
            ):
                self._write_authority(
                    cursor,
                    actor_user_id,
                    expected_book_id,
                    "accounting.period.close.prepare",
                )
                cursor.execute(
                    "SELECT accounting.prepare_elapsed_loan_risk_assessment(%s,%s,%s,%s,%s::bigint,%s,%s) AS id",
                    (
                        period_id,
                        loan_id,
                        actor_user_id,
                        source_digest,
                        credit_risk_review_id,
                        Jsonb(scenarios),
                        review_rationale,
                    ),
                )
                prepared = require_row(cursor.fetchone())["id"]
                cursor.execute(
                    "SELECT * FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
                    (prepared,),
                )
                row = require_row(cursor.fetchone())
                _verify_native_files(row["source_snapshot"])
                return _prepared_payload(row)
        except psycopg.Error as error:
            raise _error(error) from error

    def load_impaired_cash(self, *, period_id, loan_id, application_id, actor_user_id):
        try:
            with (
                _candidate_connection() as conn,
                conn.cursor(row_factory=dict_row) as cursor,
            ):
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                _require_actor(cursor, actor_user_id, "accounting.view")
                book = book_identity_payload(read_book_identity(cursor))
                cursor.execute(
                    "SELECT accounting.native_impaired_cash_candidate(%s,%s,%s) AS candidate",
                    (period_id, loan_id, application_id),
                )
                candidate = require_row(cursor.fetchone())["candidate"]
                if candidate.get("ready"):
                    _verify_impaired_cash_files(candidate["snapshot"])
                cursor.execute(
                    "SELECT *,accounting.native_impaired_cash_review_exact(id) AS exact "
                    "FROM accounting.native_impaired_cash_reviews "
                    "WHERE application_id=%s AND fiscal_period_id=%s AND loan_id=%s "
                    "ORDER BY calculated_at DESC,id DESC LIMIT 1",
                    (application_id, period_id, loan_id),
                )
                review = cursor.fetchone()
                return _impaired_cash_source_payload(candidate) | {
                    "book": book,
                    "period_id": str(period_id),
                    "loan_id": str(loan_id),
                    "application_id": str(application_id),
                    "as_of_date": candidate.get("as_of_date"),
                    "retained_review_id": str(review["id"]) if review else None,
                    "current_confirmation": bool(
                        candidate.get("ready") and review and review["exact"]
                    ),
                    "review": _impaired_cash_review_payload(review)
                    if candidate.get("ready") and review and review["exact"]
                    else None,
                }
        except psycopg.Error as error:
            raise _error(error) from error

    def review_impaired_cash(
        self,
        *,
        period_id,
        loan_id,
        application_id,
        expected_book_id,
        source_digest,
        scenarios,
        review_rationale,
        actor_user_id,
    ):
        try:
            with (
                _candidate_connection() as conn,
                conn.cursor(row_factory=dict_row) as cursor,
            ):
                self._write_authority(
                    cursor,
                    actor_user_id,
                    expected_book_id,
                    "accounting.period.close.prepare",
                )
                cursor.execute(
                    "SELECT accounting.record_native_impaired_cash_review(%s,%s,%s,%s,%s,%s,%s) AS id",
                    (
                        period_id,
                        loan_id,
                        application_id,
                        actor_user_id,
                        source_digest,
                        Jsonb(scenarios),
                        review_rationale,
                    ),
                )
                retained = require_row(cursor.fetchone())["id"]
                cursor.execute(
                    "SELECT * FROM accounting.native_impaired_cash_reviews WHERE id=%s",
                    (retained,),
                )
                row = require_row(cursor.fetchone())
                _verify_impaired_cash_files(row["source_snapshot"])
                return _impaired_cash_review_payload(row)
        except psycopg.Error as error:
            raise _error(error) from error

    @staticmethod
    def _write_authority(cursor, actor_user_id, expected_book_id, permission):
        cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
        _require_actor(cursor, actor_user_id, permission)
        book = read_book_identity(cursor)
        if book is None or book.book_id != expected_book_id:
            raise CutoffAssessmentConflict(
                "The confirmed accounting book does not match this deployment."
            )

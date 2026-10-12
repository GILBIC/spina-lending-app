"""Reviewed actual payout legs; retained admission evidence stays private."""

from contextlib import contextmanager
from decimal import Decimal
from uuid import UUID

from psycopg.types.json import Jsonb

from .accounting_query import require_row
from .native_regular_evidence import verify_native_regular_files
from .office_review_evidence_storage import PrivateEvidenceStore
from .treasury_authorization import (
    TreasuryConflict,
    TreasuryDenied,
    TreasuryUnavailable,
    require_actor,
)
from .treasury_receipt_accounting_repository import (
    TreasuryAccountingAccess,
)
from .treasury_repository import json_value


def public_payout_review(source, *, include_digest=True):
    keys = (
        "book_id",
        "payout_id",
        "stage",
        "event_id",
        "loan_id",
        "client_id",
        "disbursement_event_id",
        "treasury_account_id",
        "fiscal_period_id",
        "posting_date",
        "amount",
        "fee",
    )
    result = {key: source[key] for key in keys if key in source}
    if (
        source.get("accounting_policy_version")
        == "native_regular_renewal_completion_v1"
    ):
        result.update(
            {
                key: source[key]
                for key in (
                    "accounting_policy_version",
                    "old_loan_id",
                    "accounting_asset_id",
                    "renewal_review_id",
                    "renewal_decision",
                    "measurement",
                )
            }
        )
        for key in ("predecessor_credit_impaired", "credit_impaired_boundary"):
            if source.get(key) is not None:
                result[key] = source[key]
    if include_digest and "source_digest" in source:
        result["source_digest"] = source["source_digest"]
    result["lines"] = [
        {
            **{
                key: line[key]
                for key in (
                    "line_number",
                    "account_code",
                    "debit",
                    "credit",
                    "loan_id",
                    "component",
                )
                if key in line
            },
            "account_snapshot": {"name": line["account_snapshot"]["name"]},
        }
        for line in source.get("lines", [])
    ]
    return result


class PostgresLoanPayoutAccountingRepository(TreasuryAccountingAccess):
    def __init__(
        self,
        *,
        connection_factory=None,
        evidence_store=None,
        office_evidence_store=None,
    ):
        super().__init__(
            connection_factory=connection_factory, evidence_store=evidence_store
        )
        self._office_store = office_evidence_store

    def _verify_file(self, source):
        super()._verify_file(source)
        if source["stage"] == "completion":
            super()._verify_file({"evidence": source["borrower_evidence"]})
            if (
                source.get("accounting_policy_version")
                == "native_regular_renewal_completion_v1"
            ):
                super()._verify_file({"evidence": source["measurement_evidence"]})
                self._verify_renewal_source(source["origin"]["source"])
                return
            office = source["office_evidence"]
            if self._office_store is None:
                self._office_store = PrivateEvidenceStore()
            self._office_store.read(
                UUID(str(office["request_id"])),
                office["content_sha256"],
                office["byte_count"],
            )

    @contextmanager
    def _transaction(self):
        try:
            with super()._transaction() as conn:
                yield conn
        except TreasuryUnavailable as error:
            if getattr(error.__cause__, "sqlstate", None) in {"40P01", "40001"}:
                raise TreasuryConflict(
                    "Concurrent payout accounting changed the review; retry from current evidence."
                ) from error
            raise

    def _authorize_payout(self, conn, actor, payout_id):
        require_actor(conn, actor)
        conn.execute(
            "SELECT accounting.require_loan_payout_accounting_actor(%s,%s)",
            (actor.user_id, payout_id),
        )

    def _authorize_renewal(self, conn, actor, payout_id):
        self._authorize_payout(conn, actor, payout_id)
        conn.execute(
            "SELECT accounting.require_native_renewal_actor(%s,%s)",
            (actor.user_id, payout_id),
        )

    def _authorize_stage(self, conn, actor, payout_id, stage):
        self._authorize_payout(conn, actor, payout_id)
        if stage == "completion":
            payout = require_row(
                conn.execute(
                    "SELECT source_kind FROM treasury.loan_payouts WHERE id=%s",
                    (payout_id,),
                ).fetchone()
            )
            if payout["source_kind"] == "renewal":
                self._authorize_renewal(conn, actor, payout_id)

    def _verify_renewal_source(self, source):
        verify_native_regular_files(
            source["boundary"]["rollforward"]["native_origin"], store=self._office_store
        )
        super()._verify_file({"evidence": source["borrower_evidence"]})
        super()._verify_file(source["payout_debit_origin"])

    def renewal_measurement_review(self, actor, *, payout_id):
        with self._transaction() as conn:
            self._authorize_renewal(conn, actor, payout_id)
            source = require_row(
                conn.execute(
                    "SELECT accounting.native_renewal_source(%s) AS source",
                    (payout_id,),
                ).fetchone()
            )["source"]
            self._verify_renewal_source(source)
            super()._verify_file({"evidence": source["borrower_evidence"]})
            debit = require_row(
                conn.execute(
                    "SELECT p.snapshot FROM accounting.loan_payout_accounting_preparations p "
                    "JOIN accounting.loan_payout_accounting_postings a ON a.preparation_id=p.id "
                    "WHERE a.payout_id=%s AND a.stage='debit'",
                    (payout_id,),
                ).fetchone()
            )["snapshot"]
            super()._verify_file(debit)
            retained = conn.execute(
                "SELECT r.id,r.measurement_digest,r.reviewed_measurement->'review'->>'decision' AS decision, r.reviewed_measurement->'evidence' AS evidence "
                "FROM accounting.native_renewal_measurement_reviews r "
                "WHERE r.payout_id=%s AND NOT EXISTS(SELECT 1 FROM accounting.renewal_treatment_decision_voids v WHERE v.decision_id=r.decision_id) "
                "ORDER BY r.reviewed_at DESC,r.id DESC LIMIT 1",
                (payout_id,),
            ).fetchone()
            if retained is not None:
                super()._verify_file(retained)
                retained = {
                    key: retained[key]
                    for key in ("id", "measurement_digest", "decision")
                }
            boundary, execution = source["boundary"], source["execution"]
            result = {
                key: boundary[key]
                for key in (
                    "old_loan_component",
                    "old_accrued_interest",
                    "old_allowance",
                    "old_gross_carrying",
                    "original_daily_eir",
                    "accounting_asset_id",
                )
            }
            result.update(
                {
                    "policy_version": "native_regular_renewal_measurement_v1",
                    "book_id": source["book_id"],
                    "payout_id": payout_id,
                    "execution_id": execution["id"],
                    "old_loan_id": execution["old_loan_id"],
                    "new_loan_id": execution["new_loan_id"],
                    "treasury_account_id": source["payout"]["account_id"],
                    "effective_date": execution["business_date"],
                    "source_digest": source["source_digest"],
                    "fresh_cash": format(
                        Decimal(str(source["payout"]["amount"])), ".2f"
                    ),
                    "revised_pv": source["revised_pv"],
                    "nominal_settlement": format(
                        Decimal(str(execution["old_loan_settlement_amount"])), ".2f"
                    ),
                    "contractual_total": source["contractual_total"],
                    "schedule_id": source["schedule"]["id"],
                    "contract_reference": source["schedule"]["contract_reference"],
                    "evidence_reference": source["registration"]["evidence_reference"],
                    "retained_review": retained,
                }
            )
            result["original_daily_eir"] = str(result["original_daily_eir"])
            for key in (
                "predecessor_credit_impaired",
                "derecognition_blocker",
                "credit_impaired_boundary",
            ):
                if boundary.get(key) is not None:
                    result[key] = boundary[key]
            return json_value(result)

    def retain_renewal_measurement(
        self, actor, *, payout_id, source_digest, request_id, evidence_id, review
    ):
        with self._transaction() as conn:
            self._authorize_renewal(conn, actor, payout_id)
            prior = conn.execute(
                "SELECT id FROM accounting.native_renewal_measurement_reviews WHERE request_id=%s",
                (request_id,),
            ).fetchone()
            if prior is None:
                source = require_row(
                    conn.execute(
                        "SELECT accounting.native_renewal_source(%s) AS source",
                        (payout_id,),
                    ).fetchone()
                )["source"]
                self._verify_renewal_source(source)
                evidence = conn.execute(
                    "SELECT to_jsonb(e) AS evidence FROM treasury.evidence e JOIN treasury.loan_payouts p ON p.account_id=e.account_id "
                    "WHERE p.id=%s AND e.id=%s",
                    (payout_id, evidence_id),
                ).fetchone()
                if evidence is None:
                    raise TreasuryDenied(
                        "Private measurement evidence is unavailable for this payout wallet."
                    )
                super()._verify_file(evidence)
            review_id = require_row(
                conn.execute(
                    "SELECT accounting.record_native_renewal_measurement(%s,%s,%s,%s,%s,%s) AS id",
                    (
                        payout_id,
                        source_digest,
                        request_id,
                        actor.user_id,
                        evidence_id,
                        Jsonb(review),
                    ),
                ).fetchone()
            )["id"]
            retained = require_row(
                conn.execute(
                    "SELECT id,payout_id,book_id,source_digest,request_id,measurement_digest,"
                    "reviewed_measurement->'review'->>'decision' AS decision "
                    "FROM accounting.native_renewal_measurement_reviews WHERE id=%s",
                    (review_id,),
                ).fetchone()
            )
            return json_value(retained)

    def _preparation(self, conn, actor, preparation_id):
        row = conn.execute(
            "SELECT * FROM accounting.loan_payout_accounting_preparations WHERE id=%s",
            (preparation_id,),
        ).fetchone()
        if row is None:
            raise TreasuryDenied("The private payout preparation is unavailable.")
        self._authorize(conn, actor, row["treasury_account_id"])
        if (
            row["snapshot"].get("accounting_policy_version")
            == "native_regular_renewal_completion_v1"
        ):
            self._authorize_renewal(conn, actor, row["payout_id"])
        return row

    def _preparation_payload(self, conn, row):
        status = conn.execute(
            "SELECT * FROM accounting.loan_payout_accounting_posting_status WHERE preparation_id=%s",
            (row["id"],),
        ).fetchone()
        preparation = {
            key: row[key]
            for key in (
                "id",
                "actor_user_id",
                "confirmation_token",
                "source_digest",
                "request_id",
                "book_id",
                "payout_id",
                "stage",
                "event_id",
                "treasury_account_id",
                "loan_id",
                "client_id",
                "disbursement_event_id",
                "created_at",
            )
            if key in row
        }
        preparation["snapshot"] = public_payout_review(
            row["snapshot"], include_digest=False
        )
        posting = (
            None
            if status is None
            else {
                key: status[key]
                for key in (
                    "preparation_id",
                    "journal_entry_id",
                    "book_id",
                    "payout_id",
                    "stage",
                    "event_id",
                    "loan_id",
                    "client_id",
                    "disbursement_event_id",
                    "treasury_account_id",
                    "source_digest",
                    "posting_date",
                    "amount",
                    "fee",
                    "exact_posted",
                    "correction_pending",
                )
                if key in status
            }
        )
        return json_value({"preparation": preparation, "posting": posting})

    def review(self, actor, *, payout_id, stage):
        with self._transaction() as conn:
            self._authorize_stage(conn, actor, payout_id, stage)
            source = require_row(
                conn.execute(
                    "SELECT accounting.loan_payout_coordinates(%s,%s) AS source",
                    (payout_id, stage),
                ).fetchone()
            )["source"]
            self._verify_file(source)
            return json_value(public_payout_review(source))

    def prepare(self, actor, *, payout_id, stage, source_digest, request_id):
        with self._transaction() as conn:
            self._authorize_stage(conn, actor, payout_id, stage)
            prior = conn.execute(
                "SELECT id FROM accounting.loan_payout_accounting_preparations WHERE request_id=%s",
                (request_id,),
            ).fetchone()
            if prior is None:
                source = require_row(
                    conn.execute(
                        "SELECT accounting.loan_payout_coordinates(%s,%s) AS source",
                        (payout_id, stage),
                    ).fetchone()
                )["source"]
                self._verify_file(source)
            preparation_id = require_row(
                conn.execute(
                    "SELECT accounting.prepare_loan_payout_accounting(%s,%s,%s,%s,%s) AS id",
                    (payout_id, stage, source_digest, request_id, actor.user_id),
                ).fetchone()
            )["id"]
            row = conn.execute(
                "SELECT * FROM accounting.loan_payout_accounting_preparations WHERE id=%s",
                (preparation_id,),
            ).fetchone()
            return self._preparation_payload(conn, row)

    def post(self, actor, *, preparation_id, source_digest, confirmation_token):
        with self._transaction() as conn:
            row = self._preparation(conn, actor, preparation_id)
            prior = conn.execute(
                "SELECT id FROM accounting.loan_payout_accounting_postings WHERE payout_id=%s AND stage=%s",
                (row["payout_id"], row["stage"]),
            ).fetchone()
            if prior is None:
                self._verify_file(row["snapshot"])
            entry_id = require_row(
                conn.execute(
                    "SELECT accounting.post_loan_payout_accounting(%s,%s,%s,%s) AS id",
                    (preparation_id, source_digest, confirmation_token, actor.user_id),
                ).fetchone()
            )["id"]
            return dict(
                journal_entry_id=str(entry_id), **self._preparation_payload(conn, row)
            )

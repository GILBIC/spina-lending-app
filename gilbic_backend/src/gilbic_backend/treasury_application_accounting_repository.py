"""Reviewed consumption of retained funds with protected product EIR coordinates."""

from contextlib import contextmanager

from .accounting_query import require_row
from .native_regular_evidence import verify_native_regular_files
from .treasury_authorization import (
    TreasuryConflict,
    TreasuryDenied,
    TreasuryUnavailable,
)
from .treasury_receipt_accounting_repository import (
    TreasuryAccountingAccess,
)
from .treasury_repository import json_value


def public_application_review(source, *, include_digest=True):
    """Project the authorized source; cross-wallet admission evidence stays private."""
    model = source.get("product_model")
    policy = source.get("accounting_policy_version")
    # Every pre0155 snapshot was produced by the unchanged7x7-only0146 adapter.
    # Project its known historical policy without rewriting retained evidence.
    if model is None and policy is None:
        model, policy = "seven_by_seven", "treasury_seven_by_seven_application_v1"
    if (model, policy) not in {
        ("seven_by_seven", "treasury_seven_by_seven_application_v1"),
        ("fixed_daily", "treasury_regular_original_first_cash_v1"),
        ("fixed_daily", "treasury_regular_original_chronological_cash_v1"),
        ("fixed_daily", "treasury_regular_renewal_chronological_cash_v1"),
        ("fixed_daily", "treasury_regular_original_full_payoff_v1"),
    }:
        raise TreasuryUnavailable(
            "The retained application product policy is unavailable."
        )
    keys = (
        "book_id",
        "treasury_account_id",
        "application_id",
        "receipt_id",
        "transaction_id",
        "event_id",
        "loan_id",
        "fiscal_period_id",
        "posting_date",
        "amount",
    )
    result = {key: source[key] for key in keys if key in source}
    result.update(product_model=model, accounting_policy_version=policy)
    if include_digest and "source_digest" in source:
        result["source_digest"] = source["source_digest"]
    result["lines"] = [
        {
            **{
                key: line[key]
                for key in ("line_number", "account_code", "debit", "credit")
                if key in line
            },
            "account_snapshot": {"name": line["account_snapshot"]["name"]},
        }
        for line in source.get("lines", [])
    ]
    if policy == "treasury_regular_original_full_payoff_v1":
        measured = source.get("measurement", {})
        result["payoff"] = {
            key: measured[key]
            for key in (
                "payoff_review_id",
                "payoff_treatment",
                "contract_evidence_reference",
                "payoff_review_rationale",
                "gross_carrying_before",
                "settlement_difference",
            )
            if key in measured
        }
    measured = source.get("measurement", {})
    if measured.get("closed_term_review_id"):
        result["closed_term"] = {
            key: measured[key]
            for key in (
                "closed_term_review_id",
                "closed_term_treatment",
                "closed_term_rationale",
            )
        }
    return result


class PostgresTreasuryApplicationAccountingRepository(TreasuryAccountingAccess):
    """Share receipt authority/file verification; SQL owns the application writer."""

    def _verify_file(self, source):
        super()._verify_file(source)
        verify_native_regular_files(source.get("origin", {}).get("native_origin"))

    @contextmanager
    def _transaction(self):
        try:
            with super()._transaction() as conn:
                yield conn
        except TreasuryUnavailable as error:
            if getattr(error.__cause__, "sqlstate", None) in {"40P01", "40001"}:
                raise TreasuryConflict(
                    "Concurrent accounting changed the review; retry from current evidence."
                ) from error
            raise

    def _application_account(self, conn, application_id):
        row = conn.execute(
            "SELECT account_id FROM treasury.applications WHERE id=%s",
            (application_id,),
        ).fetchone()
        if row is None:
            raise TreasuryDenied("The private application is unavailable.")
        return row["account_id"]

    def _preparation(self, conn, actor, preparation_id):
        row = conn.execute(
            "SELECT * FROM accounting.treasury_application_preparations WHERE id=%s",
            (preparation_id,),
        ).fetchone()
        if row is None:
            raise TreasuryDenied("The private application preparation is unavailable.")
        self._authorize(conn, actor, row["treasury_account_id"])
        return row

    def _preparation_payload(self, conn, row):
        status = conn.execute(
            "SELECT * FROM accounting.treasury_application_posting_status WHERE preparation_id=%s",
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
                "application_id",
                "transaction_id",
                "receipt_id",
                "treasury_account_id",
                "loan_id",
                "created_at",
            )
            if key in row
        }
        preparation["snapshot"] = public_application_review(
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
                    "application_id",
                    "transaction_id",
                    "receipt_id",
                    "treasury_account_id",
                    "loan_id",
                    "source_digest",
                    "exact_posted",
                    "correction_pending",
                )
                if key in status
            }
        )
        return json_value({"preparation": preparation, "posting": posting})

    def review(self, actor, *, application_id):
        with self._transaction() as conn:
            self._authorize(
                conn, actor, self._application_account(conn, application_id)
            )
            source = require_row(
                conn.execute(
                    "SELECT accounting.treasury_application_coordinates(%s) AS source",
                    (application_id,),
                ).fetchone()
            )["source"]
            self._verify_file(source)
            return json_value(public_application_review(source))

    @staticmethod
    def _payoff_payload(source, review_id=None):
        return json_value(
            {
                key: source[key]
                for key in (
                    "ready",
                    "blockers",
                    "source_digest",
                    "contract_evidence_reference",
                    "amount",
                    "gross_carrying_before",
                    "settlement_difference",
                    "application_id",
                    "treasury_account_id",
                    "book_id",
                )
                if key in source
            }
            | {"review_id": str(review_id) if review_id else None}
        )

    def payoff_candidate(self, actor, *, application_id):
        with self._transaction() as conn:
            self._authorize(
                conn, actor, self._application_account(conn, application_id)
            )
            source = require_row(
                conn.execute(
                    "SELECT accounting.regular_payoff_candidate(%s) AS source",
                    (application_id,),
                ).fetchone()
            )["source"]
            if source.get("ready"):
                verify_native_regular_files(
                    source["snapshot"]["origin"]["native_origin"]
                )
            row = conn.execute(
                "SELECT id FROM accounting.regular_payoff_reviews WHERE application_id=%s",
                (application_id,),
            ).fetchone()
            return self._payoff_payload(source, row["id"] if row else None)

    @staticmethod
    def _closed_term_payload(source):
        return json_value(
            {
                key: source[key]
                for key in (
                    "ready",
                    "blockers",
                    "application_id",
                    "treasury_account_id",
                    "book_id",
                    "loan_id",
                    "contractual_due_date",
                    "source_digest",
                    "contract_evidence_reference",
                    "review_id",
                    "treatment",
                )
                if key in source
            }
        )

    def closed_term_candidate(self, actor, *, application_id):
        with self._transaction() as conn:
            self._authorize(
                conn, actor, self._application_account(conn, application_id)
            )
            source = require_row(
                conn.execute(
                    "SELECT accounting.regular_closed_term_candidate(%s) AS source",
                    (application_id,),
                ).fetchone()
            )["source"]
            return self._closed_term_payload(source)

    def review_closed_term(
        self,
        actor,
        *,
        application_id,
        source_digest,
        request_id,
        treatment,
        contract_evidence_reference,
        review_rationale,
    ):
        with self._transaction() as conn:
            self._authorize(
                conn, actor, self._application_account(conn, application_id)
            )
            candidate = require_row(
                conn.execute(
                    "SELECT accounting.regular_closed_term_candidate(%s) AS source",
                    (application_id,),
                ).fetchone()
            )["source"]
            if candidate.get("ready"):
                origin = require_row(
                    conn.execute(
                        "SELECT accounting.regular_closed_term_source(%s) AS source",
                        (candidate["loan_id"],),
                    ).fetchone()
                )["source"]
                verify_native_regular_files(origin)
            conn.execute(
                "SELECT accounting.record_regular_closed_term_review(%s,%s,%s,%s,%s,%s,%s)",
                (
                    application_id,
                    source_digest,
                    request_id,
                    treatment,
                    contract_evidence_reference,
                    review_rationale,
                    actor.user_id,
                ),
            )
            source = require_row(
                conn.execute(
                    "SELECT accounting.regular_closed_term_candidate(%s) AS source",
                    (application_id,),
                ).fetchone()
            )["source"]
            return self._closed_term_payload(source)

    def review_payoff(
        self,
        actor,
        *,
        application_id,
        source_digest,
        request_id,
        treatment,
        contract_evidence_reference,
        review_rationale,
    ):
        with self._transaction() as conn:
            self._authorize(
                conn, actor, self._application_account(conn, application_id)
            )
            source = require_row(
                conn.execute(
                    "SELECT accounting.regular_payoff_candidate(%s) AS source",
                    (application_id,),
                ).fetchone()
            )["source"]
            if source.get("ready"):
                verify_native_regular_files(
                    source["snapshot"]["origin"]["native_origin"]
                )
            review_id = require_row(
                conn.execute(
                    "SELECT accounting.record_regular_payoff_review(%s,%s,%s,%s,%s,%s,%s) AS id",
                    (
                        application_id,
                        source_digest,
                        request_id,
                        treatment,
                        contract_evidence_reference,
                        review_rationale,
                        actor.user_id,
                    ),
                ).fetchone()
            )["id"]
            return self._payoff_payload(source, review_id)

    def prepare(self, actor, *, application_id, source_digest, request_id):
        with self._transaction() as conn:
            self._authorize(
                conn, actor, self._application_account(conn, application_id)
            )
            prior = conn.execute(
                "SELECT id FROM accounting.treasury_application_preparations WHERE request_id=%s",
                (request_id,),
            ).fetchone()
            if prior is None:
                source = require_row(
                    conn.execute(
                        "SELECT accounting.treasury_application_coordinates(%s) AS source",
                        (application_id,),
                    ).fetchone()
                )["source"]
                self._verify_file(source)
            preparation_id = require_row(
                conn.execute(
                    "SELECT accounting.prepare_treasury_application(%s,%s,%s,%s) AS id",
                    (application_id, source_digest, request_id, actor.user_id),
                ).fetchone()
            )["id"]
            row = conn.execute(
                "SELECT * FROM accounting.treasury_application_preparations WHERE id=%s",
                (preparation_id,),
            ).fetchone()
            return self._preparation_payload(conn, require_row(row))

    def post(self, actor, *, preparation_id, source_digest, confirmation_token):
        with self._transaction() as conn:
            row = self._preparation(conn, actor, preparation_id)
            prior = conn.execute(
                "SELECT id FROM accounting.treasury_application_postings WHERE application_id=%s",
                (row["application_id"],),
            ).fetchone()
            if prior is None:
                self._verify_file(row["snapshot"])
            entry_id = require_row(
                conn.execute(
                    "SELECT accounting.post_treasury_application(%s,%s,%s,%s) AS id",
                    (preparation_id, source_digest, confirmation_token, actor.user_id),
                ).fetchone()
            )["id"]
            return dict(
                journal_entry_id=str(entry_id), **self._preparation_payload(conn, row)
            )

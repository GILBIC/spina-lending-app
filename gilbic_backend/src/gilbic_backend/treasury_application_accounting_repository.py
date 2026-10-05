"""Reviewed consumption of retained funds with protected product EIR coordinates."""

from contextlib import contextmanager

from .treasury_authorization import (
    TreasuryConflict,
    TreasuryDenied,
    TreasuryUnavailable,
)
from .treasury_receipt_accounting_repository import (
    PostgresTreasuryReceiptAccountingRepository,
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
    return result


class PostgresTreasuryApplicationAccountingRepository(
    PostgresTreasuryReceiptAccountingRepository
):
    """Share receipt authority/file verification; SQL owns the application writer."""

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
            source = conn.execute(
                "SELECT accounting.treasury_application_coordinates(%s) AS source",
                (application_id,),
            ).fetchone()["source"]
            self._verify_file(source)
            return json_value(public_application_review(source))

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
                source = conn.execute(
                    "SELECT accounting.treasury_application_coordinates(%s) AS source",
                    (application_id,),
                ).fetchone()["source"]
                self._verify_file(source)
            preparation_id = conn.execute(
                "SELECT accounting.prepare_treasury_application(%s,%s,%s,%s) AS id",
                (application_id, source_digest, request_id, actor.user_id),
            ).fetchone()["id"]
            row = conn.execute(
                "SELECT * FROM accounting.treasury_application_preparations WHERE id=%s",
                (preparation_id,),
            ).fetchone()
            return self._preparation_payload(conn, row)

    def post(self, actor, *, preparation_id, source_digest, confirmation_token):
        with self._transaction() as conn:
            row = self._preparation(conn, actor, preparation_id)
            prior = conn.execute(
                "SELECT id FROM accounting.treasury_application_postings WHERE application_id=%s",
                (row["application_id"],),
            ).fetchone()
            if prior is None:
                self._verify_file(row["snapshot"])
            entry_id = conn.execute(
                "SELECT accounting.post_treasury_application(%s,%s,%s,%s) AS id",
                (preparation_id, source_digest, confirmation_token, actor.user_id),
            ).fetchone()["id"]
            return dict(
                journal_entry_id=str(entry_id), **self._preparation_payload(conn, row)
            )

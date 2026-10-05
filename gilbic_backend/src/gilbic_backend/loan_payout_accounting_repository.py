"""Reviewed actual payout legs; retained admission evidence stays private."""

from contextlib import contextmanager
from uuid import UUID

from .office_review_evidence_storage import PrivateEvidenceStore
from .treasury_authorization import (
    TreasuryConflict,
    TreasuryDenied,
    TreasuryUnavailable,
    require_actor,
)
from .treasury_receipt_accounting_repository import (
    PostgresTreasuryReceiptAccountingRepository,
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


class PostgresLoanPayoutAccountingRepository(
    PostgresTreasuryReceiptAccountingRepository
):
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

    def _preparation(self, conn, actor, preparation_id):
        row = conn.execute(
            "SELECT * FROM accounting.loan_payout_accounting_preparations WHERE id=%s",
            (preparation_id,),
        ).fetchone()
        if row is None:
            raise TreasuryDenied("The private payout preparation is unavailable.")
        self._authorize(conn, actor, row["treasury_account_id"])
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
            self._authorize_payout(conn, actor, payout_id)
            source = conn.execute(
                "SELECT accounting.loan_payout_coordinates(%s,%s) AS source",
                (payout_id, stage),
            ).fetchone()["source"]
            self._verify_file(source)
            return json_value(public_payout_review(source))

    def prepare(self, actor, *, payout_id, stage, source_digest, request_id):
        with self._transaction() as conn:
            self._authorize_payout(conn, actor, payout_id)
            prior = conn.execute(
                "SELECT id FROM accounting.loan_payout_accounting_preparations WHERE request_id=%s",
                (request_id,),
            ).fetchone()
            if prior is None:
                source = conn.execute(
                    "SELECT accounting.loan_payout_coordinates(%s,%s) AS source",
                    (payout_id, stage),
                ).fetchone()["source"]
                self._verify_file(source)
            preparation_id = conn.execute(
                "SELECT accounting.prepare_loan_payout_accounting(%s,%s,%s,%s,%s) AS id",
                (payout_id, stage, source_digest, request_id, actor.user_id),
            ).fetchone()["id"]
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
            entry_id = conn.execute(
                "SELECT accounting.post_loan_payout_accounting(%s,%s,%s,%s) AS id",
                (preparation_id, source_digest, confirmation_token, actor.user_id),
            ).fetchone()["id"]
            return dict(
                journal_entry_id=str(entry_id), **self._preparation_payload(conn, row)
            )

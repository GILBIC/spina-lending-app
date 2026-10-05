"""Reviewed actual transfer legs; retained admission evidence stays private."""

from contextlib import contextmanager

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


def public_transfer_review(source, *, include_digest=True):
    keys = (
        "book_id",
        "transfer_id",
        "leg",
        "event_id",
        "source_account_id",
        "destination_account_id",
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


class PostgresTreasuryTransferAccountingRepository(
    PostgresTreasuryReceiptAccountingRepository
):
    @contextmanager
    def _transaction(self):
        try:
            with super()._transaction() as conn:
                yield conn
        except TreasuryUnavailable as error:
            if getattr(error.__cause__, "sqlstate", None) in {"40P01", "40001"}:
                raise TreasuryConflict(
                    "Concurrent transfer accounting changed the review; retry from current evidence."
                ) from error
            raise

    def _authorize_transfer(self, conn, actor, transfer_id):
        require_actor(conn, actor)
        conn.execute(
            "SELECT accounting.require_treasury_transfer_actor(%s,%s)",
            (actor.user_id, transfer_id),
        )

    def _preparation(self, conn, actor, preparation_id):
        row = conn.execute(
            "SELECT * FROM accounting.treasury_transfer_preparations WHERE id=%s",
            (preparation_id,),
        ).fetchone()
        if row is None:
            raise TreasuryDenied("The private transfer preparation is unavailable.")
        for account in sorted(
            (row["source_account_id"], row["destination_account_id"]), key=str
        ):
            self._authorize(conn, actor, account)
        return row

    def _preparation_payload(self, conn, row):
        status = conn.execute(
            "SELECT * FROM accounting.treasury_transfer_posting_status WHERE preparation_id=%s",
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
                "transfer_id",
                "leg",
                "event_id",
                "source_account_id",
                "destination_account_id",
                "source_mapping_id",
                "destination_mapping_id",
                "created_at",
            )
            if key in row
        }
        preparation["snapshot"] = public_transfer_review(
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
                    "transfer_id",
                    "leg",
                    "event_id",
                    "source_account_id",
                    "destination_account_id",
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

    def review(
        self, actor, *, transfer_id, leg, source_mapping_id, destination_mapping_id
    ):
        with self._transaction() as conn:
            self._authorize_transfer(conn, actor, transfer_id)
            source = conn.execute(
                "SELECT accounting.treasury_transfer_coordinates(%s,%s,%s,%s) AS source",
                (transfer_id, leg, source_mapping_id, destination_mapping_id),
            ).fetchone()["source"]
            self._verify_file(source)
            return json_value(public_transfer_review(source))

    def prepare(
        self,
        actor,
        *,
        transfer_id,
        leg,
        source_mapping_id,
        destination_mapping_id,
        source_digest,
        request_id,
    ):
        with self._transaction() as conn:
            self._authorize_transfer(conn, actor, transfer_id)
            prior = conn.execute(
                "SELECT id FROM accounting.treasury_transfer_preparations WHERE request_id=%s",
                (request_id,),
            ).fetchone()
            if prior is None:
                source = conn.execute(
                    "SELECT accounting.treasury_transfer_coordinates(%s,%s,%s,%s) AS source",
                    (transfer_id, leg, source_mapping_id, destination_mapping_id),
                ).fetchone()["source"]
                self._verify_file(source)
            preparation_id = conn.execute(
                "SELECT accounting.prepare_treasury_transfer(%s,%s,%s,%s,%s,%s,%s) AS id",
                (
                    transfer_id,
                    leg,
                    source_mapping_id,
                    destination_mapping_id,
                    source_digest,
                    request_id,
                    actor.user_id,
                ),
            ).fetchone()["id"]
            row = conn.execute(
                "SELECT * FROM accounting.treasury_transfer_preparations WHERE id=%s",
                (preparation_id,),
            ).fetchone()
            return self._preparation_payload(conn, row)

    def post(self, actor, *, preparation_id, source_digest, confirmation_token):
        with self._transaction() as conn:
            row = self._preparation(conn, actor, preparation_id)
            prior = conn.execute(
                "SELECT id FROM accounting.treasury_transfer_postings WHERE transfer_id=%s AND leg=%s",
                (row["transfer_id"], row["leg"]),
            ).fetchone()
            if prior is None:
                self._verify_file(row["snapshot"])
            entry_id = conn.execute(
                "SELECT accounting.post_treasury_transfer(%s,%s,%s,%s) AS id",
                (preparation_id, source_digest, confirmation_token, actor.user_id),
            ).fetchone()["id"]
            return dict(
                journal_entry_id=str(entry_id), **self._preparation_payload(conn, row)
            )

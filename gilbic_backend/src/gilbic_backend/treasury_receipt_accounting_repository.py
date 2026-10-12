"""Explicit reviewed recognition of original verified Treasury borrower cash.

The caller supplies identities and digests. SQL derives every journal coordinate,
rechecks live authority and source state, and posts with its immutable audit.
"""

import json
from contextlib import contextmanager
from decimal import Decimal
from functools import partial
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import set_json_loads

from .accounting_query import require_row
from .database import connect_database
from .office_review_evidence_storage import EvidenceFileError, PrivateEvidenceStore
from .treasury_authorization import (
    TreasuryConflict,
    TreasuryDenied,
    TreasuryUnavailable,
    require_actor,
)
from .treasury_repository import json_value


class TreasuryAccountingAccess:
    def __init__(self, *, connection_factory=None, evidence_store=None):
        self._connect = connection_factory or connect_database
        self._store = evidence_store

    @contextmanager
    def _transaction(self):
        try:
            with self._connect() as conn:
                conn.row_factory = dict_row
                set_json_loads(partial(json.loads, parse_float=Decimal), context=conn)
                yield conn
        except psycopg.Error as error:
            if error.sqlstate == "42501":
                raise TreasuryDenied(
                    "Current Management and private Treasury account permission are required."
                ) from error
            if error.sqlstate in {"22023", "55000", "23505", "23514", "P0001"}:
                raise TreasuryConflict(
                    error.diag.message_primary
                    or "Receipt accounting review was rejected."
                ) from error
            raise TreasuryUnavailable("Receipt accounting is unavailable.") from error
        except EvidenceFileError as error:
            raise TreasuryUnavailable(
                "Retained private receipt evidence is unavailable or changed."
            ) from error

    def _authorize(self, conn, actor, account_id, permission="treasury.view"):
        require_actor(conn, actor)
        conn.execute(
            "SELECT accounting.require_treasury_gl_actor(%s,%s,%s)",
            (actor.user_id, account_id, permission),
        )

    def _verify_file(self, source):
        evidence = source["evidence"]
        if self._store is None:
            self._store = PrivateEvidenceStore()
        self._store.read(
            UUID(str(evidence["id"])), evidence["sha256"], evidence["byte_count"]
        )

    def _receipt_account(self, conn, receipt_id):
        row = conn.execute(
            "SELECT account_id FROM treasury.receipts WHERE id=%s", (receipt_id,)
        ).fetchone()
        if row is None:
            raise TreasuryDenied("The private receipt is unavailable.")
        return row["account_id"]

    def _preparation(self, conn, actor, preparation_id):
        raise NotImplementedError

    def _preparation_payload(self, conn, row):
        raise NotImplementedError

    def read_preparation(self, actor, *, preparation_id):
        with self._transaction() as conn:
            return self._preparation_payload(
                conn, self._preparation(conn, actor, preparation_id)
            )


class PostgresTreasuryReceiptAccountingRepository(TreasuryAccountingAccess):
    def _preparation(self, conn, actor, preparation_id):
        row = conn.execute(
            "SELECT * FROM accounting.treasury_receipt_preparations WHERE id=%s",
            (preparation_id,),
        ).fetchone()
        if row is None:
            raise TreasuryDenied("The private receipt preparation is unavailable.")
        self._authorize(conn, actor, row["treasury_account_id"])
        return row

    def _preparation_payload(self, conn, row):
        status = conn.execute(
            "SELECT * FROM accounting.treasury_receipt_posting_status WHERE preparation_id=%s",
            (row["id"],),
        ).fetchone()
        return json_value({"preparation": row, "posting": status})

    def read_mapping(self, actor, *, account_id):
        with self._transaction() as conn:
            self._authorize(conn, actor, account_id)
            book = require_row(
                conn.execute(
                    "SELECT accounting.require_book_treasury_account(%s) AS id",
                    (account_id,),
                ).fetchone()
            )["id"]
            mapping = conn.execute(
                "SELECT * FROM accounting.treasury_cash_mappings WHERE treasury_account_id=%s ORDER BY version DESC LIMIT 1",
                (account_id,),
            ).fetchone()
            return json_value(
                {"book_id": book, "treasury_account_id": account_id, "mapping": mapping}
            )

    def configure_mapping(
        self,
        actor,
        *,
        account_id,
        cash_code,
        expected_version,
        request_id,
        evidence_reference,
        evidence_digest,
    ):
        with self._transaction() as conn:
            self._authorize(conn, actor, account_id, "treasury.account.manage")
            mapping_id = require_row(
                conn.execute(
                    "SELECT accounting.configure_treasury_cash_mapping(%s,%s,%s,%s,%s,%s,%s) AS id",
                    (
                        account_id,
                        cash_code,
                        expected_version,
                        request_id,
                        evidence_reference,
                        evidence_digest,
                        actor.user_id,
                    ),
                ).fetchone()
            )["id"]
            row = conn.execute(
                "SELECT * FROM accounting.treasury_cash_mappings WHERE id=%s",
                (mapping_id,),
            ).fetchone()
            return json_value({"mapping": row})

    def review(self, actor, *, receipt_id, mapping_id):
        with self._transaction() as conn:
            self._authorize(conn, actor, self._receipt_account(conn, receipt_id))
            source = require_row(
                conn.execute(
                    "SELECT accounting.treasury_receipt_coordinates(%s,%s) AS source",
                    (receipt_id, mapping_id),
                ).fetchone()
            )["source"]
            self._verify_file(source)
            return json_value(source)

    def prepare(self, actor, *, receipt_id, mapping_id, source_digest, request_id):
        with self._transaction() as conn:
            self._authorize(conn, actor, self._receipt_account(conn, receipt_id))
            prior = conn.execute(
                "SELECT * FROM accounting.treasury_receipt_preparations WHERE request_id=%s",
                (request_id,),
            ).fetchone()
            # A retry returns the immutable prior review; SQL checks exact inputs.
            # A new review must verify retained bytes before any insertion.
            if prior is None:
                source = require_row(
                    conn.execute(
                        "SELECT accounting.treasury_receipt_coordinates(%s,%s) AS source",
                        (receipt_id, mapping_id),
                    ).fetchone()
                )["source"]
                self._verify_file(source)
            preparation_id = require_row(
                conn.execute(
                    "SELECT accounting.prepare_treasury_receipt(%s,%s,%s,%s,%s) AS id",
                    (receipt_id, mapping_id, source_digest, request_id, actor.user_id),
                ).fetchone()
            )["id"]
            row = conn.execute(
                "SELECT * FROM accounting.treasury_receipt_preparations WHERE id=%s",
                (preparation_id,),
            ).fetchone()
            return self._preparation_payload(conn, row)

    def post(self, actor, *, preparation_id, source_digest, confirmation_token):
        with self._transaction() as conn:
            row = self._preparation(conn, actor, preparation_id)
            prior = conn.execute(
                "SELECT id FROM accounting.treasury_receipt_postings WHERE event_id=%s",
                (row["event_id"],),
            ).fetchone()
            if prior is None:
                self._verify_file(row["snapshot"])
            entry_id = require_row(
                conn.execute(
                    "SELECT accounting.post_treasury_receipt(%s,%s,%s,%s) AS id",
                    (preparation_id, source_digest, confirmation_token, actor.user_id),
                ).fetchone()
            )["id"]
            return dict(
                journal_entry_id=str(entry_id), **self._preparation_payload(conn, row)
            )

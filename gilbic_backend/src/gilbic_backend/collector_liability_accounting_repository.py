"""Explicit Collector journals derived from private, retained source proof."""

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


class PostgresCollectorLiabilityAccountingRepository:
    def __init__(self, *, connection_factory=None, evidence_store=None):
        self._connect = connection_factory or connect_database
        self._store = evidence_store

    def control_schedule(self, actor, *, as_of=None, limit=100, offset=0):
        from .collector_control_schedule import load_collector_control_schedule

        with self._transaction() as conn:
            return load_collector_control_schedule(
                conn, actor, as_of=as_of, limit=limit, offset=offset
            )

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
                    "Current Management and all affected private Treasury account permissions are required."
                ) from error
            if error.sqlstate in {
                "22023",
                "55000",
                "23505",
                "23514",
                "P0001",
                "40P01",
                "40001",
            }:
                raise TreasuryConflict(
                    error.diag.message_primary
                    or "Collector accounting review changed; review current evidence."
                ) from error
            raise TreasuryUnavailable("Collector accounting is unavailable.") from error
        except EvidenceFileError as error:
            raise TreasuryUnavailable(
                "Retained private Collector evidence is unavailable or changed."
            ) from error

    def _authorize_source(self, conn, actor, source_kind, source_id):
        require_actor(conn, actor)
        conn.execute(
            "SELECT accounting.require_collector_liability_actor(%s,%s,%s)",
            (actor.user_id, source_kind, source_id),
        )

    def _verify_files(self, source):
        if self._store is None:
            self._store = PrivateEvidenceStore()
        for evidence in source["evidence"]:
            self._store.read(
                UUID(str(evidence["id"])), evidence["sha256"], evidence["byte_count"]
            )

    def _public_review(self, conn, source, *, include_digest=True):
        keys = (
            "book_id",
            "source_kind",
            "source_id",
            "treasury_account_id",
            "fiscal_period_id",
            "posting_date",
            "amount",
            "fee",
        )
        result = {key: source[key] for key in keys if key in source}
        if include_digest and "source_digest" in source:
            result["source_digest"] = source["source_digest"]
        names = {
            str(row["id"]): row["name"]
            for row in conn.execute(
                "SELECT id,name FROM accounting.accounts WHERE id=ANY(%s::uuid[])",
                ([str(line["account_id"]) for line in source["lines"]],),
            ).fetchall()
        }
        result["lines"] = [
            {
                **{
                    key: line[key]
                    for key in ("line_number", "account_code", "debit", "credit")
                },
                "account_snapshot": {
                    "name": names.get(str(line["account_id"]), line["account_code"])
                },
            }
            for line in source["lines"]
        ]
        facts = source.get("source_facts", {})
        if facts.get("application"):
            settlement = facts["settlement"]["payload"]
            count = facts["count"]["payload"]
            result["custody_split"] = {
                "gross_obligation": settlement["gross_obligation"],
                "authorized_credit_amount": settlement["authorized_credit_amount"],
                "physical_amount": settlement["physical_amount"],
                "physical_cash_required": count["physical_cash_required"],
                "excess_amount": count["difference"],
            }
        return result

    def _preparation(self, conn, actor, preparation_id):
        row = conn.execute(
            "SELECT * FROM accounting.collector_liability_preparations WHERE id=%s",
            (preparation_id,),
        ).fetchone()
        if row is None:
            raise TreasuryDenied("The private Collector preparation is unavailable.")
        self._authorize_source(conn, actor, row["source_kind"], row["source_id"])
        # Retained files may refer to a prior wallet even if an operational
        # correction changed the current source. Both scopes remain private.
        for account in row["snapshot"].get("account_ids", []):
            for permission in ("treasury.view", "treasury.collector_surplus.view"):
                conn.execute(
                    "SELECT accounting.require_treasury_gl_actor(%s,%s,%s)",
                    (actor.user_id, account, permission),
                )
        return row

    def _preparation_payload(self, conn, row):
        status = conn.execute(
            "SELECT * FROM accounting.collector_liability_posting_status WHERE preparation_id=%s",
            (row["id"],),
        ).fetchone()
        prepared = {
            key: row[key]
            for key in (
                "id",
                "request_id",
                "book_id",
                "source_kind",
                "source_id",
                "source_digest",
                "confirmation_token",
                "actor_user_id",
                "created_at",
            )
            if key in row
        }
        prepared["snapshot"] = self._public_review(
            conn, row["snapshot"], include_digest=False
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
                    "source_kind",
                    "source_id",
                    "posting_date",
                    "amount",
                    "exact_posted",
                    "correction_pending",
                )
                if key in status
            }
        )
        return json_value({"preparation": prepared, "posting": posting})

    def review(self, actor, *, source_kind, source_id):
        with self._transaction() as conn:
            self._authorize_source(conn, actor, source_kind, source_id)
            source = require_row(
                conn.execute(
                    "SELECT accounting.collector_liability_coordinates(%s,%s) AS source",
                    (source_kind, source_id),
                ).fetchone()
            )["source"]
            self._verify_files(source)
            return json_value(self._public_review(conn, source))

    def prepare(self, actor, *, source_kind, source_id, source_digest, request_id):
        with self._transaction() as conn:
            self._authorize_source(conn, actor, source_kind, source_id)
            prior = conn.execute(
                "SELECT id FROM accounting.collector_liability_preparations WHERE request_id=%s",
                (request_id,),
            ).fetchone()
            if prior is None:
                source = require_row(
                    conn.execute(
                        "SELECT accounting.collector_liability_coordinates(%s,%s) AS source",
                        (source_kind, source_id),
                    ).fetchone()
                )["source"]
                self._verify_files(source)
            identity = require_row(
                conn.execute(
                    "SELECT accounting.prepare_collector_liability(%s,%s,%s,%s,%s) AS id",
                    (source_kind, source_id, source_digest, request_id, actor.user_id),
                ).fetchone()
            )["id"]
            row = conn.execute(
                "SELECT * FROM accounting.collector_liability_preparations WHERE id=%s",
                (identity,),
            ).fetchone()
            return self._preparation_payload(conn, row)

    def read_preparation(self, actor, *, preparation_id):
        with self._transaction() as conn:
            return self._preparation_payload(
                conn, self._preparation(conn, actor, preparation_id)
            )

    def post(self, actor, *, preparation_id, source_digest, confirmation_token):
        with self._transaction() as conn:
            row = self._preparation(conn, actor, preparation_id)
            prior = conn.execute(
                "SELECT id FROM accounting.collector_liability_postings WHERE source_kind=%s AND source_id=%s",
                (row["source_kind"], row["source_id"]),
            ).fetchone()
            if prior is None:
                self._verify_files(row["snapshot"])
            journal = require_row(
                conn.execute(
                    "SELECT accounting.post_collector_liability(%s,%s,%s,%s) AS id",
                    (preparation_id, source_digest, confirmation_token, actor.user_id),
                ).fetchone()
            )["id"]
            return dict(
                journal_entry_id=str(journal), **self._preparation_payload(conn, row)
            )

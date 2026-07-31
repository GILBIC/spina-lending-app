from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .contracts import (
    ActorContext,
    CollectionCommand,
    CollectionOutcome,
    CollectionStatus,
    PostedCollection,
)
from .service import CollectionConflict, CollectionRejected


class CollectionPostingBridge(Protocol):
    """Calls the existing SPINA business rules using the supplied transaction."""

    def post_collection(
        self,
        connection: Connection[Any],
        actor: ActorContext,
        command: CollectionCommand,
    ) -> PostedCollection: ...


ConnectionFactory = Callable[[], Connection[Any]]


class PostgresCollectionExecutor:
    def __init__(
        self,
        *,
        connection_factory: ConnectionFactory,
        posting_bridge: CollectionPostingBridge,
    ) -> None:
        self._connection_factory = connection_factory
        self._posting_bridge = posting_bridge

    def execute(
        self,
        *,
        actor: ActorContext,
        command: CollectionCommand,
        canonical_payload: dict[str, Any],
        request_hash: str,
    ) -> CollectionOutcome:
        try:
            with self._connection_factory() as connection:
                with connection.transaction():
                    with connection.cursor(row_factory=dict_row) as cursor:
                        self._lock_key(cursor, command)
                        existing = self._find_existing(cursor, command)
                        if existing is not None:
                            return self._replay_or_conflict(
                                existing=existing,
                                actor=actor,
                                command=command,
                                request_hash=request_hash,
                            )

                        posted = self._posting_bridge.post_collection(
                            connection,
                            actor,
                            command,
                        )
                        self._store_result(
                            cursor=cursor,
                            actor=actor,
                            command=command,
                            canonical_payload=canonical_payload,
                            request_hash=request_hash,
                            posted=posted,
                        )
                        return CollectionOutcome(
                            status=CollectionStatus.ACCEPTED,
                            idempotency_key=command.idempotency_key,
                            message=posted.message,
                            posted=posted,
                        )
        except CollectionConflict as exc:
            return CollectionOutcome(
                status=CollectionStatus.CONFLICT,
                idempotency_key=command.idempotency_key,
                message=exc.message,
                code=exc.code,
            )
        except CollectionRejected as exc:
            return CollectionOutcome(
                status=CollectionStatus.REJECTED,
                idempotency_key=command.idempotency_key,
                message=exc.message,
                code=exc.code,
            )

    @staticmethod
    def _lock_key(cursor: Any, command: CollectionCommand) -> None:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (str(command.idempotency_key),),
        )

    @staticmethod
    def _find_existing(
        cursor: Any,
        command: CollectionCommand,
    ) -> dict[str, Any] | None:
        cursor.execute(
            """
            SELECT
                collector_account_id,
                registered_device_id,
                canonical_request_hash,
                server_transaction_id,
                receipt_number,
                official_balance,
                accepted_at,
                route_revision
            FROM mobile.gilbic_collection_idempotency
            WHERE idempotency_key = %s
            FOR UPDATE
            """,
            (command.idempotency_key,),
        )
        return cursor.fetchone()

    @staticmethod
    def _replay_or_conflict(
        *,
        existing: dict[str, Any],
        actor: ActorContext,
        command: CollectionCommand,
        request_hash: str,
    ) -> CollectionOutcome:
        same_owner = (
            str(existing["collector_account_id"]) == actor.account_id
            and str(existing["registered_device_id"]) == actor.device_id
        )
        if not same_owner or existing["canonical_request_hash"] != request_hash:
            return CollectionOutcome(
                status=CollectionStatus.CONFLICT,
                idempotency_key=command.idempotency_key,
                message="This transaction key was already used for different collection data.",
                code="idempotency_mismatch",
            )

        posted = PostedCollection(
            server_transaction_id=str(existing["server_transaction_id"]),
            receipt_number=str(existing["receipt_number"]),
            official_balance=existing["official_balance"],
            accepted_at=existing["accepted_at"],
            route_revision=existing["route_revision"],
            message="Previously accepted",
        )
        return CollectionOutcome(
            status=CollectionStatus.DUPLICATE,
            idempotency_key=command.idempotency_key,
            message="Previously accepted",
            posted=posted,
        )

    @staticmethod
    def _store_result(
        *,
        cursor: Any,
        actor: ActorContext,
        command: CollectionCommand,
        canonical_payload: dict[str, Any],
        request_hash: str,
        posted: PostedCollection,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO mobile.gilbic_collection_idempotency (
                idempotency_key,
                collector_account_id,
                registered_device_id,
                canonical_request_hash,
                request_payload,
                result_status,
                server_transaction_id,
                receipt_number,
                official_balance,
                accepted_at,
                route_revision,
                result_payload
            ) VALUES (
                %s, %s, %s, %s, %s, 'accepted',
                %s, %s, %s, %s, %s, %s
            )
            """,
            (
                command.idempotency_key,
                actor.account_id,
                actor.device_id,
                request_hash,
                Jsonb(canonical_payload),
                posted.server_transaction_id,
                posted.receipt_number,
                posted.official_balance,
                posted.accepted_at,
                posted.route_revision,
                Jsonb(
                    posted.response_payload(
                        idempotency_key=command.idempotency_key,
                        duplicate=False,
                    )
                ),
            ),
        )

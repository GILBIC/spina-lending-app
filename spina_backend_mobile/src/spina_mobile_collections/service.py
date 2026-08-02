from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from .contracts import (
    ActorContext,
    CollectionCommand,
    CollectionEntryType,
    CollectionOutcome,
)

CONTRACT_VERSION = "gilbic-collection-v1"


class CollectionProtocolError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class CollectionConflict(Exception):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class CollectionRejected(Exception):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass(frozen=True, slots=True)
class SubmissionHeaders:
    idempotency_key: UUID
    client_transaction_id: UUID
    device_id: str
    contract_version: str


class CollectionTransactionExecutor(Protocol):
    def execute(
        self,
        *,
        actor: ActorContext,
        command: CollectionCommand,
        canonical_payload: dict[str, Any],
        request_hash: str,
    ) -> CollectionOutcome: ...


class CollectionSubmissionService:
    def __init__(self, executor: CollectionTransactionExecutor) -> None:
        self._executor = executor

    def submit(
        self,
        *,
        actor: ActorContext,
        headers: SubmissionHeaders,
        command: CollectionCommand,
    ) -> CollectionOutcome:
        self._validate(actor=actor, headers=headers, command=command)
        payload = command.canonical_payload()
        return self._executor.execute(
            actor=actor,
            command=command,
            canonical_payload=payload,
            request_hash=canonical_request_hash(payload),
        )

    def _validate(
        self,
        *,
        actor: ActorContext,
        headers: SubmissionHeaders,
        command: CollectionCommand,
    ) -> None:
        if headers.contract_version != CONTRACT_VERSION:
            raise CollectionProtocolError(
                "The Gilbic collection contract version is not supported.",
                code="unsupported_contract_version",
                status_code=400,
            )
        if not actor.can_create_collection():
            raise CollectionProtocolError(
                "This account cannot create collections.",
                code="permission_denied",
                status_code=403,
            )
        if not actor.account_id.strip():
            raise CollectionProtocolError(
                "The authenticated account is invalid.",
                code="invalid_session",
                status_code=401,
            )
        if (
            headers.idempotency_key != headers.client_transaction_id
            or headers.idempotency_key != command.idempotency_key
        ):
            raise CollectionProtocolError(
                "Collection transaction identifiers must match.",
                code="idempotency_key_mismatch",
                status_code=400,
            )
        if (
            not headers.device_id.strip()
            or headers.device_id != command.device_id
            or headers.device_id != actor.device_id
        ):
            raise CollectionProtocolError(
                "The registered device does not match this collection.",
                code="device_not_registered",
                status_code=403,
            )
        if command.device_sequence < 1:
            raise CollectionProtocolError(
                "The device sequence must be greater than zero.",
                code="invalid_device_sequence",
                status_code=422,
            )
        if command.recorded_at.tzinfo is None:
            raise CollectionProtocolError(
                "The recorded time must include a timezone.",
                code="invalid_recorded_at",
                status_code=422,
            )
        if not all(
            value.strip()
            for value in (
                command.route_entry_id,
                command.client_id,
                command.loan_id,
            )
        ):
            raise CollectionProtocolError(
                "The route entry, client, and loan are required.",
                code="invalid_collection_reference",
                status_code=422,
            )
        self._validate_entry(command)

    def _validate_entry(self, command: CollectionCommand) -> None:
        positive_amount = command.amount is not None and command.amount > Decimal("0")
        has_advance_dates = (
            command.advance_from is not None or command.advance_until is not None
        )
        selected_dates = tuple(sorted(command.covered_dates))
        if len(selected_dates) != len(set(selected_dates)):
            raise CollectionProtocolError(
                "Covered dates must not contain duplicates.",
                code="duplicate_covered_date",
                status_code=422,
            )

        if command.entry_type is CollectionEntryType.PAYMENT:
            if not positive_amount:
                raise CollectionProtocolError(
                    "A payment amount greater than zero is required.",
                    code="invalid_amount",
                    status_code=422,
                )
            if has_advance_dates:
                raise CollectionProtocolError(
                    "A normal payment cannot contain coverage bounds.",
                    code="invalid_advance_range",
                    status_code=422,
                )
            if selected_dates and selected_dates != (command.collection_date,):
                raise CollectionProtocolError(
                    "A normal payment may cover only the collection date.",
                    code="invalid_covered_dates",
                    status_code=422,
                )
            return

        if command.entry_type is CollectionEntryType.ADVANCE:
            if not positive_amount:
                raise CollectionProtocolError(
                    "A covered-date payment amount greater than zero is required.",
                    code="invalid_amount",
                    status_code=422,
                )
            if command.advance_from is None or command.advance_until is None:
                raise CollectionProtocolError(
                    "The first and last selected covered dates are required.",
                    code="invalid_advance_range",
                    status_code=422,
                )
            if command.advance_until < command.advance_from:
                raise CollectionProtocolError(
                    "The last covered date cannot be before the first covered date.",
                    code="invalid_advance_range",
                    status_code=422,
                )
            if selected_dates:
                if selected_dates[0] != command.advance_from:
                    raise CollectionProtocolError(
                        "The first coverage bound must match the earliest selected date.",
                        code="covered_date_bounds_mismatch",
                        status_code=422,
                    )
                if selected_dates[-1] != command.advance_until:
                    raise CollectionProtocolError(
                        "The last coverage bound must match the latest selected date.",
                        code="covered_date_bounds_mismatch",
                        status_code=422,
                    )
            return

        if (
            command.amount not in {None, Decimal("0")}
            or has_advance_dates
            or selected_dates
        ):
            raise CollectionProtocolError(
                "An unable-to-pay entry cannot contain an amount or covered dates.",
                code="invalid_pass",
                status_code=422,
            )


def canonical_request_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


class RemittanceAccountingEvidenceError(RuntimeError):
    code = "remittance_accounting_evidence_error"


class RemittanceAccountingEvidenceNotFound(RemittanceAccountingEvidenceError):
    code = "remittance_accounting_evidence_not_found"


class RemittanceAccountingEvidenceConflict(RemittanceAccountingEvidenceError):
    code = "remittance_accounting_evidence_conflict"


class RemittanceAccountingEvidenceInvalid(RemittanceAccountingEvidenceError):
    code = "remittance_accounting_evidence_invalid"


@dataclass(frozen=True, slots=True)
class RemittanceTransferEvidenceRecord:
    evidence_id: UUID
    remittance_id: UUID
    remittance_number: str
    destination_account_system_key: str
    business_date: date
    transferred_at: datetime
    external_reference: str
    evidence_note: str
    remittance_number_snapshot: str
    collector_user_id_snapshot: UUID
    recipient_user_id_snapshot: UUID
    custody_user_id_snapshot: UUID
    custody_transferred_at_snapshot: datetime
    collection_date_snapshot: date
    total_amount_snapshot: Decimal
    recorded_by_user_id: UUID
    recorded_at: datetime
    is_voided: bool
    voided_by_user_id: UUID | None
    voided_at: datetime | None
    void_reason: str | None


@dataclass(frozen=True, slots=True)
class RemittanceTransferReadinessRecord:
    remittance_id: UUID
    remittance_number: str
    collector_user_id: UUID
    collector_name: str
    recipient_user_id: UUID
    recipient_name: str
    custody_user_id: UUID | None
    custody_name: str | None
    collection_date: date
    remittance_status: str
    total_amount: Decimal
    received_at: datetime | None
    custody_transferred_at: datetime | None
    transfer_evidence_id: UUID | None
    destination_account_system_key: str | None
    business_date: date | None
    transferred_at: datetime | None
    external_reference: str | None
    readiness_status: str
    source_event_key: str | None
    debit_account_system_key: str | None
    credit_account_system_key: str | None
    debit_amount: Decimal | None
    credit_amount: Decimal | None
    income_recognition: bool
    journal_lines_enabled: bool
    automatic_source_posting: bool


class PostgresRemittanceAccountingEvidenceRepository:
    def list_readiness(
        self,
        *,
        readiness_status: str | None = None,
        limit: int = 100,
    ) -> tuple[RemittanceTransferReadinessRecord, ...]:
        safe_limit = max(1, min(int(limit), 250))
        normalized_status = (
            readiness_status.strip()
            if readiness_status and readiness_status.strip()
            else None
        )
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    rows = cursor.execute(
                        """
                        select *
                        from accounting.remittance_transfer_readiness
                        where (%s::text is null or readiness_status = %s::text)
                        order by collection_date desc, remittance_number, remittance_id
                        limit %s
                        """,
                        (normalized_status, normalized_status, safe_limit),
                    ).fetchall()
            return tuple(self._readiness_from_row(row) for row in rows)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def record(
        self,
        *,
        actor_user_id: UUID,
        remittance_id: UUID,
        destination_account_system_key: str,
        business_date: date,
        transferred_at: datetime,
        external_reference: str,
        evidence_note: str,
    ) -> RemittanceTransferEvidenceRecord:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    evidence_id = cursor.execute(
                        """
                        select accounting.record_remittance_transfer_evidence(
                            %s, %s, %s, %s, %s, %s, %s
                        ) as evidence_id
                        """,
                        (
                            remittance_id,
                            actor_user_id,
                            destination_account_system_key,
                            business_date,
                            transferred_at,
                            external_reference,
                            evidence_note,
                        ),
                    ).fetchone()["evidence_id"]
                    return self._fetch_evidence(cursor, evidence_id=evidence_id)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def void(
        self,
        *,
        actor_user_id: UUID,
        evidence_id: UUID,
        reason: str,
    ) -> RemittanceTransferEvidenceRecord:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "select accounting.void_remittance_transfer_evidence(%s, %s, %s)",
                        (evidence_id, actor_user_id, reason),
                    )
                    return self._fetch_evidence(cursor, evidence_id=evidence_id)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    @staticmethod
    def _fetch_evidence(
        cursor,
        *,
        evidence_id: UUID,
    ) -> RemittanceTransferEvidenceRecord:
        row = cursor.execute(
            """
            select evidence.*, remittance.remittance_number
            from accounting.remittance_transfer_evidence evidence
            join lending.collection_remittances remittance
              on remittance.id = evidence.remittance_id
            where evidence.id = %s
            """,
            (evidence_id,),
        ).fetchone()
        if row is None:
            raise RemittanceAccountingEvidenceNotFound(
                "Remittance transfer evidence was not found."
            )
        return RemittanceTransferEvidenceRecord(
            evidence_id=row["id"],
            remittance_id=row["remittance_id"],
            remittance_number=str(row["remittance_number"]),
            destination_account_system_key=str(
                row["destination_account_system_key"]
            ),
            business_date=row["business_date"],
            transferred_at=row["transferred_at"],
            external_reference=str(row["external_reference"]),
            evidence_note=str(row["evidence_note"] or ""),
            remittance_number_snapshot=str(row["remittance_number_snapshot"]),
            collector_user_id_snapshot=row["collector_user_id_snapshot"],
            recipient_user_id_snapshot=row["recipient_user_id_snapshot"],
            custody_user_id_snapshot=row["custody_user_id_snapshot"],
            custody_transferred_at_snapshot=row["custody_transferred_at_snapshot"],
            collection_date_snapshot=row["collection_date_snapshot"],
            total_amount_snapshot=Decimal(row["total_amount_snapshot"]),
            recorded_by_user_id=row["recorded_by_user_id"],
            recorded_at=row["recorded_at"],
            is_voided=bool(row["is_voided"]),
            voided_by_user_id=row["voided_by_user_id"],
            voided_at=row["voided_at"],
            void_reason=str(row["void_reason"]) if row["void_reason"] else None,
        )

    @staticmethod
    def _readiness_from_row(row) -> RemittanceTransferReadinessRecord:
        return RemittanceTransferReadinessRecord(
            remittance_id=row["remittance_id"],
            remittance_number=str(row["remittance_number"]),
            collector_user_id=row["collector_user_id"],
            collector_name=str(row["collector_name"]),
            recipient_user_id=row["recipient_user_id"],
            recipient_name=str(row["recipient_name"]),
            custody_user_id=row["custody_user_id"],
            custody_name=str(row["custody_name"]) if row["custody_name"] else None,
            collection_date=row["collection_date"],
            remittance_status=str(row["remittance_status"]),
            total_amount=Decimal(row["total_amount"]),
            received_at=row["received_at"],
            custody_transferred_at=row["custody_transferred_at"],
            transfer_evidence_id=row["transfer_evidence_id"],
            destination_account_system_key=(
                str(row["destination_account_system_key"])
                if row["destination_account_system_key"]
                else None
            ),
            business_date=row["business_date"],
            transferred_at=row["transferred_at"],
            external_reference=(
                str(row["external_reference"])
                if row["external_reference"]
                else None
            ),
            readiness_status=str(row["readiness_status"]),
            source_event_key=(
                str(row["source_event_key"]) if row["source_event_key"] else None
            ),
            debit_account_system_key=(
                str(row["debit_account_system_key"])
                if row["debit_account_system_key"]
                else None
            ),
            credit_account_system_key=(
                str(row["credit_account_system_key"])
                if row["credit_account_system_key"]
                else None
            ),
            debit_amount=(
                Decimal(row["debit_amount"])
                if row["debit_amount"] is not None
                else None
            ),
            credit_amount=(
                Decimal(row["credit_amount"])
                if row["credit_amount"] is not None
                else None
            ),
            income_recognition=bool(row["income_recognition"]),
            journal_lines_enabled=bool(row["journal_lines_enabled"]),
            automatic_source_posting=bool(row["automatic_source_posting"]),
        )

    @staticmethod
    def _map_error(error: psycopg.Error) -> RemittanceAccountingEvidenceError:
        message = str(error).split("CONTEXT:", 1)[0].strip()
        lower = message.lower()
        if "not found" in lower:
            return RemittanceAccountingEvidenceNotFound(message)
        if (
            "already" in lower
            or "different active" in lower
            or "journal history" in lower
            or "cannot" in lower
            or "immutable" in lower
        ):
            return RemittanceAccountingEvidenceConflict(message)
        return RemittanceAccountingEvidenceInvalid(
            message or "Remittance accounting evidence failed validation."
        )

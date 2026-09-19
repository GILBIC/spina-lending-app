"""Client-owned reads of issued packets retained by the office release authority."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection
from .first_loan_terms import snapshot_digest
from .first_loan_repository import _cash_snapshot, _sign_snapshot
from .office_review_evidence_storage import EvidenceFileError, PrivateEvidenceStore


class ClientDocumentNotFound(RuntimeError):
    pass


class ClientDocumentUnavailable(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ClientDocumentRecord:
    document_id: UUID
    loan_id: UUID
    content_sha256: str
    byte_count: int
    generated_at: datetime
    released_at: datetime
    kind: str = "finalized_loan_packet"
    media_type: str = "application/pdf"


@dataclass(frozen=True, slots=True)
class ClientDocumentDownload:
    record: ClientDocumentRecord
    content: bytes


class PostgresClientDocumentRepository:
    def _read(self, *, user_id: UUID, loan_id: UUID):
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                row = cursor.execute(
                    """
                    select document.id as document_id, document.loan_id,
                           document.content_sha256, document.byte_count,
                           document.generated_at, document.storage_key,
                           document.pricing_snapshot, release.released_at,
                           release.authorization_id, release.released_by_user_id,
                           release.contract_evidence_reference, release.cash_evidence_reference,
                           approval.id, approval.client_id, approval.cif_version_id,
                           approval.application_version_id, approval.packet, approval.packet_hash
                    from lending.clients client
                    join lending.loans loan on loan.client_id = client.id
                    join lending.first_loan_approvals approval
                      on approval.loan_id = loan.id and approval.client_id = client.id
                    join lending.first_loan_releases release
                      on release.loan_id = loan.id
                     and release.packet_hash = approval.packet_hash
                    join lending.first_loan_packet_documents document
                      on document.loan_id = loan.id
                     and document.packet_hash = approval.packet_hash
                    where client.user_id = %s and loan.id = %s
                    """,
                    (user_id, loan_id),
                ).fetchone()
                if row is None:
                    raise ClientDocumentNotFound(
                        "The requested document is unavailable."
                    )
                if snapshot_digest(row["packet"]) != row["packet_hash"]:
                    raise ClientDocumentUnavailable(
                        "The saved document is unavailable."
                    )
                # Read only the two immutable references used by this release. No
                # current CIF, approval permission, or unrelated office evidence.
                evidence = cursor.execute(
                    """select * from lending.office_review_evidence
                       where ('office-evidence:' || id::text) in (%s, %s)""",
                    (
                        row["contract_evidence_reference"],
                        row["cash_evidence_reference"],
                    ),
                ).fetchall()
        result = [
            (
                ClientDocumentRecord(
                    document_id=row["document_id"],
                    loan_id=row["loan_id"],
                    content_sha256=row["content_sha256"],
                    byte_count=row["byte_count"],
                    generated_at=row["generated_at"],
                    released_at=row["released_at"],
                ),
                row["storage_key"],
            )
        ]
        document = {
            "id": str(row["document_id"]),
            "content_sha256": row["content_sha256"],
            "byte_count": row["byte_count"],
            "pricing_snapshot": row["pricing_snapshot"],
        }
        expected = (
            (
                "contract_evidence_reference",
                "borrower_contract_signed",
                "signed_loan_contract",
                _sign_snapshot(row, document),
            ),
            (
                "cash_evidence_reference",
                "borrower_cash_received",
                "cash_release_acknowledgment",
                _cash_snapshot(row, row["authorization_id"], document),
            ),
        )
        for reference, purpose, kind, snapshot in expected:
            saved = next(
                (
                    item
                    for item in evidence
                    if f"office-evidence:{item['id']}" == row[reference]
                ),
                None,
            )
            if saved is None:
                continue  # Legacy non-file references are never reclassified as files.
            if any(
                (
                    saved["purpose"] != purpose,
                    saved["subject_id"] != row["id"],
                    saved["client_id"] != row["client_id"],
                    saved["cif_version_id"] != row["cif_version_id"],
                    saved["application_version_id"] != row["application_version_id"],
                    str(saved["application_id"])
                    != row["packet"]["application"]["application_id"],
                    saved["review_snapshot"] != snapshot,
                    saved["snapshot_sha256"] != snapshot_digest(snapshot),
                    purpose == "borrower_cash_received"
                    and saved["captured_by_user_id"] != row["released_by_user_id"],
                )
            ):
                raise ClientDocumentUnavailable("The saved document is unavailable.")
            result.append(
                (
                    ClientDocumentRecord(
                        document_id=saved["id"],
                        loan_id=row["loan_id"],
                        content_sha256=saved["content_sha256"],
                        byte_count=saved["byte_count"],
                        generated_at=saved["captured_at"],
                        released_at=row["released_at"],
                        kind=kind,
                        media_type=saved["media_type"],
                    ),
                    saved["request_id"],
                )
            )
        return result

    def list_for_user(
        self, *, user_id: UUID, loan_id: UUID
    ) -> tuple[ClientDocumentRecord, ...]:
        return tuple(
            record for record, _ in self._read(user_id=user_id, loan_id=loan_id)
        )

    def download_for_user(
        self, *, user_id: UUID, loan_id: UUID, document_id: UUID
    ) -> ClientDocumentDownload:
        selected = next(
            (
                (record, key)
                for record, key in self._read(user_id=user_id, loan_id=loan_id)
                if record.document_id == document_id
            ),
            None,
        )
        if selected is None:
            raise ClientDocumentNotFound("The requested document is unavailable.")
        record, key = selected
        try:
            content = PrivateEvidenceStore().read(
                key, record.content_sha256, record.byte_count
            )
        except EvidenceFileError as error:
            raise ClientDocumentUnavailable(
                "The saved document is unavailable."
            ) from error
        return ClientDocumentDownload(record=record, content=content)

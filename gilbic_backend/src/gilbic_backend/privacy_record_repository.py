"""Separate exact-version privacy evidence; optional consent never gates a loan."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .database import open_connection
from .office_review_evidence_repository import (
    OfficeReviewEvidenceConflict,
    _require_actor,
    require_evidence,
    snapshot_digest,
)


REQUIRED_FACTS = (
    "registered_lender_name",
    "registered_office_address",
    "dpo_name",
    "dpo_email",
    "retention_schedule_version",
    "provider_disclosures_version",
)


def privacy_package() -> dict:
    """Load operator-approved PDFs, never accept legal template paths from a client."""
    configured = os.getenv("GILBIC_PRIVACY_PACKAGE_MANIFEST", "").strip()
    unavailable = {
        "issuable": False,
        "detail": "Final privacy contact, retention and provider disclosures and approved PDFs must be configured before privacy signing.",
    }
    if not configured:
        return unavailable
    try:
        manifest_path = Path(configured)
        if not manifest_path.is_absolute():
            return unavailable
        data = json.loads(manifest_path.read_text(encoding="utf8"))
        facts = data["facts"]
        if data.get("approved_for_issuance") is not True or any(
            not isinstance(facts.get(key), str)
            or not facts[key].strip()
            or any(
                marker in facts[key].lower() for marker in ("to be finalized", "{", "}")
            )
            for key in REQUIRED_FACTS
        ):
            return unavailable
        result = {
            "issuable": True,
            "facts": {key: facts[key].strip() for key in REQUIRED_FACTS},
        }
        for kind in ("notice", "consent"):
            item = data[kind]
            path = Path(item["path"])
            if not path.is_absolute() or path.suffix.lower() != ".pdf":
                return unavailable
            content = path.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            if (
                not content.startswith(b"%PDF-")
                or len(content) > 10485760
                or digest != item["sha256"]
                or not str(item["version"]).strip()
            ):
                return unavailable
            result[kind] = {
                "version": str(item["version"]).strip(),
                "sha256": digest,
                "content": content,
            }
        return result
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return unavailable


def build_privacy_context(
    cursor,
    *,
    client_id: UUID,
    cif_version_id: UUID,
    optional_service_communications: bool = False,
    lock: bool = False,
) -> dict:
    cif = cursor.execute(
        """select cif.full_name, cif.phone_number, cif.email, cif.present_address
        from lending.client_cif_versions cif join lending.clients c on c.id = cif.client_id
        where cif.id = %s and cif.client_id = %s and cif.is_current
          and cif.status in ('draft', 'active') and c.status in ('active', 'inactive')
          and exists (select 1 from lending.client_onboarding_applicants a
            where a.promoted_client_id = c.id and a.status = 'eligible_for_cif')
        """
        + ("for update of cif, c" if lock else ""),
        (cif_version_id, client_id),
    ).fetchone()
    if cif is None:
        raise OfficeReviewEvidenceConflict(
            "The exact current eligible CIF is required for privacy acknowledgment."
        )
    package = privacy_package()
    snapshot = {
        "schema_version": 1,
        "scope": "privacy_acknowledgment",
        "client_id": str(client_id),
        "cif_version_id": str(cif_version_id),
        "cif_information": dict(cif),
        "optional_service_communications": optional_service_communications,
    }
    if package["issuable"]:
        for kind in ("notice", "consent"):
            item = package[kind]
            if lock:
                # Cross-Client confirmations must not approve different bytes under
                # one document version concurrently. Read-only contexts take no lock.
                cursor.execute(
                    "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (f"privacy-document:{kind}:{item['version']}",),
                )
            collision = cursor.execute(
                f"select 1 from lending.client_privacy_acknowledgments where {kind}_version = %s and {kind}_sha256 <> %s limit 1",
                (item["version"], item["sha256"]),
            ).fetchone()
            if collision:
                raise OfficeReviewEvidenceConflict(
                    "Privacy template content changed without a new version."
                )
            snapshot[kind] = {"version": item["version"], "sha256": item["sha256"]}
        snapshot["facts"] = package["facts"]
    return {
        "client_id": str(client_id),
        "cif_version_id": str(cif_version_id),
        "application_id": None,
        "application_version_id": None,
        "purpose": "privacy_acknowledgment",
        "subject_id": str(cif_version_id),
        "review_snapshot": snapshot,
        "snapshot_sha256": snapshot_digest(snapshot),
        "issuable": package["issuable"],
        "issuance_ready": package["issuable"],
        "detail": package.get(
            "detail",
            "Review both documents before recording the borrower acknowledgment. Optional service communications are not required for a loan.",
        ),
    }


class PostgresPrivacyRecordRepository:
    def context(self, *, actor_user_id: UUID, **source) -> dict:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                _require_actor(cursor, actor_user_id)
                context = build_privacy_context(cursor, **source)
                row = cursor.execute(
                    """select * from lending.client_privacy_acknowledgments
                    where client_id = %s and cif_version_id = %s
                    order by acknowledged_at desc, id desc limit 1""",
                    (source["client_id"], source["cif_version_id"]),
                ).fetchone()
                context["acknowledgment"] = self.payload(row) if row else None
                return context

    def confirm(
        self,
        *,
        actor_user_id: UUID,
        client_id: UUID,
        cif_version_id: UUID,
        optional_service_communications: bool,
        evidence_reference: str,
    ) -> dict:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                _require_actor(cursor, actor_user_id)
                context = build_privacy_context(
                    cursor,
                    client_id=client_id,
                    cif_version_id=cif_version_id,
                    optional_service_communications=optional_service_communications,
                    lock=True,
                )
                if not context["issuable"]:
                    raise OfficeReviewEvidenceConflict(context["detail"])
                snapshot = context["review_snapshot"]
                evidence = require_evidence(
                    cursor,
                    evidence_reference=evidence_reference,
                    actor_user_id=actor_user_id,
                    client_id=client_id,
                    purpose="privacy_acknowledgment",
                    subject_id=cif_version_id,
                    review_snapshot=snapshot,
                )
                existing = cursor.execute(
                    "select * from lending.client_privacy_acknowledgments where evidence_id = %s",
                    (evidence.id,),
                ).fetchone()
                if existing is not None:
                    return self.payload(existing)
                row = cursor.execute(
                    """insert into lending.client_privacy_acknowledgments
                    (client_id, cif_version_id, notice_version, notice_sha256,
                     consent_version, consent_sha256, optional_service_communications,
                     evidence_id, review_snapshot, acknowledged_by_user_id)
                    values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning *""",
                    (
                        client_id,
                        cif_version_id,
                        snapshot["notice"]["version"],
                        snapshot["notice"]["sha256"],
                        snapshot["consent"]["version"],
                        snapshot["consent"]["sha256"],
                        optional_service_communications,
                        evidence.id,
                        Jsonb(snapshot),
                        actor_user_id,
                    ),
                ).fetchone()
                cursor.execute(
                    """insert into core.audit_logs(actor_user_id,action,target_type,target_id,details)
                    values (%s,'client_privacy.acknowledged','client',%s,%s)""",
                    (
                        actor_user_id,
                        client_id,
                        Jsonb(
                            {
                                "acknowledgment_id": str(row["id"]),
                                "evidence_id": str(evidence.id),
                            }
                        ),
                    ),
                )
                return self.payload(row)

    @staticmethod
    def payload(row) -> dict:
        return {
            key: str(row[key])
            if isinstance(row[key], UUID)
            else row[key].isoformat()
            if key == "acknowledged_at"
            else row[key]
            for key in (
                "id",
                "client_id",
                "cif_version_id",
                "notice_version",
                "notice_sha256",
                "consent_version",
                "consent_sha256",
                "optional_service_communications",
                "evidence_id",
                "acknowledged_by_user_id",
                "acknowledged_at",
            )
        }

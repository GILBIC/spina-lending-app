from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from .account_repository import AccountContext, PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .request_auth import authenticated_device_context
from .restricted_identity_repository import (
    PostgresRestrictedIdentityRepository,
    RestrictedEvidenceData,
    RestrictedEvidenceRecord,
    RestrictedIdentityConflict,
    RestrictedIdentityError,
    RestrictedIdentityInvalid,
    RestrictedIdentityNotFound,
)


class RestrictedEvidenceBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    client_id: UUID
    evidence_type: Literal[
        "national_id_check",
        "government_id_metadata",
        "utility_proof",
        "residence_visit",
        "approved_exception",
    ]
    verification_method: str = Field(min_length=1, max_length=120)
    verification_outcome: Literal[
        "verified",
        "not_verified",
        "inconclusive",
        "exception_approved",
    ]
    checked_at: AwareDatetime
    document_date: date | None = None
    document_expires_at: date | None = None
    masked_reference: str = Field(min_length=1, max_length=120)
    external_evidence_reference: str = Field(min_length=1, max_length=500)
    evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    retention_class: Literal[
        "identity_verification",
        "residence_verification",
        "approved_exception",
    ]
    retain_until: date
    legal_hold: bool = False
    supersedes_evidence_id: UUID | None = None


class RestrictedEvidenceReviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: Literal["approved", "rejected"]
    review_note: str = Field(min_length=1, max_length=1000)


def restricted_identity_repository_dependency() -> (
    PostgresRestrictedIdentityRepository
):
    return PostgresRestrictedIdentityRepository()


def _evidence_data(body: RestrictedEvidenceBody) -> RestrictedEvidenceData:
    return RestrictedEvidenceData(
        evidence_type=body.evidence_type,
        verification_method=body.verification_method,
        verification_outcome=body.verification_outcome,
        checked_at=datetime.fromisoformat(body.checked_at.isoformat()),
        document_date=body.document_date,
        document_expires_at=body.document_expires_at,
        masked_reference=body.masked_reference,
        external_evidence_reference=body.external_evidence_reference,
        evidence_digest=body.evidence_digest,
        retention_class=body.retention_class,
        retain_until=body.retain_until,
        legal_hold=body.legal_hold,
        supersedes_evidence_id=body.supersedes_evidence_id,
    )


def _record_payload(record: RestrictedEvidenceRecord) -> dict[str, object]:
    return {
        "evidence_id": str(record.evidence_id),
        "client_id": str(record.client_id),
        "cif_id": str(record.cif_id),
        "evidence_type": record.evidence_type,
        "verification_method": record.verification_method,
        "verification_outcome": record.verification_outcome,
        "checked_at": record.checked_at.isoformat(),
        "document_date": (
            record.document_date.isoformat() if record.document_date else None
        ),
        "document_expires_at": (
            record.document_expires_at.isoformat()
            if record.document_expires_at
            else None
        ),
        "masked_reference": record.masked_reference,
        "external_evidence_reference": record.external_evidence_reference,
        "evidence_digest": record.evidence_digest,
        "retention_class": record.retention_class,
        "retain_until": record.retain_until.isoformat(),
        "legal_hold": record.legal_hold,
        "recorded_by_user_id": str(record.recorded_by_user_id),
        "recorded_at": record.recorded_at.isoformat(),
        "supersedes_evidence_id": (
            str(record.supersedes_evidence_id)
            if record.supersedes_evidence_id
            else None
        ),
        "review_decision": record.review_decision,
        "review_note": record.review_note,
        "reviewed_by_user_id": (
            str(record.reviewed_by_user_id) if record.reviewed_by_user_id else None
        ),
        "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
        "is_superseded": record.is_superseded,
    }


def _raise_restricted_error(error: RestrictedIdentityError) -> None:
    if isinstance(error, RestrictedIdentityNotFound):
        status_code = 404
    elif isinstance(error, RestrictedIdentityInvalid):
        status_code = 422
    elif isinstance(error, RestrictedIdentityConflict):
        status_code = 409
    else:
        status_code = 409
    raise HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    ) from error


def _require_headers(
    *,
    x_access_purpose: str | None,
    x_request_id: str | None,
) -> tuple[str, UUID]:
    purpose = (x_access_purpose or "").strip().lower()
    if not purpose:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "restricted_access_purpose_required",
                "message": "X-Access-Purpose is required for restricted evidence.",
            },
        )
    if len(purpose) > 80:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "restricted_access_purpose_invalid",
                "message": "X-Access-Purpose is invalid.",
            },
        )
    raw_request_id = (x_request_id or "").strip()
    if not raw_request_id:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "restricted_request_id_required",
                "message": "X-Request-Id is required for restricted evidence.",
            },
        )
    try:
        request_id = UUID(raw_request_id)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "restricted_request_id_invalid",
                "message": "X-Request-Id must be a UUID.",
            },
        ) from error
    return purpose, request_id


def _require_restricted_management(
    *,
    authorization: str | None,
    x_device_id: str | None,
    permission: str,
    auth: SupabaseAuthClient,
    accounts: PostgresAccountRepository,
) -> AccountContext:
    actor = authenticated_device_context(
        authorization=authorization,
        device_identifier=x_device_id,
        auth=auth,
        accounts=accounts,
        permission=permission,
        permission_error="Restricted identity-evidence permission is required.",
    )
    if "management" not in actor.roles:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "management_role_required",
                "message": "Only Management may access restricted identity evidence.",
            },
        )
    if actor.registered_device_id is None:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "registered_device_required",
                "message": "An active registered device is required for restricted evidence.",
            },
        )
    return actor


def create_restricted_identity_router() -> APIRouter:
    router = APIRouter(tags=["restricted identity evidence"])

    @router.get("/api/v1/management/cifs/{cif_id}/verification-evidence")
    def list_restricted_evidence(
        cif_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        x_access_purpose: str | None = Header(
            default=None,
            alias="X-Access-Purpose",
        ),
        x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRestrictedIdentityRepository = Depends(
            restricted_identity_repository_dependency
        ),
    ) -> dict[str, object]:
        purpose, request_id = _require_headers(
            x_access_purpose=x_access_purpose,
            x_request_id=x_request_id,
        )
        actor = _require_restricted_management(
            authorization=authorization,
            x_device_id=x_device_id,
            permission="identity_evidence.view",
            auth=auth,
            accounts=accounts,
        )
        assert actor.registered_device_id is not None
        try:
            records = repository.list_for_cif(
                actor_user_id=actor.user_id,
                registered_device_id=actor.registered_device_id,
                request_id=request_id,
                purpose_code=purpose,
                cif_id=cif_id,
            )
        except RestrictedIdentityError as error:
            _raise_restricted_error(error)
        return {"success": True, "data": [_record_payload(item) for item in records]}

    @router.post("/api/v1/management/cifs/{cif_id}/verification-evidence")
    def record_restricted_evidence(
        cif_id: UUID,
        body: RestrictedEvidenceBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        x_access_purpose: str | None = Header(
            default=None,
            alias="X-Access-Purpose",
        ),
        x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRestrictedIdentityRepository = Depends(
            restricted_identity_repository_dependency
        ),
    ) -> dict[str, object]:
        purpose, request_id = _require_headers(
            x_access_purpose=x_access_purpose,
            x_request_id=x_request_id,
        )
        actor = _require_restricted_management(
            authorization=authorization,
            x_device_id=x_device_id,
            permission="identity_evidence.record",
            auth=auth,
            accounts=accounts,
        )
        assert actor.registered_device_id is not None
        try:
            record = repository.record(
                actor_user_id=actor.user_id,
                registered_device_id=actor.registered_device_id,
                request_id=request_id,
                purpose_code=purpose,
                client_id=body.client_id,
                cif_id=cif_id,
                data=_evidence_data(body),
            )
        except RestrictedIdentityError as error:
            _raise_restricted_error(error)
        return {"success": True, "data": _record_payload(record)}

    @router.post(
        "/api/v1/management/verification-evidence/{evidence_id}/review"
    )
    def review_restricted_evidence(
        evidence_id: UUID,
        body: RestrictedEvidenceReviewBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        x_access_purpose: str | None = Header(
            default=None,
            alias="X-Access-Purpose",
        ),
        x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRestrictedIdentityRepository = Depends(
            restricted_identity_repository_dependency
        ),
    ) -> dict[str, object]:
        purpose, request_id = _require_headers(
            x_access_purpose=x_access_purpose,
            x_request_id=x_request_id,
        )
        actor = _require_restricted_management(
            authorization=authorization,
            x_device_id=x_device_id,
            permission="identity_evidence.review",
            auth=auth,
            accounts=accounts,
        )
        assert actor.registered_device_id is not None
        try:
            record = repository.review(
                actor_user_id=actor.user_id,
                registered_device_id=actor.registered_device_id,
                request_id=request_id,
                purpose_code=purpose,
                evidence_id=evidence_id,
                decision=body.decision,
                review_note=body.review_note,
            )
        except RestrictedIdentityError as error:
            _raise_restricted_error(error)
        return {"success": True, "data": _record_payload(record)}

    return router

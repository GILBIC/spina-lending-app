from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .request_auth import authenticated_device_context
from .restricted_identity_repository import (
    PostgresRestrictedIdentityRepository,
    RestrictedEvidenceConflict,
    RestrictedEvidenceInput,
    RestrictedEvidenceNotFound,
    RestrictedEvidenceRecord,
    RestrictedEvidenceValidationError,
    RestrictedIdentityRepositoryError,
)


class StrictRestrictedEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RestrictedEvidenceRequest(StrictRestrictedEvidenceRequest):
    evidence_type: Literal[
        "national_id_check",
        "everify_outcome",
        "government_id_metadata",
        "utility_proof",
        "residence_visit",
        "approved_exception",
    ]
    verification_method: str = Field(min_length=1, max_length=150)
    verification_result: Literal[
        "verified",
        "not_verified",
        "inconclusive",
        "exception_approved",
    ]
    checked_at: datetime
    document_date: date | None = None
    document_expires_at: datetime | None = None
    masked_reference: str | None = Field(default=None, max_length=120)
    external_evidence_reference: str = Field(min_length=1, max_length=500)
    evidence_sha256: str = Field(min_length=64, max_length=64)
    retention_class: Literal[
        "identity_verification",
        "residence_verification",
        "exception_evidence",
    ]
    retain_until: date
    legal_hold: bool = False


class RestrictedEvidenceReviewRequest(StrictRestrictedEvidenceRequest):
    decision: Literal["verified", "rejected"]


def restricted_identity_repository_dependency(
) -> PostgresRestrictedIdentityRepository:
    return PostgresRestrictedIdentityRepository()


def _evidence_input(
    request: RestrictedEvidenceRequest,
) -> RestrictedEvidenceInput:
    return RestrictedEvidenceInput(
        evidence_type=request.evidence_type,
        verification_method=request.verification_method,
        verification_result=request.verification_result,
        checked_at=request.checked_at,
        document_date=request.document_date,
        document_expires_at=request.document_expires_at,
        masked_reference=request.masked_reference,
        external_evidence_reference=(
            request.external_evidence_reference
        ),
        evidence_sha256=request.evidence_sha256,
        retention_class=request.retention_class,
        retain_until=request.retain_until,
        legal_hold=request.legal_hold,
    )


def _evidence_payload(
    record: RestrictedEvidenceRecord,
) -> dict[str, object]:
    return {
        "evidence_id": str(record.evidence_id),
        "cif_id": str(record.cif_id),
        "client_id": str(record.client_id),
        "evidence_type": record.evidence_type,
        "verification_method": record.verification_method,
        "verification_result": record.verification_result,
        "checked_at": record.checked_at.isoformat(),
        "document_date": (
            record.document_date.isoformat()
            if record.document_date
            else None
        ),
        "document_expires_at": (
            record.document_expires_at.isoformat()
            if record.document_expires_at
            else None
        ),
        "masked_reference": record.masked_reference,
        "external_evidence_reference": (
            record.external_evidence_reference
        ),
        "evidence_sha256": record.evidence_sha256,
        "retention_class": record.retention_class,
        "retain_until": record.retain_until.isoformat(),
        "legal_hold": record.legal_hold,
        "review_state": record.review_state,
        "verified_by_user_id": str(record.verified_by_user_id),
        "final_reviewed_by_user_id": (
            str(record.final_reviewed_by_user_id)
            if record.final_reviewed_by_user_id
            else None
        ),
        "reviewed_at": (
            record.reviewed_at.isoformat()
            if record.reviewed_at
            else None
        ),
        "supersedes_evidence_id": (
            str(record.supersedes_evidence_id)
            if record.supersedes_evidence_id
            else None
        ),
        "created_by_user_id": str(record.created_by_user_id),
        "created_at": record.created_at.isoformat(),
    }


def _require_restricted_actor(
    *,
    authorization: str | None,
    x_device_id: str | None,
    permission: str,
    auth: SupabaseAuthClient,
    accounts: PostgresAccountRepository,
) -> Any:
    actor = authenticated_device_context(
        authorization=authorization,
        device_identifier=x_device_id,
        permissions=(permission,),
        auth=auth,
        accounts=accounts,
    )
    if "management" not in actor.roles:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "restricted_identity_management_required",
                "message": (
                    "Restricted identity evidence is available only to "
                    "authorized Management users."
                ),
            },
        )
    return actor


def _actor_registered_device_id(actor: Any) -> UUID:
    for attribute in ("registered_device_id", "device_id"):
        value = getattr(actor, attribute, None)
        if value is not None:
            try:
                return UUID(str(value))
            except ValueError:
                pass
    device = getattr(actor, "device", None)
    value = getattr(device, "id", None)
    if value is not None:
        try:
            return UUID(str(value))
        except ValueError:
            pass
    raise HTTPException(
        status_code=500,
        detail={
            "code": "registered_device_context_missing",
            "message": (
                "The authenticated registered-device context is incomplete."
            ),
        },
    )


def _evidence_headers(
    *,
    purpose: str | None,
    request_id: str | None,
) -> tuple[str, UUID]:
    normalized_purpose = (purpose or "").strip().lower()
    if not normalized_purpose:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "evidence_purpose_required",
                "message": (
                    "X-Evidence-Purpose is required for restricted evidence."
                ),
            },
        )
    try:
        parsed_request_id = UUID((request_id or "").strip())
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "evidence_request_id_required",
                "message": (
                    "X-Request-Id must be a valid UUID for restricted evidence."
                ),
            },
        ) from error
    return normalized_purpose, parsed_request_id


def _raise_safe(error: Exception) -> None:
    if isinstance(error, RestrictedEvidenceNotFound):
        status_code = 404
    elif isinstance(error, RestrictedEvidenceConflict):
        status_code = 409
    elif isinstance(error, RestrictedEvidenceValidationError):
        status_code = 400
    elif isinstance(error, RestrictedIdentityRepositoryError):
        status_code = 503
    else:
        raise error
    raise HTTPException(
        status_code=status_code,
        detail={
            "code": getattr(
                error,
                "code",
                "restricted_evidence_request_failed",
            ),
            "message": str(error),
        },
    ) from error


def create_restricted_identity_router() -> APIRouter:
    router = APIRouter(tags=["management restricted identity evidence"])

    @router.get(
        "/api/v1/management/cifs/{cif_id}/verification-evidence"
    )
    def list_evidence(
        cif_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        x_evidence_purpose: str | None = Header(
            default=None,
            alias="X-Evidence-Purpose",
        ),
        x_request_id: str | None = Header(
            default=None,
            alias="X-Request-Id",
        ),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(
            account_repository_dependency
        ),
        repository: PostgresRestrictedIdentityRepository = Depends(
            restricted_identity_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _require_restricted_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            permission="identity_evidence.view",
            auth=auth,
            accounts=accounts,
        )
        purpose, request_id = _evidence_headers(
            purpose=x_evidence_purpose,
            request_id=x_request_id,
        )
        try:
            records = repository.list_for_cif(
                cif_id=cif_id,
                actor_user_id=actor.user_id,
                registered_device_id=_actor_registered_device_id(actor),
                purpose_code=purpose,
                request_id=request_id,
            )
        except Exception as error:
            _raise_safe(error)
        return {
            "success": True,
            "data": {
                "cif_id": str(cif_id),
                "evidence": [
                    _evidence_payload(record) for record in records
                ],
            },
        }

    @router.post(
        "/api/v1/management/cifs/{cif_id}/verification-evidence"
    )
    def create_evidence(
        cif_id: UUID,
        request: RestrictedEvidenceRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        x_evidence_purpose: str | None = Header(
            default=None,
            alias="X-Evidence-Purpose",
        ),
        x_request_id: str | None = Header(
            default=None,
            alias="X-Request-Id",
        ),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(
            account_repository_dependency
        ),
        repository: PostgresRestrictedIdentityRepository = Depends(
            restricted_identity_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _require_restricted_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            permission="identity_evidence.manage",
            auth=auth,
            accounts=accounts,
        )
        purpose, request_id = _evidence_headers(
            purpose=x_evidence_purpose,
            request_id=x_request_id,
        )
        try:
            record = repository.create(
                cif_id=cif_id,
                actor_user_id=actor.user_id,
                registered_device_id=_actor_registered_device_id(actor),
                purpose_code=purpose,
                request_id=request_id,
                evidence=_evidence_input(request),
            )
        except Exception as error:
            _raise_safe(error)
        return {"success": True, "data": _evidence_payload(record)}

    @router.post(
        "/api/v1/management/verification-evidence/{evidence_id}/review"
    )
    def review_evidence(
        evidence_id: UUID,
        request: RestrictedEvidenceReviewRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        x_evidence_purpose: str | None = Header(
            default=None,
            alias="X-Evidence-Purpose",
        ),
        x_request_id: str | None = Header(
            default=None,
            alias="X-Request-Id",
        ),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(
            account_repository_dependency
        ),
        repository: PostgresRestrictedIdentityRepository = Depends(
            restricted_identity_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _require_restricted_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            permission="identity_evidence.manage",
            auth=auth,
            accounts=accounts,
        )
        purpose, request_id = _evidence_headers(
            purpose=x_evidence_purpose,
            request_id=x_request_id,
        )
        try:
            record = repository.review(
                evidence_id=evidence_id,
                actor_user_id=actor.user_id,
                registered_device_id=_actor_registered_device_id(actor),
                purpose_code=purpose,
                request_id=request_id,
                decision=request.decision,
            )
        except Exception as error:
            _raise_safe(error)
        return {"success": True, "data": _evidence_payload(record)}

    @router.post(
        "/api/v1/management/verification-evidence/{evidence_id}/supersede"
    )
    def supersede_evidence(
        evidence_id: UUID,
        request: RestrictedEvidenceRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        x_evidence_purpose: str | None = Header(
            default=None,
            alias="X-Evidence-Purpose",
        ),
        x_request_id: str | None = Header(
            default=None,
            alias="X-Request-Id",
        ),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(
            account_repository_dependency
        ),
        repository: PostgresRestrictedIdentityRepository = Depends(
            restricted_identity_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _require_restricted_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            permission="identity_evidence.manage",
            auth=auth,
            accounts=accounts,
        )
        purpose, request_id = _evidence_headers(
            purpose=x_evidence_purpose,
            request_id=x_request_id,
        )
        try:
            record = repository.supersede(
                evidence_id=evidence_id,
                replacement=_evidence_input(request),
                actor_user_id=actor.user_id,
                registered_device_id=_actor_registered_device_id(actor),
                purpose_code=purpose,
                request_id=request_id,
            )
        except Exception as error:
            _raise_safe(error)
        return {"success": True, "data": _evidence_payload(record)}

    return router

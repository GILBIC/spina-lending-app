from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .cif_repository import (
    CifClientNotFound,
    CifConflict,
    CifDraftInput,
    CifInvalidTransition,
    CifNotFound,
    CifRecord,
    CifStaleRevision,
    CifValidationError,
    PostgresCifRepository,
)
from .request_auth import authenticated_device_context


class StrictCifRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CifDraftRequest(StrictCifRequest):
    legal_full_name: str = Field(min_length=1, max_length=250)
    birth_date: date | None = None
    nationality: str | None = Field(default=None, max_length=100)
    civil_status: str | None = Field(default=None, max_length=100)
    phone_number: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=250)
    present_address: dict[str, str | int | float | bool] = Field(
        default_factory=dict
    )
    permanent_address: dict[str, str | int | float | bool] = Field(
        default_factory=dict
    )
    livelihood_profile: dict[str, str | int | float | bool] = Field(
        default_factory=dict
    )
    privacy_notice_version: str = Field(min_length=1, max_length=100)
    privacy_acknowledged_at: datetime | None = None
    client_signature_reference: str | None = Field(
        default=None,
        max_length=500,
    )
    client_signature_sha256: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )
    form_schema_version: str = Field(default="cif-v1", max_length=100)


class CifUpdateRequest(CifDraftRequest):
    expected_revision: int = Field(gt=0)


class CifWorkflowRequest(StrictCifRequest):
    expected_revision: int = Field(gt=0)


class CifReverificationRequest(StrictCifRequest):
    reason: Literal[
        "material_identity_change",
        "address_change",
        "contact_change",
        "document_expiry",
        "discrepancy",
        "suspicious_activity",
        "other_risk_event",
    ]
    severity: Literal["standard", "elevated", "critical"] = "standard"
    note: str = Field(default="", max_length=1000)


def cif_repository_dependency() -> PostgresCifRepository:
    return PostgresCifRepository()


def _draft_input(request: CifDraftRequest) -> CifDraftInput:
    return CifDraftInput(
        legal_full_name=request.legal_full_name,
        birth_date=request.birth_date,
        nationality=request.nationality,
        civil_status=request.civil_status,
        phone_number=request.phone_number,
        email=request.email,
        present_address=request.present_address,
        permanent_address=request.permanent_address,
        livelihood_profile=request.livelihood_profile,
        privacy_notice_version=request.privacy_notice_version,
        privacy_acknowledged_at=request.privacy_acknowledged_at,
        client_signature_reference=request.client_signature_reference,
        client_signature_sha256=request.client_signature_sha256,
        form_schema_version=request.form_schema_version,
    )


def _cif_payload(record: CifRecord) -> dict[str, object]:
    return {
        "cif_id": str(record.cif_id),
        "cif_number": record.cif_number,
        "client_id": str(record.client_id),
        "form_version": record.form_version,
        "durable_state": record.durable_state.value,
        "status": record.public_status,
        "is_eligible_for_new_credit": record.is_eligible_for_new_credit,
        "reverification_required": record.reverification_required,
        "allows_existing_obligation_servicing": (
            record.allows_existing_obligation_servicing
        ),
        "effective_at": (
            record.effective_at.isoformat() if record.effective_at else None
        ),
        "expires_at": (
            record.expires_at.isoformat() if record.expires_at else None
        ),
        "supersedes_cif_id": (
            str(record.supersedes_cif_id)
            if record.supersedes_cif_id
            else None
        ),
        "legal_full_name": record.legal_full_name,
        "birth_date": (
            record.birth_date.isoformat() if record.birth_date else None
        ),
        "nationality": record.nationality,
        "civil_status": record.civil_status,
        "phone_number": record.phone_number,
        "email": record.email,
        "present_address": record.present_address,
        "permanent_address": record.permanent_address,
        "livelihood_profile": record.livelihood_profile,
        "privacy_notice_version": record.privacy_notice_version,
        "privacy_acknowledged_at": (
            record.privacy_acknowledged_at.isoformat()
            if record.privacy_acknowledged_at
            else None
        ),
        "client_signature_recorded": bool(
            record.client_signature_reference
            and record.client_signature_sha256
        ),
        "prepared_by_user_id": str(record.prepared_by_user_id),
        "verified_by_user_id": (
            str(record.verified_by_user_id)
            if record.verified_by_user_id
            else None
        ),
        "verified_at": (
            record.verified_at.isoformat() if record.verified_at else None
        ),
        "approved_by_user_id": (
            str(record.approved_by_user_id)
            if record.approved_by_user_id
            else None
        ),
        "approved_at": (
            record.approved_at.isoformat() if record.approved_at else None
        ),
        "form_schema_version": record.form_schema_version,
        "draft_revision": record.draft_revision,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _require_actor(
    *,
    authorization: str | None,
    x_device_id: str | None,
    permission: str,
    allowed_roles: frozenset[str],
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
    if not allowed_roles.intersection(actor.roles):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "cif_role_required",
                "message": "This CIF action is not available for this role.",
            },
        )
    return actor


def _raise_safe(error: Exception) -> None:
    if isinstance(error, (CifNotFound, CifClientNotFound)):
        status_code = 404
    elif isinstance(
        error,
        (CifConflict, CifInvalidTransition, CifStaleRevision),
    ):
        status_code = 409
    elif isinstance(error, CifValidationError):
        status_code = 400
    else:
        raise error
    raise HTTPException(
        status_code=status_code,
        detail={
            "code": getattr(error, "code", "cif_request_failed"),
            "message": str(error),
        },
    ) from error


def create_cif_router() -> APIRouter:
    router = APIRouter(tags=["management CIF"])
    office_roles = frozenset({"employee", "management"})
    management_role = frozenset({"management"})

    @router.get("/api/v1/management/clients/{client_id}/cifs")
    def list_cifs(
        client_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(
            account_repository_dependency
        ),
        repository: PostgresCifRepository = Depends(
            cif_repository_dependency
        ),
    ) -> dict[str, object]:
        _require_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            permission="cif.view",
            allowed_roles=office_roles,
            auth=auth,
            accounts=accounts,
        )
        try:
            records = repository.list_for_client(client_id=client_id)
        except Exception as error:
            _raise_safe(error)
        return {
            "success": True,
            "data": {
                "client_id": str(client_id),
                "cifs": [_cif_payload(record) for record in records],
            },
        }

    @router.post("/api/v1/management/clients/{client_id}/cifs")
    def create_cif(
        client_id: UUID,
        request: CifDraftRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(
            account_repository_dependency
        ),
        repository: PostgresCifRepository = Depends(
            cif_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _require_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            permission="cif.prepare",
            allowed_roles=office_roles,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = repository.create_draft(
                client_id=client_id,
                actor_user_id=actor.user_id,
                draft=_draft_input(request),
            )
        except Exception as error:
            _raise_safe(error)
        return {"success": True, "data": _cif_payload(record)}

    @router.get("/api/v1/management/cifs/{cif_id}")
    def get_cif(
        cif_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(
            account_repository_dependency
        ),
        repository: PostgresCifRepository = Depends(
            cif_repository_dependency
        ),
    ) -> dict[str, object]:
        _require_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            permission="cif.view",
            allowed_roles=office_roles,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = repository.get(cif_id=cif_id)
        except Exception as error:
            _raise_safe(error)
        return {"success": True, "data": _cif_payload(record)}

    @router.patch("/api/v1/management/cifs/{cif_id}")
    def update_cif(
        cif_id: UUID,
        request: CifUpdateRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(
            account_repository_dependency
        ),
        repository: PostgresCifRepository = Depends(
            cif_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _require_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            permission="cif.prepare",
            allowed_roles=office_roles,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = repository.update_draft(
                cif_id=cif_id,
                actor_user_id=actor.user_id,
                expected_revision=request.expected_revision,
                draft=_draft_input(request),
            )
        except Exception as error:
            _raise_safe(error)
        return {"success": True, "data": _cif_payload(record)}

    @router.post("/api/v1/management/cifs/{cif_id}/verify")
    def verify_cif(
        cif_id: UUID,
        request: CifWorkflowRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(
            account_repository_dependency
        ),
        repository: PostgresCifRepository = Depends(
            cif_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _require_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            permission="cif.verify",
            allowed_roles=management_role,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = repository.verify(
                cif_id=cif_id,
                actor_user_id=actor.user_id,
                expected_revision=request.expected_revision,
            )
        except Exception as error:
            _raise_safe(error)
        return {"success": True, "data": _cif_payload(record)}

    @router.post("/api/v1/management/cifs/{cif_id}/activate")
    def activate_cif(
        cif_id: UUID,
        request: CifWorkflowRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(
            account_repository_dependency
        ),
        repository: PostgresCifRepository = Depends(
            cif_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _require_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            permission="cif.approve",
            allowed_roles=management_role,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = repository.activate(
                cif_id=cif_id,
                actor_user_id=actor.user_id,
                expected_revision=request.expected_revision,
            )
        except Exception as error:
            _raise_safe(error)
        return {"success": True, "data": _cif_payload(record)}

    @router.post(
        "/api/v1/management/clients/{client_id}/cif-reverification"
    )
    def open_reverification(
        client_id: UUID,
        request: CifReverificationRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(
            account_repository_dependency
        ),
        repository: PostgresCifRepository = Depends(
            cif_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _require_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            permission="cif.reverification.open",
            allowed_roles=management_role,
            auth=auth,
            accounts=accounts,
        )
        try:
            requirement_id = repository.open_reverification(
                client_id=client_id,
                actor_user_id=actor.user_id,
                reason=request.reason,
                severity=request.severity,
                note=request.note,
            )
        except Exception as error:
            _raise_safe(error)
        return {
            "success": True,
            "data": {
                "requirement_id": str(requirement_id),
                "client_id": str(client_id),
                "status": "open",
            },
        }

    return router

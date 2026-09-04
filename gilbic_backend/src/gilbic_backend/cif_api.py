from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from .account_repository import AccountContext, PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .cif_repository import (
    CifClientSummary,
    CifConflict,
    CifDraftData,
    CifError,
    CifInvalid,
    CifNotFound,
    CifReverificationRecord,
    ClientInformationFormRecord,
    PostgresCifRepository,
)
from .request_auth import authenticated_device_context


class CifAddressBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    line1: str | None = Field(default=None, max_length=300)
    line2: str | None = Field(default=None, max_length=300)
    barangay: str | None = Field(default=None, max_length=200)
    city_municipality: str | None = Field(default=None, max_length=200)
    province: str | None = Field(default=None, max_length=200)
    postal_code: str | None = Field(default=None, max_length=30)
    landmark: str | None = Field(default=None, max_length=300)


class CifLivelihoodBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: str | None = Field(default=None, max_length=100)
    employer_or_business: str | None = Field(default=None, max_length=300)
    position_or_activity: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=300)
    years_active: int | None = Field(default=None, ge=0, le=100)


class CifDraftBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    legal_full_name: str = Field(min_length=1, max_length=200)
    birth_date: date | None = None
    place_of_birth: str = Field(default="", max_length=200)
    nationality: str = Field(default="", max_length=100)
    civil_status: str = Field(default="", max_length=50)
    phone_number: str = Field(default="", max_length=40)
    email: str | None = Field(default=None, max_length=254)
    present_address: CifAddressBody = Field(default_factory=CifAddressBody)
    permanent_address: CifAddressBody = Field(default_factory=CifAddressBody)
    same_as_present_address: bool = False
    livelihood_profile: CifLivelihoodBody = Field(default_factory=CifLivelihoodBody)
    privacy_notice_version: str = Field(default="", max_length=100)
    privacy_acknowledged_at: AwareDatetime | None = None
    client_signature_reference: str = Field(default="", max_length=500)
    client_signature_digest: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    form_schema_version: str = Field(default="1", min_length=1, max_length=50)

    @field_validator("birth_date")
    @classmethod
    def _birth_date_not_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("Birth date cannot be in the future.")
        return value


class CifUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_updated_at: AwareDatetime
    draft: CifDraftBody


class CifVerifyBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expected_updated_at: AwareDatetime
    review_note: str = Field(min_length=1, max_length=1000)


class CifActivateBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expected_source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_note: str = Field(min_length=1, max_length=1000)


class CifReverificationBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: Literal[
        "material_identity_change",
        "address_change",
        "contact_change",
        "document_expiry",
        "discrepancy",
        "suspicious_activity",
        "approved_risk_event",
    ]
    severity: Literal["standard", "high"] = "standard"
    note: str = Field(min_length=1, max_length=1000)


def cif_repository_dependency() -> PostgresCifRepository:
    return PostgresCifRepository()


def _draft_data(body: CifDraftBody) -> CifDraftData:
    return CifDraftData(
        legal_full_name=body.legal_full_name,
        birth_date=body.birth_date,
        place_of_birth=body.place_of_birth,
        nationality=body.nationality,
        civil_status=body.civil_status,
        phone_number=body.phone_number,
        email=body.email,
        present_address=body.present_address.model_dump(exclude_none=True),
        permanent_address=body.permanent_address.model_dump(exclude_none=True),
        same_as_present_address=body.same_as_present_address,
        livelihood_profile=body.livelihood_profile.model_dump(exclude_none=True),
        privacy_notice_version=body.privacy_notice_version,
        privacy_acknowledged_at=(
            datetime.fromisoformat(body.privacy_acknowledged_at.isoformat())
            if body.privacy_acknowledged_at is not None
            else None
        ),
        client_signature_reference=body.client_signature_reference,
        client_signature_digest=body.client_signature_digest,
        form_schema_version=body.form_schema_version,
    )


def _client_payload(record: CifClientSummary) -> dict[str, object]:
    return {
        "client_id": str(record.client_id),
        "client_code": record.client_code,
        "client_name": record.client_name,
        "area": record.area,
        "client_status": record.client_status,
        "active_cif_id": str(record.active_cif_id) if record.active_cif_id else None,
        "active_cif_number": record.active_cif_number,
        "active_cif_status": record.active_cif_status,
        "active_cif_expires_at": (
            record.active_cif_expires_at.isoformat()
            if record.active_cif_expires_at
            else None
        ),
        "is_eligible_for_new_credit": record.is_eligible_for_new_credit,
    }


def _record_payload(record: ClientInformationFormRecord) -> dict[str, object]:
    return {
        "cif_id": str(record.cif_id),
        "cif_number": record.cif_number,
        "client_id": str(record.client_id),
        "client_code": record.client_code,
        "client_name": record.client_name,
        "form_version": record.form_version,
        "lifecycle_state": record.lifecycle_state,
        "public_status": record.public_status,
        "effective_at": record.effective_at.isoformat() if record.effective_at else None,
        "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        "supersedes_cif_id": (
            str(record.supersedes_cif_id) if record.supersedes_cif_id else None
        ),
        "legal_full_name": record.legal_full_name,
        "birth_date": record.birth_date.isoformat() if record.birth_date else None,
        "place_of_birth": record.place_of_birth,
        "nationality": record.nationality,
        "civil_status": record.civil_status,
        "phone_number": record.phone_number,
        "email": record.email,
        "present_address": record.present_address,
        "permanent_address": record.permanent_address,
        "same_as_present_address": record.same_as_present_address,
        "livelihood_profile": record.livelihood_profile,
        "privacy_notice_version": record.privacy_notice_version,
        "privacy_acknowledged_at": (
            record.privacy_acknowledged_at.isoformat()
            if record.privacy_acknowledged_at
            else None
        ),
        "has_client_signature": record.has_client_signature,
        "prepared_by_user_id": str(record.prepared_by_user_id),
        "verified_by_user_id": (
            str(record.verified_by_user_id) if record.verified_by_user_id else None
        ),
        "verified_at": record.verified_at.isoformat() if record.verified_at else None,
        "approved_by_user_id": (
            str(record.approved_by_user_id) if record.approved_by_user_id else None
        ),
        "approved_at": record.approved_at.isoformat() if record.approved_at else None,
        "form_schema_version": record.form_schema_version,
        "source_digest": record.source_digest,
        "has_open_reverification": record.has_open_reverification,
        "is_eligible_for_new_credit": record.is_eligible_for_new_credit,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _requirement_payload(record: CifReverificationRecord) -> dict[str, object]:
    return {
        "requirement_id": str(record.requirement_id),
        "client_id": str(record.client_id),
        "source_cif_id": str(record.source_cif_id) if record.source_cif_id else None,
        "reason": record.reason,
        "severity": record.severity,
        "status": record.status,
        "note": record.note,
        "opened_by_user_id": str(record.opened_by_user_id),
        "opened_at": record.opened_at.isoformat(),
        "resolved_by_user_id": (
            str(record.resolved_by_user_id) if record.resolved_by_user_id else None
        ),
        "resolved_at": record.resolved_at.isoformat() if record.resolved_at else None,
        "resolution_cif_id": (
            str(record.resolution_cif_id) if record.resolution_cif_id else None
        ),
        "resolution_note": record.resolution_note,
    }


def _raise_cif_error(error: CifError) -> None:
    if isinstance(error, CifNotFound):
        status_code = 404
    elif isinstance(error, CifInvalid):
        status_code = 422
    elif isinstance(error, CifConflict):
        status_code = 409
    else:
        status_code = 409
    raise HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    ) from error


def _authenticated(
    *,
    authorization: str | None,
    x_device_id: str | None,
    permission: str,
    permission_error: str,
    auth: SupabaseAuthClient,
    accounts: PostgresAccountRepository,
) -> AccountContext:
    return authenticated_device_context(
        authorization=authorization,
        device_identifier=x_device_id,
        auth=auth,
        accounts=accounts,
        permission=permission,
        permission_error=permission_error,
    )


def _require_office(
    *,
    authorization: str | None,
    x_device_id: str | None,
    permission: str,
    auth: SupabaseAuthClient,
    accounts: PostgresAccountRepository,
) -> AccountContext:
    actor = _authenticated(
        authorization=authorization,
        x_device_id=x_device_id,
        permission=permission,
        permission_error="CIF permission is required.",
        auth=auth,
        accounts=accounts,
    )
    if not ({"employee", "management"} & set(actor.roles)):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "office_role_required",
                "message": "Only Office Staff or Management may administer CIF records.",
            },
        )
    return actor


def _require_management(
    *,
    authorization: str | None,
    x_device_id: str | None,
    permission: str,
    auth: SupabaseAuthClient,
    accounts: PostgresAccountRepository,
) -> AccountContext:
    actor = _authenticated(
        authorization=authorization,
        x_device_id=x_device_id,
        permission=permission,
        permission_error="Management CIF permission is required.",
        auth=auth,
        accounts=accounts,
    )
    if "management" not in actor.roles:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "management_role_required",
                "message": "Only Management may verify, activate, or require CIF re-verification.",
            },
        )
    return actor


def create_cif_router() -> APIRouter:
    router = APIRouter(tags=["client information forms"])

    @router.get("/api/v1/management/cif-clients")
    def search_cif_clients(
        q: str = Query(default="", max_length=200),
        limit: int = Query(default=50, ge=1, le=100),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresCifRepository = Depends(cif_repository_dependency),
    ) -> dict[str, object]:
        _require_office(
            authorization=authorization,
            x_device_id=x_device_id,
            permission="cif.view",
            auth=auth,
            accounts=accounts,
        )
        try:
            records = repository.search_clients(query=q, limit=limit)
        except CifError as error:
            _raise_cif_error(error)
        return {"success": True, "data": [_client_payload(item) for item in records]}

    @router.get("/api/v1/management/clients/{client_id}/cifs")
    def list_client_cifs(
        client_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresCifRepository = Depends(cif_repository_dependency),
    ) -> dict[str, object]:
        _require_office(
            authorization=authorization,
            x_device_id=x_device_id,
            permission="cif.view",
            auth=auth,
            accounts=accounts,
        )
        try:
            forms = repository.list_for_client(client_id=client_id)
            reverification = repository.list_reverification_for_client(
                client_id=client_id
            )
        except CifError as error:
            _raise_cif_error(error)
        return {
            "success": True,
            "data": {
                "client_id": str(client_id),
                "forms": [_record_payload(item) for item in forms],
                "reverification": [
                    _requirement_payload(item) for item in reverification
                ],
            },
        }

    @router.post("/api/v1/management/clients/{client_id}/cifs")
    def create_cif_draft(
        client_id: UUID,
        body: CifDraftBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresCifRepository = Depends(cif_repository_dependency),
    ) -> dict[str, object]:
        actor = _require_office(
            authorization=authorization,
            x_device_id=x_device_id,
            permission="cif.prepare",
            auth=auth,
            accounts=accounts,
        )
        try:
            record = repository.create_draft(
                actor_user_id=actor.user_id,
                client_id=client_id,
                draft=_draft_data(body),
            )
        except CifError as error:
            _raise_cif_error(error)
        return {"success": True, "data": _record_payload(record)}

    @router.get("/api/v1/management/cifs/{cif_id}")
    def get_cif(
        cif_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresCifRepository = Depends(cif_repository_dependency),
    ) -> dict[str, object]:
        _require_office(
            authorization=authorization,
            x_device_id=x_device_id,
            permission="cif.view",
            auth=auth,
            accounts=accounts,
        )
        try:
            record = repository.get(cif_id=cif_id)
        except CifError as error:
            _raise_cif_error(error)
        return {"success": True, "data": _record_payload(record)}

    @router.patch("/api/v1/management/cifs/{cif_id}")
    def update_cif_draft(
        cif_id: UUID,
        body: CifUpdateBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresCifRepository = Depends(cif_repository_dependency),
    ) -> dict[str, object]:
        actor = _require_office(
            authorization=authorization,
            x_device_id=x_device_id,
            permission="cif.prepare",
            auth=auth,
            accounts=accounts,
        )
        try:
            record = repository.update_draft(
                actor_user_id=actor.user_id,
                cif_id=cif_id,
                expected_updated_at=body.expected_updated_at,
                draft=_draft_data(body.draft),
            )
        except CifError as error:
            _raise_cif_error(error)
        return {"success": True, "data": _record_payload(record)}

    @router.post("/api/v1/management/cifs/{cif_id}/verify")
    def verify_cif(
        cif_id: UUID,
        body: CifVerifyBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresCifRepository = Depends(cif_repository_dependency),
    ) -> dict[str, object]:
        actor = _require_management(
            authorization=authorization,
            x_device_id=x_device_id,
            permission="cif.verify",
            auth=auth,
            accounts=accounts,
        )
        try:
            record = repository.verify(
                actor_user_id=actor.user_id,
                cif_id=cif_id,
                expected_updated_at=body.expected_updated_at,
                review_note=body.review_note,
            )
        except CifError as error:
            _raise_cif_error(error)
        return {"success": True, "data": _record_payload(record)}

    @router.post("/api/v1/management/cifs/{cif_id}/activate")
    def activate_cif(
        cif_id: UUID,
        body: CifActivateBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresCifRepository = Depends(cif_repository_dependency),
    ) -> dict[str, object]:
        actor = _require_management(
            authorization=authorization,
            x_device_id=x_device_id,
            permission="cif.approve",
            auth=auth,
            accounts=accounts,
        )
        try:
            record = repository.activate(
                actor_user_id=actor.user_id,
                cif_id=cif_id,
                expected_source_digest=body.expected_source_digest,
                review_note=body.review_note,
            )
        except CifError as error:
            _raise_cif_error(error)
        return {"success": True, "data": _record_payload(record)}

    @router.post("/api/v1/management/clients/{client_id}/cif-reverification")
    def open_cif_reverification(
        client_id: UUID,
        body: CifReverificationBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresCifRepository = Depends(cif_repository_dependency),
    ) -> dict[str, object]:
        actor = _require_management(
            authorization=authorization,
            x_device_id=x_device_id,
            permission="cif.reverification.manage",
            auth=auth,
            accounts=accounts,
        )
        try:
            record = repository.open_reverification(
                actor_user_id=actor.user_id,
                client_id=client_id,
                reason=body.reason,
                severity=body.severity,
                note=body.note,
            )
        except CifError as error:
            _raise_cif_error(error)
        return {"success": True, "data": _requirement_payload(record)}

    return router

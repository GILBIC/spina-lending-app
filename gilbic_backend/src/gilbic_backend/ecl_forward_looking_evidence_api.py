from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .ecl_forward_looking_evidence_repository import (
    EclForwardLookingEvidence,
    EclForwardLookingEvidenceBlocked,
    EclForwardLookingEvidenceError,
    EclForwardLookingEvidenceNotFound,
    PostgresEclForwardLookingEvidenceRepository,
)
from .request_auth import authenticated_device_context


MANAGE_PERMISSION = "accounting.ecl.forward_looking_evidence.manage"


class StrictForwardLookingEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RecordForwardLookingEvidenceRequest(StrictForwardLookingEvidenceRequest):
    evidence_key: str = Field(min_length=1, max_length=120)
    source_name: str = Field(min_length=1, max_length=240)
    source_reference: str = Field(min_length=1, max_length=1000)
    observation_period_start: date | None = None
    observation_period_end: date | None = None
    forecast_period_start: date
    forecast_period_end: date
    retrieved_at: datetime
    effective_date: date
    management_interpretation: str = Field(min_length=20, max_length=4000)
    supersedes_evidence_id: UUID | None = None

    @field_validator(
        "evidence_key", "source_name", "source_reference", "management_interpretation"
    )
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.split())

    @model_validator(mode="after")
    def validate_periods(self):
        if self.forecast_period_end < self.forecast_period_start:
            raise ValueError("Forecast period end cannot be before forecast period start.")
        if (
            self.observation_period_start is not None
            and self.observation_period_end is not None
            and self.observation_period_end < self.observation_period_start
        ):
            raise ValueError("Observation period end cannot be before observation period start.")
        return self


class RevokeForwardLookingEvidenceRequest(StrictForwardLookingEvidenceRequest):
    reason: str = Field(min_length=3, max_length=1200)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return " ".join(value.split())


def ecl_forward_looking_evidence_repository_dependency() -> (
    PostgresEclForwardLookingEvidenceRepository
):
    return PostgresEclForwardLookingEvidenceRepository()


def _payload(evidence: EclForwardLookingEvidence) -> dict[str, object]:
    return {
        "id": str(evidence.id),
        "evidence_key": evidence.evidence_key,
        "version": evidence.version,
        "source_name": evidence.source_name,
        "source_reference": evidence.source_reference,
        "observation_period_start": (
            evidence.observation_period_start.isoformat()
            if evidence.observation_period_start
            else None
        ),
        "observation_period_end": (
            evidence.observation_period_end.isoformat()
            if evidence.observation_period_end
            else None
        ),
        "forecast_period_start": evidence.forecast_period_start.isoformat(),
        "forecast_period_end": evidence.forecast_period_end.isoformat(),
        "retrieved_at": evidence.retrieved_at.isoformat(),
        "effective_date": evidence.effective_date.isoformat(),
        "management_interpretation": evidence.management_interpretation,
        "approved_by_user_id": str(evidence.approved_by_user_id),
        "approved_at": evidence.approved_at.isoformat(),
        "supersedes_evidence_id": (
            str(evidence.supersedes_evidence_id)
            if evidence.supersedes_evidence_id
            else None
        ),
        "evidence_status": evidence.evidence_status,
        "ready_for_new_measurement": evidence.ready_for_new_measurement,
        "revocation_id": str(evidence.revocation_id) if evidence.revocation_id else None,
        "revocation_reason": evidence.revocation_reason,
        "revoked_by_user_id": (
            str(evidence.revoked_by_user_id) if evidence.revoked_by_user_id else None
        ),
        "revoked_at": evidence.revoked_at.isoformat() if evidence.revoked_at else None,
        "scenario_probability_defaulted": False,
        "multiplier_defaulted": False,
        "management_overlay_defaulted": False,
        "ecl_calculation_enabled": False,
        "account_1190_posting_enabled": False,
        "automatic_source_posting": False,
    }


def _exception(error: EclForwardLookingEvidenceError) -> HTTPException:
    if isinstance(error, EclForwardLookingEvidenceNotFound):
        status_code = 404
    elif isinstance(error, EclForwardLookingEvidenceBlocked):
        status_code = 409
    else:
        status_code = 500
    return HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    )


def _require_management(actor) -> None:
    if "management" not in actor.roles:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "management_role_required",
                "message": "Management access is required for forward-looking ECL evidence.",
            },
        )


def _require_manage_permission(actor) -> None:
    _require_management(actor)
    if MANAGE_PERMISSION not in actor.permissions:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "forward_looking_ecl_evidence_permission_required",
                "message": "Forward-looking ECL evidence Management permission is required.",
            },
        )


def create_ecl_forward_looking_evidence_router() -> APIRouter:
    router = APIRouter(tags=["management financial accounting"])

    @router.get(
        "/api/v1/management/financial-accounting/ecl-forward-looking-evidence"
    )
    @router.get(
        "/api/mobile/v1/management/financial-accounting/ecl-forward-looking-evidence",
        include_in_schema=False,
    )
    def list_forward_looking_evidence(
        status: Literal[
            "all", "current", "stale", "superseded", "revoked", "not_yet_effective", "ready"
        ] = Query(default="all"),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        evidence: PostgresEclForwardLookingEvidenceRepository = Depends(
            ecl_forward_looking_evidence_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_management(actor)
        items = evidence.list_evidence(status=status, limit=limit, offset=offset)
        return {
            "success": True,
            "data": {
                "items": [_payload(item) for item in items],
                "filter": status,
                "limit": limit,
                "offset": offset,
                "manage_permission": MANAGE_PERMISSION in actor.permissions,
                "notice": (
                    "Evidence is immutable/versioned. Later versions affect future readiness only; "
                    "no ECL amount, scenario probability, multiplier, overlay, account 1190 posting, "
                    "or automatic source posting is created here."
                ),
            },
        }

    @router.post(
        "/api/v1/management/financial-accounting/ecl-forward-looking-evidence"
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/ecl-forward-looking-evidence",
        include_in_schema=False,
    )
    def record_forward_looking_evidence(
        request: RecordForwardLookingEvidenceRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        evidence: PostgresEclForwardLookingEvidenceRepository = Depends(
            ecl_forward_looking_evidence_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_manage_permission(actor)
        try:
            item = evidence.record_evidence(
                evidence_key=request.evidence_key,
                source_name=request.source_name,
                source_reference=request.source_reference,
                observation_period_start=request.observation_period_start,
                observation_period_end=request.observation_period_end,
                forecast_period_start=request.forecast_period_start,
                forecast_period_end=request.forecast_period_end,
                retrieved_at=request.retrieved_at,
                effective_date=request.effective_date,
                management_interpretation=request.management_interpretation,
                actor_user_id=actor.user_id,
                supersedes_evidence_id=request.supersedes_evidence_id,
            )
        except EclForwardLookingEvidenceError as error:
            raise _exception(error) from error
        return {"success": True, "data": _payload(item)}

    @router.post(
        "/api/v1/management/financial-accounting/ecl-forward-looking-evidence/{evidence_id}/revoke"
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/ecl-forward-looking-evidence/{evidence_id}/revoke",
        include_in_schema=False,
    )
    def revoke_forward_looking_evidence(
        evidence_id: UUID,
        request: RevokeForwardLookingEvidenceRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        evidence: PostgresEclForwardLookingEvidenceRepository = Depends(
            ecl_forward_looking_evidence_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_manage_permission(actor)
        try:
            item = evidence.revoke_evidence(
                evidence_id=evidence_id,
                reason=request.reason,
                actor_user_id=actor.user_id,
            )
        except EclForwardLookingEvidenceError as error:
            raise _exception(error) from error
        return {"success": True, "data": _payload(item)}

    return router

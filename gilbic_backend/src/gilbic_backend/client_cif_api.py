from __future__ import annotations

from datetime import datetime
from typing import NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import AccountContext, PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .client_cif_repository import (
    ClientCifConflict,
    ClientCifLivenessStatus,
    ClientCifVersion,
    PostgresClientCifRepository,
)
from .request_auth import authenticated_device_context


_CIF_PERMISSION = "client_onboarding.requirement.review"


class BaselineLiveFaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_reference: str = Field(min_length=1, max_length=500)
    liveness_status: ClientCifLivenessStatus


def client_cif_repository_dependency() -> PostgresClientCifRepository:
    return PostgresClientCifRepository()


def _office_cif_actor(
    *,
    authorization: str | None,
    x_device_id: str | None,
    auth: SupabaseAuthClient,
    accounts: PostgresAccountRepository,
) -> AccountContext:
    actor = authenticated_device_context(
        authorization=authorization,
        device_identifier=x_device_id,
        auth=auth,
        accounts=accounts,
        permission=_CIF_PERMISSION,
        permission_error="Onboarding requirement review permission is required.",
    )
    if not any(role in actor.roles for role in ("employee", "management")):
        raise HTTPException(
            status_code=403,
            detail="Employee or Management role is required for CIF work.",
        )
    return actor


def _summary_payload(record: ClientCifVersion) -> dict[str, object]:
    return {
        "client_id": str(record.client_id),
        "version_number": record.version_number,
        "status": record.status,
        "liveness_status": record.baseline_liveness_status,
    }


def _iso_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _activation_payload(record: ClientCifVersion) -> dict[str, object]:
    payload = _summary_payload(record)
    payload.update(
        {
            "activated_at": _iso_timestamp(record.activated_at),
            "expires_at": _iso_timestamp(record.expires_at),
            "review_due_at": _iso_timestamp(record.review_due_at),
        }
    )
    return payload


def _raise_cif_conflict(error: ClientCifConflict) -> NoReturn:
    raise HTTPException(status_code=409, detail=str(error)) from error


def create_client_cif_router() -> APIRouter:
    router = APIRouter(tags=["client-cif"])

    @router.post(
        "/api/v1/management/clients/{client_id}/cif/draft",
        status_code=status.HTTP_201_CREATED,
    )
    def begin_cif_draft(
        client_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        cif: PostgresClientCifRepository = Depends(client_cif_repository_dependency),
    ) -> dict[str, object]:
        actor = _office_cif_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = cif.begin_draft(actor_user_id=actor.user_id, client_id=client_id)
        except ClientCifConflict as error:
            _raise_cif_conflict(error)
        return _summary_payload(record)

    @router.patch(
        "/api/v1/management/clients/{client_id}/cif/baseline-live-face"
    )
    def record_baseline_live_face(
        client_id: UUID,
        body: BaselineLiveFaceRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        cif: PostgresClientCifRepository = Depends(client_cif_repository_dependency),
    ) -> dict[str, object]:
        _office_cif_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = cif.record_baseline_live_face(
                client_id=client_id,
                evidence_reference=body.evidence_reference,
                liveness_status=body.liveness_status,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except ClientCifConflict as error:
            _raise_cif_conflict(error)
        return _summary_payload(record)

    @router.post("/api/v1/management/clients/{client_id}/cif/activate")
    def activate_cif(
        client_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        cif: PostgresClientCifRepository = Depends(client_cif_repository_dependency),
    ) -> dict[str, object]:
        actor = _office_cif_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        if "management" not in actor.roles:
            raise HTTPException(
                status_code=403,
                detail="Management role is required to activate a CIF.",
            )
        try:
            record = cif.activate_current(
                actor_user_id=actor.user_id,
                client_id=client_id,
            )
        except ClientCifConflict as error:
            _raise_cif_conflict(error)
        return _activation_payload(record)

    return router

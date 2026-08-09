from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .contract_collection_activation_repository import (
    ContractCollectionActivationConflict,
    ContractCollectionActivationError,
    ContractCollectionActivationNotFound,
    ContractCollectionActivationPreview,
    PostgresContractCollectionActivationRepository,
)
from .request_auth import authenticated_device_context


class StrictActivationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ContractCollectionActivationRequest(StrictActivationRequest):
    activation_note: str = Field(min_length=1, max_length=1000)
    confirm_action: bool = False

    @field_validator("activation_note")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Activation note cannot be blank.")
        return normalized


def contract_collection_activation_repository_dependency() -> (
    PostgresContractCollectionActivationRepository
):
    return PostgresContractCollectionActivationRepository()


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _preview_payload(preview: ContractCollectionActivationPreview) -> dict[str, object]:
    return {
        "loan_id": str(preview.loan_id),
        "loan_number": preview.loan_number,
        "client_name": preview.client_name,
        "loan_type_name": preview.loan_type_name,
        "loan_status": preview.loan_status,
        "remaining_balance": _decimal(preview.remaining_balance),
        "mobile_collections_enabled": preview.mobile_collections_enabled,
        "mobile_balance_mode": preview.mobile_balance_mode,
        "schedule_id": str(preview.schedule_id) if preview.schedule_id else None,
        "schedule_version": preview.schedule_version,
        "payment_frequency": preview.payment_frequency,
        "contract_reference": preview.contract_reference,
        "dpd_data_status": preview.dpd_data_status,
        "contractual_schedule_total": _decimal(preview.contractual_schedule_total),
        "allocated_schedule_total": _decimal(preview.allocated_schedule_total),
        "unpaid_contractual_amount": _decimal(preview.unpaid_contractual_amount),
        "schedule_verified": preview.schedule_verified,
        "balance_reconciled": preview.balance_reconciled,
        "accounting_safe": preview.accounting_safe,
        "activation_event_id": preview.activation_event_id,
        "activation_action": preview.activation_action,
        "activation_schedule_id": (
            str(preview.activation_schedule_id)
            if preview.activation_schedule_id
            else None
        ),
        "activation_note": preview.activation_note,
        "activated_by_user_id": (
            str(preview.activated_by_user_id)
            if preview.activated_by_user_id
            else None
        ),
        "activation_acted_at": (
            preview.activation_acted_at.isoformat()
            if preview.activation_acted_at
            else None
        ),
        "is_active": preview.is_active,
        "active_for_current_schedule": preview.active_for_current_schedule,
        "can_activate": preview.can_activate,
        "can_deactivate": preview.can_deactivate,
        "blockers": list(preview.blockers),
    }


def _activation_exception(error: ContractCollectionActivationError) -> HTTPException:
    if isinstance(error, ContractCollectionActivationNotFound):
        status_code = 404
    elif isinstance(error, ContractCollectionActivationConflict):
        status_code = 409
    else:
        status_code = 500
    return HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    )


def create_contract_collection_activation_router() -> APIRouter:
    router = APIRouter(tags=["management contract collection activation"])

    @router.get(
        "/api/v1/management/financial-accounting/contract-collection-activation"
    )
    @router.get(
        "/api/mobile/v1/management/financial-accounting/contract-collection-activation",
        include_in_schema=False,
    )
    def list_activation_readiness(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        activations: PostgresContractCollectionActivationRepository = Depends(
            contract_collection_activation_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        if "management" not in actor.roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "management_role_required",
                    "message": "Management access is required for contract activation review.",
                },
            )
        previews = activations.list_previews()
        return {
            "success": True,
            "data": {
                "permission": (
                    "lending.contract_collection.activate" in actor.permissions
                ),
                "loans": [_preview_payload(item) for item in previews],
                "active_count": sum(1 for item in previews if item.is_active),
                "ready_to_activate_count": sum(
                    1 for item in previews if item.can_activate
                ),
                "notice": (
                    "Readiness only. No loan is activated automatically. Activation is "
                    "one loan at a time and does not create Default/ECL labels or journals."
                ),
            },
        }

    @router.get(
        "/api/v1/management/financial-accounting/contract-collection-activation/{loan_id}"
    )
    @router.get(
        "/api/mobile/v1/management/financial-accounting/contract-collection-activation/{loan_id}",
        include_in_schema=False,
    )
    def preview_activation(
        loan_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        activations: PostgresContractCollectionActivationRepository = Depends(
            contract_collection_activation_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        if "management" not in actor.roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "management_role_required",
                    "message": "Management access is required for contract activation preview.",
                },
            )
        try:
            preview = activations.get_preview(loan_id=loan_id)
        except ContractCollectionActivationError as error:
            raise _activation_exception(error) from error
        return {
            "success": True,
            "data": {
                **_preview_payload(preview),
                "permission": (
                    "lending.contract_collection.activate" in actor.permissions
                ),
                "notice": (
                    "Preview only. No collection behavior, balance, Default/ECL state, "
                    "loan status, or General Ledger entry was changed."
                ),
            },
        }

    @router.post(
        "/api/v1/management/financial-accounting/contract-collection-activation/{loan_id}/activate"
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/contract-collection-activation/{loan_id}/activate",
        include_in_schema=False,
    )
    def activate_contract_collection(
        loan_id: UUID,
        body: ContractCollectionActivationRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        activations: PostgresContractCollectionActivationRepository = Depends(
            contract_collection_activation_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="lending.contract_collection.activate",
            permission_error="Per-loan contract collection activation permission is required.",
        )
        if not body.confirm_action:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "contract_collection_activation_confirmation_required",
                    "message": "Explicit activation confirmation is required.",
                },
            )
        try:
            preview = activations.activate(
                loan_id=loan_id,
                acted_by_user_id=actor.user_id,
                activation_note=body.activation_note,
            )
        except ContractCollectionActivationError as error:
            raise _activation_exception(error) from error
        return {
            "success": True,
            "data": _preview_payload(preview),
            "notice": (
                "Contractual mobile allocation is activated only for this loan and its "
                "current verified schedule. Other loans are unchanged."
            ),
        }

    @router.post(
        "/api/v1/management/financial-accounting/contract-collection-activation/{loan_id}/deactivate"
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/contract-collection-activation/{loan_id}/deactivate",
        include_in_schema=False,
    )
    def deactivate_contract_collection(
        loan_id: UUID,
        body: ContractCollectionActivationRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        activations: PostgresContractCollectionActivationRepository = Depends(
            contract_collection_activation_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="lending.contract_collection.activate",
            permission_error="Per-loan contract collection activation permission is required.",
        )
        if not body.confirm_action:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "contract_collection_deactivation_confirmation_required",
                    "message": "Explicit deactivation confirmation is required.",
                },
            )
        try:
            preview = activations.deactivate(
                loan_id=loan_id,
                acted_by_user_id=actor.user_id,
                activation_note=body.activation_note,
            )
        except ContractCollectionActivationError as error:
            raise _activation_exception(error) from error
        return {
            "success": True,
            "data": _preview_payload(preview),
            "notice": (
                "Contractual mobile allocation is deactivated for this loan. The immutable "
                "activation/deactivation history is preserved."
            ),
        }

    return router

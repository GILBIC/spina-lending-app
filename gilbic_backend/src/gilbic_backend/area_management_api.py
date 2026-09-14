from __future__ import annotations

from datetime import date
from typing import NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import AccountContext, PostgresAccountRepository
from .area_management_repository import PostgresAreaManagementRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .request_auth import authenticated_device_context


class StrictAreaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CreateAreaRequest(StrictAreaRequest):
    parent_area_id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)


class RenameAreaRequest(StrictAreaRequest):
    name: str = Field(min_length=1, max_length=200)


class MoveAreaRequest(StrictAreaRequest):
    new_parent_area_id: UUID | None = None


class ReorderAreasRequest(StrictAreaRequest):
    parent_area_id: UUID | None = None
    ordered_area_ids: list[UUID] = Field(min_length=1, max_length=500)


class CollectorAssignmentRequest(StrictAreaRequest):
    collector_user_id: UUID


class ClientAreaTransferRequest(StrictAreaRequest):
    target_area_id: UUID


def area_management_repository_dependency() -> PostgresAreaManagementRepository:
    return PostgresAreaManagementRepository()


def area_staff_context(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    auth: SupabaseAuthClient = Depends(auth_client_dependency),
    accounts: PostgresAccountRepository = Depends(account_repository_dependency),
) -> AccountContext:
    actor = authenticated_device_context(
        authorization=authorization,
        device_identifier=x_device_id,
        auth=auth,
        accounts=accounts,
    )
    if not ({"employee", "management"} & set(actor.roles)):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "area_staff_role_required",
                "message": "Employee or Management access is required for Area Management.",
            },
        )
    return actor


def _require_permission(
    actor: AccountContext,
    permission: str,
    *,
    management_only: bool = False,
) -> None:
    if management_only and "management" not in actor.roles:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "management_role_required",
                "message": "Management access is required for this Area action.",
            },
        )
    if permission not in actor.permissions:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "area_permission_required",
                "message": "Your account does not have permission for this Area action.",
            },
        )


def _raise_area_conflict(error: ValueError) -> NoReturn:
    raise HTTPException(
        status_code=409,
        detail={
            "code": "area_conflict",
            "message": "The Area action conflicts with the current authoritative state.",
        },
    ) from error


def _uuid(value: UUID | None) -> str | None:
    return str(value) if value is not None else None


def _collector_payload(record) -> dict[str, object]:
    return {
        "user_id": str(record.user_id),
        "username": record.username,
        "full_name": record.full_name,
    }


def _tree_node_payload(record) -> dict[str, object]:
    return {
        "area_id": str(record.area_uid),
        "parent_area_id": _uuid(record.parent_area_uid),
        "name": record.name,
        "full_path": record.full_path,
        "depth": record.depth,
        "sort_order": record.sort_order,
        "is_active": record.is_active,
        "is_legacy_unmapped": record.is_legacy_unmapped,
        "explicit_collector": (
            _collector_payload(record.explicit_collector)
            if record.explicit_collector is not None
            else None
        ),
        "effective_collector": (
            _collector_payload(record.effective_collector)
            if record.effective_collector is not None
            else None
        ),
        "effective_collector_source_area_id": _uuid(
            record.effective_collector_source_area_uid
        ),
        "direct_client_count": record.direct_client_count,
        "subtree_client_count": record.subtree_client_count,
        "child_count": record.child_count,
    }


def _client_payload(record) -> dict[str, object]:
    return {
        "client_id": str(record.client_id),
        "client_code": record.client_code,
        "full_name": record.full_name,
        "area_id": _uuid(record.area_uid),
        "area_path": record.area_path,
        "effective_collector": (
            _collector_payload(record.effective_collector)
            if record.effective_collector is not None
            else None
        ),
    }


def _move_payload(record) -> dict[str, object]:
    return {
        "area_id": str(record.area_uid),
        "old_parent_area_id": _uuid(record.old_parent_area_uid),
        "new_parent_area_id": _uuid(record.new_parent_area_uid),
        "old_path": record.old_path,
        "new_path": record.new_path,
        "affected_node_count": record.affected_node_count,
    }


def _transfer_payload(record) -> dict[str, object]:
    return {
        "client_id": str(record.client_id),
        "old_area_id": _uuid(record.old_area_uid),
        "old_area_path": record.old_area_path,
        "new_area_id": str(record.new_area_uid),
        "new_area_path": record.new_area_path,
        "old_effective_collector_user_id": _uuid(
            record.old_effective_collector_user_id
        ),
        "new_effective_collector_user_id": str(
            record.new_effective_collector_user_id
        ),
        "effective_date": record.effective_date.isoformat(),
        "timing": record.timing,
    }


def _retirement_payload(record) -> dict[str, object]:
    return {
        "area_id": str(record.area_uid),
        "full_path": record.full_path,
        "is_active": record.is_active,
        "active_direct_client_count": record.active_direct_client_count,
        "active_subtree_client_count": record.active_subtree_client_count,
        "active_collector_assignment_count": record.active_collector_assignment_count,
        "pending_transfer_target_count": record.pending_transfer_target_count,
        "descendant_count": record.descendant_count,
        "active_descendant_count": record.active_descendant_count,
    }


def create_area_management_router() -> APIRouter:
    router = APIRouter(tags=["area management"])

    @router.get("/api/v1/areas")
    def list_areas(
        include_inactive: bool = Query(default=False),
        actor: AccountContext = Depends(area_staff_context),
        repository: PostgresAreaManagementRepository = Depends(
            area_management_repository_dependency
        ),
    ) -> dict[str, object]:
        _require_permission(actor, "area.manage")
        records = repository.list_tree(include_inactive=include_inactive)
        return {
            "success": True,
            "data": {"areas": [_tree_node_payload(record) for record in records]},
        }

    @router.get("/api/v1/areas/collectors")
    def list_area_collectors(
        actor: AccountContext = Depends(area_staff_context),
        repository: PostgresAreaManagementRepository = Depends(
            area_management_repository_dependency
        ),
    ) -> dict[str, object]:
        _require_permission(actor, "area.manage")
        return {
            "success": True,
            "data": {
                "collectors": [
                    _collector_payload(record) for record in repository.list_collectors()
                ]
            },
        }

    @router.get("/api/v1/areas/clients")
    def search_area_clients(
        q: str = Query(min_length=1, max_length=200),
        limit: int = Query(default=20, ge=1, le=100),
        actor: AccountContext = Depends(area_staff_context),
        repository: PostgresAreaManagementRepository = Depends(
            area_management_repository_dependency
        ),
    ) -> dict[str, object]:
        _require_permission(actor, "area.manage")
        records = repository.search_clients(q, limit=limit)
        return {
            "success": True,
            "data": {"clients": [_client_payload(record) for record in records]},
        }

    @router.get("/api/v1/areas/{area_id}/move-preview")
    def preview_area_move(
        area_id: UUID,
        new_parent_area_id: UUID | None = Query(default=None),
        actor: AccountContext = Depends(area_staff_context),
        repository: PostgresAreaManagementRepository = Depends(
            area_management_repository_dependency
        ),
    ) -> dict[str, object]:
        _require_permission(actor, "area.manage")
        try:
            preview = repository.preview_move(
                area_uid=area_id,
                new_parent_area_uid=new_parent_area_id,
            )
        except ValueError as error:
            _raise_area_conflict(error)
        return {"success": True, "data": _move_payload(preview)}

    @router.get("/api/v1/areas/{area_id}/retirement-preview")
    def preview_area_retirement(
        area_id: UUID,
        actor: AccountContext = Depends(area_staff_context),
        repository: PostgresAreaManagementRepository = Depends(
            area_management_repository_dependency
        ),
    ) -> dict[str, object]:
        _require_permission(actor, "area.retire", management_only=True)
        try:
            preview = repository.preview_retirement(area_uid=area_id)
        except ValueError as error:
            _raise_area_conflict(error)
        return {"success": True, "data": _retirement_payload(preview)}

    @router.get("/api/v1/clients/{client_id}/area-transfer-preview")
    def preview_client_area_transfer(
        client_id: UUID,
        target_area_id: UUID = Query(),
        actor: AccountContext = Depends(area_staff_context),
        repository: PostgresAreaManagementRepository = Depends(
            area_management_repository_dependency
        ),
    ) -> dict[str, object]:
        _require_permission(actor, "area.client.assign")
        try:
            preview = repository.preview_client_transfer(
                client_id=client_id,
                target_area_uid=target_area_id,
                as_of_date=date.today(),
            )
        except ValueError as error:
            _raise_area_conflict(error)
        return {"success": True, "data": _transfer_payload(preview)}

    @router.post("/api/v1/areas", status_code=status.HTTP_201_CREATED)
    def create_area(
        request: CreateAreaRequest,
        actor: AccountContext = Depends(area_staff_context),
        repository: PostgresAreaManagementRepository = Depends(
            area_management_repository_dependency
        ),
    ) -> dict[str, object]:
        _require_permission(actor, "area.manage")
        try:
            area_id = repository.create_area(
                actor_user_id=actor.user_id,
                parent_area_uid=request.parent_area_id,
                name=request.name,
            )
        except ValueError as error:
            _raise_area_conflict(error)
        return {"success": True, "data": {"area_id": str(area_id)}}

    @router.patch("/api/v1/areas/{area_id}")
    def rename_area(
        area_id: UUID,
        request: RenameAreaRequest,
        actor: AccountContext = Depends(area_staff_context),
        repository: PostgresAreaManagementRepository = Depends(
            area_management_repository_dependency
        ),
    ) -> dict[str, object]:
        _require_permission(actor, "area.manage")
        try:
            updated = repository.rename_area(
                actor_user_id=actor.user_id,
                area_uid=area_id,
                name=request.name,
            )
        except ValueError as error:
            _raise_area_conflict(error)
        return {"success": True, "data": {"area_id": str(updated)}}

    @router.post("/api/v1/areas/{area_id}/move")
    def move_area(
        area_id: UUID,
        request: MoveAreaRequest,
        actor: AccountContext = Depends(area_staff_context),
        repository: PostgresAreaManagementRepository = Depends(
            area_management_repository_dependency
        ),
    ) -> dict[str, object]:
        _require_permission(actor, "area.manage")
        try:
            moved = repository.move_area(
                actor_user_id=actor.user_id,
                area_uid=area_id,
                new_parent_area_uid=request.new_parent_area_id,
            )
        except ValueError as error:
            _raise_area_conflict(error)
        return {"success": True, "data": _move_payload(moved)}

    @router.post("/api/v1/areas/reorder")
    def reorder_areas(
        request: ReorderAreasRequest,
        actor: AccountContext = Depends(area_staff_context),
        repository: PostgresAreaManagementRepository = Depends(
            area_management_repository_dependency
        ),
    ) -> dict[str, object]:
        _require_permission(actor, "area.manage")
        try:
            ordered = repository.reorder_siblings(
                actor_user_id=actor.user_id,
                parent_area_uid=request.parent_area_id,
                ordered_area_uids=tuple(request.ordered_area_ids),
            )
        except ValueError as error:
            _raise_area_conflict(error)
        return {
            "success": True,
            "data": {"ordered_area_ids": [str(value) for value in ordered]},
        }

    @router.put("/api/v1/areas/{area_id}/collector")
    def assign_area_collector(
        area_id: UUID,
        request: CollectorAssignmentRequest,
        actor: AccountContext = Depends(area_staff_context),
        repository: PostgresAreaManagementRepository = Depends(
            area_management_repository_dependency
        ),
    ) -> dict[str, object]:
        _require_permission(actor, "area.collector.assign")
        try:
            assignment_id = repository.assign_collector(
                actor_user_id=actor.user_id,
                area_uid=area_id,
                collector_user_id=request.collector_user_id,
            )
        except ValueError as error:
            _raise_area_conflict(error)
        return {
            "success": True,
            "data": {"assignment_id": str(assignment_id)},
        }

    @router.delete("/api/v1/areas/{area_id}/collector")
    def remove_area_collector(
        area_id: UUID,
        actor: AccountContext = Depends(area_staff_context),
        repository: PostgresAreaManagementRepository = Depends(
            area_management_repository_dependency
        ),
    ) -> dict[str, object]:
        _require_permission(actor, "area.collector.assign")
        try:
            collector_user_id = repository.remove_collector_assignment(
                actor_user_id=actor.user_id,
                area_uid=area_id,
            )
        except ValueError as error:
            _raise_area_conflict(error)
        return {
            "success": True,
            "data": {"collector_user_id": str(collector_user_id)},
        }

    @router.post("/api/v1/clients/{client_id}/area-transfer")
    def transfer_client_area(
        client_id: UUID,
        request: ClientAreaTransferRequest,
        actor: AccountContext = Depends(area_staff_context),
        repository: PostgresAreaManagementRepository = Depends(
            area_management_repository_dependency
        ),
    ) -> dict[str, object]:
        _require_permission(actor, "area.client.assign")
        try:
            transfer = repository.schedule_client_transfer(
                actor_user_id=actor.user_id,
                client_id=client_id,
                target_area_uid=request.target_area_id,
                as_of_date=date.today(),
            )
        except ValueError as error:
            _raise_area_conflict(error)
        return {"success": True, "data": _transfer_payload(transfer)}

    @router.post("/api/v1/areas/{area_id}/retire")
    def retire_area(
        area_id: UUID,
        actor: AccountContext = Depends(area_staff_context),
        repository: PostgresAreaManagementRepository = Depends(
            area_management_repository_dependency
        ),
    ) -> dict[str, object]:
        _require_permission(actor, "area.retire", management_only=True)
        try:
            retired = repository.retire_area(
                actor_user_id=actor.user_id,
                area_uid=area_id,
            )
        except ValueError as error:
            _raise_area_conflict(error)
        return {"success": True, "data": {"area_id": str(retired)}}

    @router.post("/api/v1/areas/{area_id}/reactivate")
    def reactivate_area(
        area_id: UUID,
        actor: AccountContext = Depends(area_staff_context),
        repository: PostgresAreaManagementRepository = Depends(
            area_management_repository_dependency
        ),
    ) -> dict[str, object]:
        _require_permission(actor, "area.retire", management_only=True)
        try:
            reactivated = repository.reactivate_area(
                actor_user_id=actor.user_id,
                area_uid=area_id,
            )
        except ValueError as error:
            _raise_area_conflict(error)
        return {"success": True, "data": {"area_id": str(reactivated)}}

    return router

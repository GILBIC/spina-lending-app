from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Header, Query
from psycopg.rows import dict_row

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .database import open_connection
from .renewal_workflow_api import _payload, _renewal_row
from .request_auth import authenticated_device_context


def create_renewal_workflow_query_router() -> APIRouter:
    router = APIRouter(tags=["renewal workflow queries"])

    @router.get("/api/v1/client/renewal-workflow")
    @router.get(
        "/api/mobile/v1/client/renewal-workflow",
        include_in_schema=False,
    )
    def client_workflow(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        if "client" not in actor.roles:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=403,
                detail={
                    "code": "client_role_required",
                    "message": "Only a linked client account can view its renewal workflow.",
                },
            )
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select request.id
                    from lending.client_renewal_requests request
                    join lending.clients client on client.id = request.client_id
                    where client.user_id = %s
                      and request.status in ('pending', 'approved', 'rejected')
                    order by request.submitted_at desc, request.id desc
                    limit 100
                    """,
                    (actor.user_id,),
                )
                ids = [row["id"] for row in cursor.fetchall()]
                items = [
                    _payload(cursor, _renewal_row(cursor, request_id=request_id))
                    for request_id in ids
                ]
        return {"success": True, "data": {"requests": items}}

    @router.get("/api/v1/management/renewal-workflow")
    @router.get(
        "/api/mobile/v1/management/renewal-workflow",
        include_in_schema=False,
    )
    def management_workflow(
        workflow_status: Literal["pending", "approved", "rejected"] = Query(
            default="pending",
            alias="status",
        ),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
    ) -> dict[str, object]:
        authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="renewal.manage",
            permission_error="Management renewal permission is required.",
        )
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select id
                    from lending.client_renewal_requests
                    where status = %s
                    order by submitted_at desc, id desc
                    limit 200
                    """,
                    (workflow_status,),
                )
                ids = [row["id"] for row in cursor.fetchall()]
                items = [
                    _payload(cursor, _renewal_row(cursor, request_id=request_id))
                    for request_id in ids
                ]
        return {"success": True, "data": {"requests": items}}

    @router.get("/api/v1/renewal-signatures/mine")
    @router.get(
        "/api/mobile/v1/renewal-signatures/mine",
        include_in_schema=False,
    )
    def my_signatures(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select signer.id as signer_id, signer.renewal_request_id,
                           signer.party_role, signer.full_name,
                           signer.government_id_verified_at,
                           signer.selfie_verified_at, signer.signed_at,
                           request.client_decision, request.status,
                           request.office_processing_required,
                           client.full_name as borrower_name,
                           loan.loan_number
                    from lending.renewal_required_signers signer
                    join lending.client_renewal_requests request
                      on request.id = signer.renewal_request_id
                    join lending.clients client on client.id = request.client_id
                    join lending.loans loan on loan.id = request.loan_id
                    where signer.user_id = %s
                      and signer.is_required = true
                      and request.status = 'approved'
                    order by request.submitted_at desc, signer.id desc
                    """,
                    (actor.user_id,),
                )
                items = [
                    {
                        "signer_id": str(row["signer_id"]),
                        "request_id": str(row["renewal_request_id"]),
                        "party_role": str(row["party_role"]),
                        "full_name": str(row["full_name"]),
                        "government_id_verified": row["government_id_verified_at"] is not None,
                        "selfie_verified": row["selfie_verified_at"] is not None,
                        "signed": row["signed_at"] is not None,
                        "client_decision": row["client_decision"],
                        "status": row["status"],
                        "office_processing_required": bool(
                            row["office_processing_required"]
                        ),
                        "borrower_name": row["borrower_name"],
                        "loan_number": row["loan_number"],
                    }
                    for row in cursor.fetchall()
                ]
        return {"success": True, "data": {"signatures": items}}

    return router

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response

from .account_repository import AccountConflict, PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .client_account_api import (
    client_account_repository_dependency,
    client_credential_mailer_dependency,
)
from .client_account_repository import PostgresClientAccountRepository
from .auth_admin_client import SupabaseAuthAdminClient
from .credential_mailer import SmtpCredentialMailer
from .first_loan_credential_service import (
    FirstLoanCredentialAccessDenied,
    FirstLoanCredentialService,
    PostgresFirstLoanCredentialRepository,
)
from .management_api import management_auth_admin_dependency
from .request_auth import authenticated_device_context
from .office_review_evidence_route import PrivateOfficeRoute


def first_loan_credential_service_dependency(
    accounts: PostgresClientAccountRepository = Depends(
        client_account_repository_dependency
    ),
    auth_admin: SupabaseAuthAdminClient = Depends(management_auth_admin_dependency),
    mailer: SmtpCredentialMailer = Depends(client_credential_mailer_dependency),
) -> FirstLoanCredentialService:
    return FirstLoanCredentialService(
        intents=PostgresFirstLoanCredentialRepository(),
        accounts=accounts,
        auth_admin=auth_admin,
        mailer=mailer,
    )


def create_first_loan_credential_router() -> APIRouter:
    router = APIRouter(
        prefix="/api/v1/management/first-loans",
        tags=["first-loans"],
        route_class=PrivateOfficeRoute,
    )

    @router.post("/{loan_id}/credentials")
    def provision_credentials(
        loan_id: UUID,
        response: Response,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        service: FirstLoanCredentialService = Depends(
            first_loan_credential_service_dependency
        ),
    ) -> dict[str, object]:
        try:
            actor = authenticated_device_context(
                authorization=authorization,
                device_identifier=x_device_id,
                auth=auth,
                accounts=accounts,
                permission="client.credential.manage",
                permission_error="Client credential management permission is required.",
            )
            if (
                not {"employee", "management"}.intersection(actor.roles)
                or actor.registered_device_id is None
            ):
                raise HTTPException(
                    status_code=403,
                    detail="An authorized office account and active device are required.",
                )
            result = service.provision(
                loan_id=loan_id,
                actor_user_id=actor.user_id,
                registered_device_id=actor.registered_device_id,
            )
        except FirstLoanCredentialAccessDenied as exc:
            raise HTTPException(
                status_code=403, detail=str(exc), headers={"Cache-Control": "no-store"}
            ) from exc
        except AccountConflict as exc:
            raise HTTPException(
                status_code=409, detail=str(exc), headers={"Cache-Control": "no-store"}
            ) from exc
        except HTTPException as exc:
            exc.headers = {**(exc.headers or {}), "Cache-Control": "no-store"}
            raise
        response.headers["Cache-Control"] = "no-store"
        return result

    return router

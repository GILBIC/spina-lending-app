from __future__ import annotations

import base64
import binascii
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from psycopg.errors import CheckViolation
from pydantic import Field, StrictBool, model_validator

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .first_loan_repository import (
    APPROVE_PERMISSION,
    RELEASE_PERMISSION,
    REVIEW_PERMISSION,
    FirstLoanAccessDenied,
    FirstLoanConflict,
    PostgresFirstLoanRepository,
)
from .first_loan_terms import FirstLoanTerms, Money, StrictInput
from .office_review_evidence_repository import OfficeReviewEvidenceConflict
from .office_review_evidence_storage import EvidenceFileError
from .office_review_evidence_route import PrivateOfficeRoute
from .request_auth import authenticated_device_context


class ApprovalRequest(StrictInput):
    request_id: UUID
    application_version_id: UUID
    terms: FirstLoanTerms
    template_version: str = Field(min_length=1, max_length=200)


class RejectionRequest(StrictInput):
    request_id: UUID
    application_version_id: UUID
    reason: str = Field(min_length=1, max_length=1000)


class PacketRequest(StrictInput):
    request_id: UUID
    packet_hash: str = Field(pattern="^[0-9a-f]{64}$")


class CancellationRequest(PacketRequest):
    reason: str = Field(min_length=1, max_length=1000)


class RevocationRequest(StrictInput):
    request_id: UUID
    authorization_id: UUID
    reason: str = Field(min_length=1, max_length=1000)


class EvidenceRequest(PacketRequest):
    purpose: Literal["borrower_contract_signed", "borrower_cash_received"]
    media_type: Literal["application/pdf", "image/png", "image/jpeg"]
    content_base64: str = Field(min_length=1, max_length=13981016)
    authorization_id: UUID | None = None
    witnessed_wet_signature: StrictBool = False

    @model_validator(mode="after")
    def require_witness(self):
        if (
            self.purpose == "borrower_contract_signed"
            and not self.witnessed_wet_signature
        ):
            raise ValueError(
                "The named borrower wet signature must be witnessed at the office."
            )
        return self


class ReleaseRequest(PacketRequest):
    authorization_id: UUID
    contract_evidence_reference: str = Field(min_length=1, max_length=100)
    cash_evidence_reference: str = Field(min_length=1, max_length=100)
    cash_amount: Money
    borrower_confirmed: StrictBool


def first_loan_repository_dependency():
    return PostgresFirstLoanRepository()


class LazyPostReleaseProvisioner:
    def provision(self, **arguments):
        # Construction is deliberately after the financial commit. A missing
        # external Auth configuration cannot prevent recording actual handoff.
        from .auth_admin_client import SupabaseAuthAdminClient
        from .client_account_repository import PostgresClientAccountRepository
        from .credential_mailer import SmtpCredentialMailer
        from .first_loan_credential_service import (
            FirstLoanCredentialService,
            PostgresFirstLoanCredentialRepository,
        )

        admin = SupabaseAuthAdminClient()
        try:
            return FirstLoanCredentialService(
                intents=PostgresFirstLoanCredentialRepository(),
                accounts=PostgresClientAccountRepository(),
                auth_admin=admin,
                mailer=SmtpCredentialMailer(),
            ).provision(**arguments)
        finally:
            admin.close()


def first_loan_post_release_dependency():
    return LazyPostReleaseProvisioner()


def _translate(error):
    if isinstance(error, HTTPException):
        error.headers = {**(error.headers or {}), "Cache-Control": "no-store"}
        return error
    return HTTPException(
        403 if isinstance(error, FirstLoanAccessDenied) else 409,
        str(error),
        headers={"Cache-Control": "no-store"},
    )


def create_first_loan_router():
    router = APIRouter(
        prefix="/api/v1/management/first-loans",
        tags=["first-loans"],
        route_class=PrivateOfficeRoute,
    )

    def actor_dependency(permission, management=False):
        def actor(
            authorization: str | None = Header(None, alias="Authorization"),
            x_device_id: str | None = Header(None, alias="X-Device-Id"),
            auth: SupabaseAuthClient = Depends(auth_client_dependency),
            accounts: PostgresAccountRepository = Depends(
                account_repository_dependency
            ),
        ):
            try:
                context = authenticated_device_context(
                    authorization=authorization,
                    device_identifier=x_device_id,
                    auth=auth,
                    accounts=accounts,
                    permission=permission,
                    permission_error="The exact first-loan permission is required.",
                )
                roles = {"management"} if management else {"employee", "management"}
                if (
                    not roles.intersection(context.roles)
                    or context.registered_device_id is None
                ):
                    raise FirstLoanAccessDenied(
                        "An authorized office role and persisted active device are required."
                    )
                return context
            except (FirstLoanAccessDenied, HTTPException) as error:
                raise _translate(error) from error

        return actor

    reviewer = actor_dependency(REVIEW_PERMISSION)
    manager = actor_dependency(APPROVE_PERMISSION, True)
    staff = actor_dependency(RELEASE_PERMISSION)

    def execute(response, repository, actor, method, **arguments):
        try:
            result = getattr(repository, method)(
                actor_user_id=actor.user_id,
                registered_device_id=actor.registered_device_id,
                **arguments,
            )
        except CheckViolation as error:
            if error.diag.constraint_name != "client_cif_new_credit_ready":
                raise
            raise _translate(
                FirstLoanConflict(
                    "Refresh the client record and complete any required CIF "
                    "re-verification before approving or releasing new credit."
                )
            ) from error
        except (
            FirstLoanAccessDenied,
            FirstLoanConflict,
            OfficeReviewEvidenceConflict,
            EvidenceFileError,
            ValueError,
        ) as error:
            raise _translate(error) from error
        response.headers["Cache-Control"] = "no-store"
        return result

    @router.get("/context")
    def context(
        response: Response,
        actor=Depends(reviewer),
        repository=Depends(first_loan_repository_dependency),
    ):
        return execute(response, repository, actor, "context")

    @router.get("/by-application/{application_id}")
    def by_application(
        application_id: UUID,
        response: Response,
        actor=Depends(reviewer),
        repository=Depends(first_loan_repository_dependency),
    ):
        return execute(
            response, repository, actor, "by_application", application_id=application_id
        )

    @router.get("/{loan_id}")
    def get(
        loan_id: UUID,
        response: Response,
        actor=Depends(reviewer),
        repository=Depends(first_loan_repository_dependency),
    ):
        return execute(response, repository, actor, "get", loan_id=loan_id)

    @router.post("/approve", status_code=201)
    def approve(
        body: ApprovalRequest,
        response: Response,
        actor=Depends(manager),
        repository=Depends(first_loan_repository_dependency),
    ):
        return execute(
            response,
            repository,
            actor,
            "approve",
            request_id=body.request_id,
            application_version_id=body.application_version_id,
            terms=body.terms.model_dump(mode="json"),
            template_version=body.template_version,
        )

    @router.post("/reject", status_code=201)
    def reject(
        body: RejectionRequest,
        response: Response,
        actor=Depends(manager),
        repository=Depends(first_loan_repository_dependency),
    ):
        return execute(response, repository, actor, "reject", **body.model_dump())

    @router.post("/{loan_id}/cancel-approval")
    def cancel(
        loan_id: UUID,
        body: CancellationRequest,
        response: Response,
        actor=Depends(manager),
        repository=Depends(first_loan_repository_dependency),
    ):
        return execute(
            response,
            repository,
            actor,
            "cancel_approval",
            loan_id=loan_id,
            **body.model_dump(),
        )

    @router.post("/{loan_id}/authorize-release", status_code=201)
    def authorize(
        loan_id: UUID,
        body: PacketRequest,
        response: Response,
        actor=Depends(manager),
        repository=Depends(first_loan_repository_dependency),
    ):
        return execute(
            response,
            repository,
            actor,
            "authorize_release",
            loan_id=loan_id,
            **body.model_dump(),
        )

    @router.post("/{loan_id}/revoke-release", status_code=201)
    def revoke(
        loan_id: UUID,
        body: RevocationRequest,
        response: Response,
        actor=Depends(manager),
        repository=Depends(first_loan_repository_dependency),
    ):
        return execute(
            response,
            repository,
            actor,
            "revoke_release",
            loan_id=loan_id,
            **body.model_dump(),
        )

    @router.post("/{loan_id}/evidence", status_code=201)
    def evidence(
        loan_id: UUID,
        body: EvidenceRequest,
        response: Response,
        actor=Depends(staff),
        repository=Depends(first_loan_repository_dependency),
    ):
        try:
            content = base64.b64decode(body.content_base64, validate=True)
        except (ValueError, binascii.Error) as error:
            raise HTTPException(
                422,
                "A valid encoded signed document is required.",
                headers={"Cache-Control": "no-store"},
            ) from error
        return execute(
            response,
            repository,
            actor,
            "capture",
            loan_id=loan_id,
            content=content,
            **body.model_dump(exclude={"content_base64"}),
        )

    @router.post("/{loan_id}/release")
    def release(
        loan_id: UUID,
        body: ReleaseRequest,
        response: Response,
        actor=Depends(staff),
        repository=Depends(first_loan_repository_dependency),
        provisioner=Depends(first_loan_post_release_dependency),
    ):
        result = execute(
            response, repository, actor, "release", loan_id=loan_id, **body.model_dump()
        )
        try:
            result["credentials"] = provisioner.provision(
                loan_id=loan_id,
                actor_user_id=actor.user_id,
                registered_device_id=actor.registered_device_id,
            )
        except Exception:
            # Never turn a committed release into an apparent failed handoff.
            result["credentials"] = {
                "status": "pending",
                "detail": "Release recorded. Credential setup requires a protected retry.",
            }
        return result

    return router

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .client_document_repository import (
    ClientDocumentNotFound,
    ClientDocumentUnavailable,
    PostgresClientDocumentRepository,
)
from .client_document_rendering import render_record_copy
from .client_loan_api import client_loan_repository_dependency
from .client_loan_repository import ClientBorrowerNotLinked
from .client_payment_api import (
    _payment_payload,
    _statement_payload,
    client_payment_repository_dependency,
)
from .client_payment_repository import ClientPaymentBorrowerNotLinked
from .office_review_evidence_route import PrivateOfficeRoute
from .request_auth import authenticated_device_context


def client_document_repository_dependency() -> PostgresClientDocumentRepository:
    return PostgresClientDocumentRepository()


def _client_actor(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    auth: SupabaseAuthClient = Depends(auth_client_dependency),
    accounts: PostgresAccountRepository = Depends(account_repository_dependency),
):
    actor = authenticated_device_context(
        authorization=authorization,
        device_identifier=x_device_id,
        auth=auth,
        accounts=accounts,
    )
    if (
        "client" not in actor.roles
        or actor.status != "active"
        or not actor.device_registered
    ):
        raise HTTPException(
            403, "An active Client account and registered device are required."
        )
    return actor


def _document_error(error):
    return HTTPException(
        404 if isinstance(error, ClientDocumentNotFound) else 409,
        "The requested document is unavailable.",
    )


def _pdf_response(content: bytes, filename: str, media_type: str = "application/pdf"):
    return Response(
        content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
        },
    )


def create_client_document_router() -> APIRouter:
    router = APIRouter(tags=["client documents"], route_class=PrivateOfficeRoute)

    @router.get("/api/v1/client/loans/{loan_id}/documents")
    @router.get(
        "/api/mobile/v1/client/loans/{loan_id}/documents", include_in_schema=False
    )
    def list_documents(
        loan_id: UUID,
        request: Request,
        actor=Depends(_client_actor),
        repository=Depends(client_document_repository_dependency),
    ):
        try:
            records = repository.list_for_user(user_id=actor.user_id, loan_id=loan_id)
        except (ClientDocumentNotFound, ClientDocumentUnavailable) as error:
            raise _document_error(error) from error
        return {
            "success": True,
            "data": {
                "documents": [
                    {
                        "document_id": str(record.document_id),
                        "kind": record.kind,
                        "media_type": record.media_type,
                        "byte_count": record.byte_count,
                        "content_sha256": record.content_sha256,
                        "generated_at": record.generated_at.isoformat(),
                        "released_at": record.released_at.isoformat(),
                        "download_path": f"{request.url.path}/{record.document_id}",
                    }
                    for record in records
                ]
            },
        }

    @router.get("/api/v1/client/loans/{loan_id}/documents/{document_id}")
    @router.get(
        "/api/mobile/v1/client/loans/{loan_id}/documents/{document_id}",
        include_in_schema=False,
    )
    def download_document(
        loan_id: UUID,
        document_id: UUID,
        actor=Depends(_client_actor),
        repository=Depends(client_document_repository_dependency),
    ):
        try:
            download = repository.download_for_user(
                user_id=actor.user_id, loan_id=loan_id, document_id=document_id
            )
        except (ClientDocumentNotFound, ClientDocumentUnavailable) as error:
            raise _document_error(error) from error
        prefix = {
            "finalized_loan_packet": "loan-packet",
            "signed_loan_contract": "signed-loan-contract",
            "cash_release_acknowledgment": "cash-release-acknowledgment",
        }[download.record.kind]
        extension = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg"}[
            download.record.media_type
        ]
        return _pdf_response(
            download.content,
            f"{prefix}-{loan_id}.{extension}",
            download.record.media_type,
        )

    @router.get("/api/v1/client/statement/document")
    @router.get("/api/mobile/v1/client/statement/document", include_in_schema=False)
    def statement_document(
        actor=Depends(_client_actor),
        loans=Depends(client_loan_repository_dependency),
        payments=Depends(client_payment_repository_dependency),
    ):
        try:
            portfolio = loans.list_for_user(user_id=actor.user_id)
            timeline = payments.list_for_user(user_id=actor.user_id)
            if portfolio.client_id != timeline.client_id:
                raise ClientDocumentNotFound()
        except (
            ClientBorrowerNotLinked,
            ClientPaymentBorrowerNotLinked,
            ClientDocumentNotFound,
        ) as error:
            raise HTTPException(
                404, "The requested document is unavailable."
            ) from error
        saved = _statement_payload(portfolio, timeline)
        return _pdf_response(
            render_record_copy(
                title="Statement of Account - record copy",
                client=saved["client"],
                loans=saved["loans"],
                payments=saved["payments"],
                generated_at=datetime.now(UTC),
            ),
            "statement-of-account-record-copy.pdf",
        )

    @router.get("/api/v1/client/payments/{transaction_id}/document")
    @router.get(
        "/api/mobile/v1/client/payments/{transaction_id}/document",
        include_in_schema=False,
    )
    def payment_document(
        transaction_id: UUID,
        actor=Depends(_client_actor),
        payments=Depends(client_payment_repository_dependency),
    ):
        try:
            timeline = payments.list_for_user(user_id=actor.user_id)
        except ClientPaymentBorrowerNotLinked as error:
            raise HTTPException(
                404, "The requested document is unavailable."
            ) from error
        payment = next(
            (
                record
                for record in timeline.payments
                if record.transaction_id == transaction_id
            ),
            None,
        )
        if payment is None:
            raise HTTPException(404, "The requested document is unavailable.")
        return _pdf_response(
            render_record_copy(
                title="Payment record copy",
                client={
                    "client_name": timeline.client_name,
                    "client_code": timeline.client_code,
                },
                payments=[_payment_payload(payment)],
                generated_at=datetime.now(UTC),
                voided=payment.is_voided,
            ),
            f"payment-record-{transaction_id}.pdf",
        )

    return router

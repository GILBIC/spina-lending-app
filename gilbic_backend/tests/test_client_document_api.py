from dataclasses import replace
from datetime import UTC, datetime
from importlib import import_module
from io import BytesIO
from uuid import UUID, uuid4
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader

from gilbic_backend.auth_api import (
    account_repository_dependency,
    auth_client_dependency,
)
from test_client_payment_api import (
    CLIENT_USER_ID,
    POSTED_TRANSACTION_ID,
    VOIDED_TRANSACTION_ID,
    FakeAccounts,
    FakeAuthClient,
    FakePayments,
    headers,
)
from test_client_loan_api import FakeLoans
from gilbic_backend.account_repository import AccountDisabled, DeviceRevoked
from gilbic_backend.client_document_repository import (
    ClientDocumentNotFound,
    ClientDocumentUnavailable,
    ClientDocumentRecord,
)
from gilbic_backend.client_loan_repository import ClientBorrowerNotLinked
from gilbic_backend.client_payment_repository import ClientPaymentBorrowerNotLinked


LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
DOCUMENT_ID = UUID("77777777-7777-4777-8777-777777777777")
PDF = b"%PDF-1.4\nIMMUTABLE ISSUED FIXTURE\n%%EOF"


def test_client_downloads_exact_original_packet_without_office_permissions():
    try:
        api = import_module("gilbic_backend.client_document_api")
        import_module("gilbic_backend.client_document_repository")
    except ModuleNotFoundError:
        pytest.fail(
            "Client historical document retrieval is not implemented", pytrace=False
        )

    class Repository:
        calls = []

        def download_for_user(self, **arguments):
            self.calls.append(arguments)
            return SimpleNamespace(
                content=PDF,
                record=SimpleNamespace(
                    kind="finalized_loan_packet", media_type="application/pdf"
                ),
            )

    repository = Repository()
    app = FastAPI()
    app.include_router(api.create_client_document_router())
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts()
    app.dependency_overrides[api.client_document_repository_dependency] = lambda: (
        repository
    )
    client = TestClient(app)
    response = client.get(
        f"/api/mobile/v1/client/loans/{LOAN_ID}/documents/{DOCUMENT_ID}",
        headers=headers(),
    )
    assert response.status_code == 200
    assert response.content == PDF
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-security-policy"] == "sandbox"
    assert repository.calls == [
        {"user_id": CLIENT_USER_ID, "loan_id": LOAN_ID, "document_id": DOCUMENT_ID}
    ]


def make_client():
    from gilbic_backend import client_document_api as api
    from gilbic_backend.client_loan_api import client_loan_repository_dependency
    from gilbic_backend.client_payment_api import client_payment_repository_dependency

    app = FastAPI()
    app.include_router(api.create_client_document_router())
    accounts = FakeAccounts()
    payments, loans = FakePayments(), FakeLoans()
    documents = FakeDocuments()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: accounts
    app.dependency_overrides[client_payment_repository_dependency] = lambda: payments
    app.dependency_overrides[client_loan_repository_dependency] = lambda: loans
    app.dependency_overrides[api.client_document_repository_dependency] = lambda: (
        documents
    )
    return TestClient(app), app, accounts, payments, loans, documents


def pdf_text(response):
    return "\n".join(
        page.extract_text() for page in PdfReader(BytesIO(response.content)).pages
    )


def test_payment_record_copy_uses_current_official_values_and_explicit_void_status():
    client, _, _, payments, _, _ = make_client()
    response = client.get(
        f"/api/mobile/v1/client/payments/{VOIDED_TRANSACTION_ID}/document",
        headers=headers(),
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    text = pdf_text(response)
    for value in (
        "Payment record copy",
        "GBC-20260805-00000008",
        "VOIDED",
        "50.00",
        "4900.00",
        "Payment posted to the wrong borrower",
        "Generated",
    ):
        assert value in text
    assert "not an original issued receipt or tax invoice" in text
    assert payments.user_id == CLIENT_USER_ID


class FakeDocuments:
    def __init__(self):
        self.calls = []
        self.error = None

    def list_for_user(self, **arguments):
        self.calls.append(arguments)
        if self.error:
            raise self.error
        return (
            ClientDocumentRecord(
                document_id=DOCUMENT_ID,
                loan_id=LOAN_ID,
                content_sha256="a" * 64,
                byte_count=len(PDF),
                generated_at=datetime(2026, 9, 1, tzinfo=UTC),
                released_at=datetime(2026, 9, 2, tzinfo=UTC),
            ),
        )

    def download_for_user(self, **arguments):
        self.calls.append(arguments)
        if self.error:
            raise self.error
        return SimpleNamespace(
            content=PDF,
            record=SimpleNamespace(
                kind="finalized_loan_packet", media_type="application/pdf"
            ),
        )


PATHS = (
    f"/loans/{LOAN_ID}/documents",
    f"/loans/{LOAN_ID}/documents/{DOCUMENT_ID}",
    "/statement/document",
    f"/payments/{POSTED_TRANSACTION_ID}/document",
)


@pytest.mark.parametrize("prefix", ["/api/v1", "/api/mobile/v1"])
def test_list_allowlists_metadata_and_uses_same_protected_alias(prefix):
    client, _, _, _, _, documents = make_client()
    response = client.get(
        f"{prefix}/client/loans/{LOAN_ID}/documents", headers=headers()
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "success": True,
        "data": {
            "documents": [
                {
                    "document_id": str(DOCUMENT_ID),
                    "kind": "finalized_loan_packet",
                    "media_type": "application/pdf",
                    "byte_count": len(PDF),
                    "content_sha256": "a" * 64,
                    "generated_at": "2026-09-01T00:00:00+00:00",
                    "released_at": "2026-09-02T00:00:00+00:00",
                    "download_path": f"{prefix}/client/loans/{LOAN_ID}/documents/{DOCUMENT_ID}",
                }
            ]
        },
    }
    assert documents.calls == [{"user_id": CLIENT_USER_ID, "loan_id": LOAN_ID}]


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("role", ["management", "employee", "collector", "unknown"])
def test_non_client_cannot_read_documents_even_with_office_permission(path, role):
    client, app, accounts, payments, loans, documents = make_client()

    class Accounts:
        def get_context_for_device(self, **arguments):
            return replace(
                accounts.get_context_for_device(**arguments),
                roles=(role,),
                permissions=("lending.first_loan.approve",),
            )

    app.dependency_overrides[account_repository_dependency] = lambda: Accounts()
    response = client.get(f"/api/v1/client{path}", headers=headers())
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert documents.calls == [] and payments.user_id is None and loans.user_id is None


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize(
    "failure,status",
    [
        ("no_auth", 401),
        ("no_device", 400),
        ("revoked", 403),
        ("inactive", 403),
        ("device_false", 403),
    ],
)
def test_auth_and_device_failures_are_private_and_do_not_read(path, failure, status):
    client, app, accounts, payments, loans, documents = make_client()
    request_headers = headers()
    if failure == "no_auth":
        del request_headers["Authorization"]
    elif failure == "no_device":
        del request_headers["X-Device-Id"]
    else:

        class Accounts:
            def get_context_for_device(self, **arguments):
                if failure == "revoked":
                    raise DeviceRevoked("Device revoked")
                if failure == "inactive":
                    raise AccountDisabled("Account disabled")
                return replace(
                    accounts.get_context_for_device(**arguments),
                    device_registered=False,
                )

        app.dependency_overrides[account_repository_dependency] = lambda: Accounts()
    response = client.get(f"/api/v1/client{path}", headers=request_headers)
    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"
    assert documents.calls == [] and payments.user_id is None and loans.user_id is None


@pytest.mark.parametrize("suffix", ["", f"/{DOCUMENT_ID}"])
@pytest.mark.parametrize(
    "error,status", [(ClientDocumentNotFound, 404), (ClientDocumentUnavailable, 409)]
)
def test_packet_errors_are_generic_without_storage_or_identity_leaks(
    suffix, error, status
):
    client, _, _, _, _, documents = make_client()
    documents.error = error("sensitive borrower /private/storage/path")
    response = client.get(
        f"/api/v1/client/loans/{LOAN_ID}/documents{suffix}", headers=headers()
    )
    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"detail": "The requested document is unavailable."}


@pytest.mark.parametrize(
    "path",
    [
        "/loans/not-a-uuid/documents",
        f"/loans/{LOAN_ID}/documents/not-a-uuid",
        "/payments/not-a-uuid/document",
    ],
)
def test_invalid_document_identity_is_rejected_before_repository_read(path):
    client, _, _, payments, loans, documents = make_client()
    response = client.get(f"/api/v1/client{path}", headers=headers())
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert documents.calls == [] and payments.user_id is None and loans.user_id is None


@pytest.mark.parametrize("prefix", ["/api/v1", "/api/mobile/v1"])
def test_statement_uses_exact_authoritative_balance_and_includes_voided_history(
    prefix, monkeypatch
):
    monkeypatch.delenv("GILBIC_OFFICE_REVIEW_EVIDENCE_ROOT", raising=False)
    client, _, _, payments, loans, _ = make_client()
    response = client.get(f"{prefix}/client/statement/document", headers=headers())
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="statement-of-account-record-copy.pdf"'
    )
    text = pdf_text(response)
    for value in (
        "Statement of Account - record copy",
        "4950.00",
        "3000.00",
        "GBC-20260806-00000010",
        "GBC-20260805-00000008",
        "VOIDED",
        "ACCEPTED",
        "State version",
        "Correction version",
    ):
        assert value in text
    assert payments.user_id == loans.user_id == CLIENT_USER_ID


def test_unknown_or_other_clients_payment_has_same_generic_not_found():
    client, _, _, _, _, _ = make_client()
    response = client.get(
        f"/api/v1/client/payments/{uuid4()}/document", headers=headers()
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "The requested document is unavailable."}
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "failure", ["loan_unlinked", "payment_unlinked", "link_changed"]
)
def test_statement_cannot_mix_different_or_missing_client_links(failure, monkeypatch):
    client, _, _, payments, loans, _ = make_client()
    if failure == "loan_unlinked":
        loans.error = ClientBorrowerNotLinked("Sensitive link")
    elif failure == "payment_unlinked":
        payments.error = ClientPaymentBorrowerNotLinked("Sensitive link")
    else:
        timeline = payments.list_for_user(user_id=CLIENT_USER_ID)
        monkeypatch.setattr(
            payments, "list_for_user", lambda **kw: replace(timeline, client_id=uuid4())
        )
    response = client.get("/api/v1/client/statement/document", headers=headers())
    assert response.status_code == 404
    assert response.json() == {"detail": "The requested document is unavailable."}
    assert response.headers["cache-control"] == "no-store"


def test_document_router_only_exposes_read_operations():
    from gilbic_backend.client_document_api import create_client_document_router

    assert all(
        route.methods == {"GET"} for route in create_client_document_router().routes
    )


def test_release_linked_signed_scan_keeps_original_media_type_and_bytes(monkeypatch):
    client, _, _, _, _, documents = make_client()
    content = b"\x89PNG\r\n\x1a\nSYNTHETIC SIGNED SCAN"
    monkeypatch.setattr(
        documents,
        "download_for_user",
        lambda **kw: SimpleNamespace(
            content=content,
            record=SimpleNamespace(kind="signed_loan_contract", media_type="image/png"),
        ),
    )
    response = client.get(
        f"/api/v1/client/loans/{LOAN_ID}/documents/{DOCUMENT_ID}", headers=headers()
    )
    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"] == "image/png"
    assert (
        response.headers["content-disposition"]
        == f'attachment; filename="signed-loan-contract-{LOAN_ID}.png"'
    )

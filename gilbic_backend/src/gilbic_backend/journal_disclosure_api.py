"""Reviewed journal components and financing-liability presentation policy."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field, StrictBool, StrictInt, StrictStr

from .journal_disclosure_repository import PostgresJournalDisclosureRepository
from .reporting_evidence_api import (
    Accounts,
    Auth,
    Authorization,
    Device,
    Evidence,
    actor,
    reviewed,
)
from .reporting_evidence_repository import ReportingEvidenceError


class DisclosurePolicyRequest(Evidence):
    request_id: UUID
    book_id: UUID
    reporting_policy_id: UUID
    expected_version: StrictInt = Field(ge=0, le=999999999)
    financing_account_codes: list[StrictStr] = Field(max_length=100)
    reviewed: StrictBool = False


class DisclosureComponent(Evidence):
    debit_line_id: UUID
    credit_line_id: UUID
    amount: StrictStr = Field(pattern=r"^(0|[1-9][0-9]{0,15})\.[0-9]{2}$")
    classification: Literal[
        "cash_operating",
        "cash_investing",
        "cash_financing",
        "cash_internal",
        "noncash_investing",
        "noncash_financing",
        "noncash_investing_financing",
        "noncash_operating",
        "noncash_reclassification",
    ]


class DisclosureReviewRequest(Evidence):
    request_id: UUID
    book_id: UUID
    disclosure_policy_id: UUID
    journal_entry_id: UUID
    expected_version: StrictInt = Field(ge=0, le=999999999)
    source_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    components: list[DisclosureComponent] = Field(min_length=1, max_length=1000)
    reason: StrictStr = Field(min_length=1, max_length=4000)
    reviewed: StrictBool = False


def journal_disclosure_repository_dependency():
    return PostgresJournalDisclosureRepository()


Reports = Annotated[
    PostgresJournalDisclosureRepository,
    Depends(journal_disclosure_repository_dependency),
]


def create_journal_disclosure_router():
    router = APIRouter(tags=["management financial statements"])

    @router.get("/api/v1/management/financial-accounting/statements/disclosures")
    @router.get(
        "/api/mobile/v1/management/financial-accounting/statements/disclosures",
        include_in_schema=False,
    )
    def get_disclosures(
        auth: Auth,
        accounts: Accounts,
        reports: Reports,
        period_id: Annotated[UUID, Query()],
        authorization: Authorization = None,
        x_device_id: Device = None,
    ):
        context = actor(auth, accounts, authorization, x_device_id, "accounting.view")
        try:
            result = reports.load_disclosures(
                period_id=period_id, actor_user_id=context.user_id
            )
        except ReportingEvidenceError as error:
            raise HTTPException(status_code=error.status, detail=str(error)) from error
        return {"success": True, "data": {"disclosures": result}}

    @router.post("/api/v1/management/financial-accounting/statements/disclosure-policy")
    @router.post(
        "/api/mobile/v1/management/financial-accounting/statements/disclosure-policy",
        include_in_schema=False,
    )
    def retain_policy(
        body: DisclosurePolicyRequest,
        auth: Auth,
        accounts: Accounts,
        reports: Reports,
        authorization: Authorization = None,
        x_device_id: Device = None,
    ):
        context = actor(
            auth, accounts, authorization, x_device_id, "accounting.journal.manage"
        )
        reviewed(body)
        try:
            identity = reports.retain_disclosure_policy(
                request_id=body.request_id,
                book_id=body.book_id,
                reporting_policy_id=body.reporting_policy_id,
                expected_version=body.expected_version,
                payload=body.model_dump(
                    mode="json",
                    exclude={
                        "request_id",
                        "book_id",
                        "reporting_policy_id",
                        "expected_version",
                    },
                ),
                actor_user_id=context.user_id,
            )
        except ReportingEvidenceError as error:
            raise HTTPException(status_code=error.status, detail=str(error)) from error
        return {"success": True, "data": {"policy_id": str(identity)}}

    @router.post(
        "/api/v1/management/financial-accounting/statements/disclosure-reviews"
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/statements/disclosure-reviews",
        include_in_schema=False,
    )
    def retain_review(
        body: DisclosureReviewRequest,
        auth: Auth,
        accounts: Accounts,
        reports: Reports,
        authorization: Authorization = None,
        x_device_id: Device = None,
    ):
        context = actor(
            auth, accounts, authorization, x_device_id, "accounting.journal.manage"
        )
        reviewed(body)
        try:
            identity = reports.retain_disclosure(
                request_id=body.request_id,
                book_id=body.book_id,
                disclosure_policy_id=body.disclosure_policy_id,
                payload=body.model_dump(
                    mode="json",
                    exclude={"request_id", "book_id", "disclosure_policy_id"},
                ),
                actor_user_id=context.user_id,
            )
        except ReportingEvidenceError as error:
            raise HTTPException(status_code=error.status, detail=str(error)) from error
        return {"success": True, "data": {"review_id": str(identity)}}

    return router

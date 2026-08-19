from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .database import open_connection
from .request_auth import authenticated_device_context


MAX_PROOF_BYTES = 8 * 1024 * 1024
ALLOWED_PROOF_TYPES = {"image/jpeg", "image/png", "image/webp"}


class StrictWorkflowModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CollectorRecommendationBody(StrictWorkflowModel):
    recommendation: Literal["recommend", "do_not_recommend"]
    reason_code: str = Field(min_length=2, max_length=80)
    comment: str = Field(default="", max_length=1000)

    @field_validator("reason_code", "comment")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.split())


class RenewalSignerInput(StrictWorkflowModel):
    party_role: Literal["borrower", "guarantor", "solidary_co_maker", "surety"]
    full_name: str = Field(min_length=2, max_length=200)
    user_id: UUID | None = None
    government_id_verified: bool = False
    selfie_verified: bool = False


class ManagementRenewalTermsBody(StrictWorkflowModel):
    decision: Literal["approved", "rejected"]
    approved_principal: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    review_note: str = Field(default="", max_length=1000)
    override_reason: str = Field(default="", max_length=1000)
    office_processing_required: bool = False
    signers: list[RenewalSignerInput] = Field(default_factory=list, max_length=10)

    @field_validator("review_note", "override_reason")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        return " ".join(value.split())


class ClientRenewalDecisionBody(StrictWorkflowModel):
    decision: Literal["accepted", "declined"]


class ManagementProofReviewBody(StrictWorkflowModel):
    decision: Literal["approved", "request_new_photo", "flag_for_review"]
    note: str = Field(default="", max_length=1000)


class SignerMarkSignedBody(StrictWorkflowModel):
    signer_id: UUID


def _money(value) -> str | None:
    if value is None:
        return None
    return format(Decimal(value).quantize(Decimal("0.01")), "f")


def _renewal_row(cursor, *, request_id: UUID):
    cursor.execute(
        """
        select
            request.id as request_id,
            request.client_id,
            client.client_code,
            client.full_name as client_name,
            client.area,
            request.loan_id,
            loan.loan_number,
            loan_type.name as loan_type_name,
            loan_type.calculation_mode,
            loan.principal as current_principal,
            loan.daily_amount,
            loan_type.term_days,
            coalesce(state.remaining_balance, loan.principal) as remaining_balance,
            request.requested_amount,
            request.client_message,
            request.status,
            request.submitted_at,
            request.collector_recommendation,
            request.collector_reason_code,
            request.collector_comment,
            request.recommended_at,
            request.approved_principal,
            request.management_override_reason,
            request.review_note,
            request.reviewed_at,
            request.client_decision,
            request.client_decided_at,
            request.signer_readiness_status,
            request.office_processing_required,
            request.renewal_offset_amount,
            request.net_release_amount,
            request.amount_locked_at,
            request.cash_released_to_collector_at,
            request.collector_cash_received_at,
            request.cash_given_to_client_at,
            request.client_cash_confirmed_at,
            request.handover_proof_status,
            request.activation_status,
            request.new_loan_id,
            lending.collector_area_owner(client.area) as assigned_collector_user_id,
            coalesce((
                select sum(tx.applied_amount)
                from lending.collection_transactions tx
                where tx.loan_id = loan.id and tx.is_voided = false
            ), 0)::numeric(18,2) as paid_cash,
            greatest(
                loan.principal,
                (loan.daily_amount * greatest(coalesce(loan_type.term_days, 120), 1))::numeric(18,2)
            ) as contractual_total
        from lending.client_renewal_requests request
        join lending.clients client on client.id = request.client_id
        join lending.loans loan on loan.id = request.loan_id
        join lending.loan_types loan_type on loan_type.id = loan.loan_type_id
        left join lending.loan_collection_state state on state.loan_id = loan.id
        where request.id = %s
        """,
        (request_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "renewal_request_not_found", "message": "Renewal request was not found."})
    return row


def _signer_payloads(cursor, *, request_id: UUID) -> list[dict[str, object]]:
    cursor.execute(
        """
        select id, party_role, full_name, user_id, is_required,
               government_id_verified_at, selfie_verified_at, signed_at
        from lending.renewal_required_signers
        where renewal_request_id = %s
        order by case party_role when 'borrower' then 0 else 1 end, full_name, id
        """,
        (request_id,),
    )
    return [
        {
            "signer_id": str(row["id"]),
            "party_role": row["party_role"],
            "full_name": row["full_name"],
            "user_id": str(row["user_id"]) if row["user_id"] else None,
            "has_app": row["user_id"] is not None,
            "government_id_verified": row["government_id_verified_at"] is not None,
            "selfie_verified": row["selfie_verified_at"] is not None,
            "signed": row["signed_at"] is not None,
            "ready": (
                row["user_id"] is not None
                and row["government_id_verified_at"] is not None
                and row["selfie_verified_at"] is not None
                and row["signed_at"] is not None
            ),
        }
        for row in cursor.fetchall()
    ]


def _payload(cursor, row) -> dict[str, object]:
    contractual_total = Decimal(row["contractual_total"] or 0)
    paid_cash = Decimal(row["paid_cash"] or 0)
    paid_percent = Decimal("0.0") if contractual_total <= 0 else min(
        Decimal("100.0"),
        (paid_cash / contractual_total * Decimal("100")).quantize(Decimal("0.1")),
    )
    is_7x7 = str(row["calculation_mode"] or "").lower() == "seven_by_seven"
    regular_eligible = paid_percent >= Decimal("50.0") or str(row["status"]).lower() == "paid"
    signers = _signer_payloads(cursor, request_id=row["request_id"])
    return {
        "request_id": str(row["request_id"]),
        "client_id": str(row["client_id"]),
        "client_code": row["client_code"],
        "client_name": row["client_name"],
        "area": row["area"],
        "loan_id": str(row["loan_id"]),
        "loan_number": row["loan_number"],
        "loan_type_name": row["loan_type_name"],
        "calculation_mode": row["calculation_mode"],
        "is_7x7": is_7x7,
        "current_principal": _money(row["current_principal"]),
        "remaining_balance": _money(row["remaining_balance"]),
        "contractual_total": _money(contractual_total),
        "paid_cash": _money(paid_cash),
        "paid_percent": format(paid_percent, "f"),
        "regular_50_percent_eligible": regular_eligible,
        "requested_amount": _money(row["requested_amount"]),
        "client_message": row["client_message"],
        "status": row["status"],
        "submitted_at": row["submitted_at"].isoformat(),
        "collector_recommendation": row["collector_recommendation"],
        "collector_reason_code": row["collector_reason_code"],
        "collector_comment": row["collector_comment"],
        "recommended_at": row["recommended_at"].isoformat() if row["recommended_at"] else None,
        "approved_principal": _money(row["approved_principal"]),
        "management_override_reason": row["management_override_reason"],
        "review_note": row["review_note"],
        "reviewed_at": row["reviewed_at"].isoformat() if row["reviewed_at"] else None,
        "client_decision": row["client_decision"],
        "client_decided_at": row["client_decided_at"].isoformat() if row["client_decided_at"] else None,
        "signer_readiness_status": row["signer_readiness_status"],
        "office_processing_required": bool(row["office_processing_required"]),
        "signers": signers,
        "renewal_offset_amount": _money(row["renewal_offset_amount"]),
        "net_release_amount": _money(row["net_release_amount"]),
        "amount_locked_at": row["amount_locked_at"].isoformat() if row["amount_locked_at"] else None,
        "cash_released_to_collector_at": row["cash_released_to_collector_at"].isoformat() if row["cash_released_to_collector_at"] else None,
        "collector_cash_received_at": row["collector_cash_received_at"].isoformat() if row["collector_cash_received_at"] else None,
        "cash_given_to_client_at": row["cash_given_to_client_at"].isoformat() if row["cash_given_to_client_at"] else None,
        "client_cash_confirmed_at": row["client_cash_confirmed_at"].isoformat() if row["client_cash_confirmed_at"] else None,
        "handover_proof_status": row["handover_proof_status"],
        "activation_status": row["activation_status"],
        "new_loan_id": str(row["new_loan_id"]) if row["new_loan_id"] else None,
        "assigned_collector_user_id": str(row["assigned_collector_user_id"]) if row["assigned_collector_user_id"] else None,
        "ready_for_activation": (
            row["handover_proof_status"] == "approved"
            and row["client_cash_confirmed_at"] is not None
            and row["new_loan_id"] is not None
        ),
    }


def _assert_assigned(row, actor_user_id: UUID) -> None:
    if row["assigned_collector_user_id"] != actor_user_id:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "renewal_assigned_collector_required",
                "message": "Only the permanently assigned Collector can act on this renewal.",
            },
        )


def _audit(cursor, *, actor_user_id: UUID, action: str, request_id: UUID, details: str = "") -> None:
    cursor.execute(
        """
        insert into core.audit_logs (actor_user_id, action, target_type, target_id, details)
        values (%s, %s, 'client_renewal_request', %s, jsonb_build_object('details', %s::text))
        """,
        (actor_user_id, action, request_id, details),
    )


def create_renewal_workflow_router() -> APIRouter:
    router = APIRouter(tags=["renewal workflow"])

    @router.get("/api/v1/collector/renewals")
    @router.get("/api/mobile/v1/collector/renewals", include_in_schema=False)
    def collector_queue(
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
            permission="renewal.recommend.assigned",
            permission_error="Assigned Collector renewal permission is required.",
        )
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select request.id
                    from lending.client_renewal_requests request
                    join lending.clients client on client.id = request.client_id
                    where lending.collector_area_owner(client.area) = %s
                      and request.status in ('pending', 'approved')
                    order by request.submitted_at desc, request.id desc
                    limit 200
                    """,
                    (actor.user_id,),
                )
                ids = [row["id"] for row in cursor.fetchall()]
                items = [_payload(cursor, _renewal_row(cursor, request_id=value)) for value in ids]
        return {"success": True, "data": {"requests": items}}

    @router.post("/api/v1/collector/renewals/{request_id}/recommendation")
    @router.post("/api/mobile/v1/collector/renewals/{request_id}/recommendation", include_in_schema=False)
    def collector_recommendation(
        request_id: UUID,
        body: CollectorRecommendationBody,
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
            permission="renewal.recommend.assigned",
            permission_error="Assigned Collector renewal permission is required.",
        )
        if body.recommendation == "do_not_recommend" and len(body.comment) < 3:
            raise HTTPException(status_code=422, detail={"code": "renewal_nonrecommend_comment_required", "message": "Explain why you do not recommend this renewal."})
        if body.reason_code.lower() == "other" and len(body.comment) < 3:
            raise HTTPException(status_code=422, detail={"code": "renewal_other_comment_required", "message": "Explain the Other recommendation reason."})
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                row = _renewal_row(cursor, request_id=request_id)
                _assert_assigned(row, actor.user_id)
                if row["status"] != "pending":
                    raise HTTPException(status_code=409, detail={"code": "renewal_not_pending", "message": "Management has already decided this renewal."})
                cursor.execute(
                    """
                    update lending.client_renewal_requests
                    set collector_recommendation=%s, collector_reason_code=%s,
                        collector_comment=%s, recommended_by_user_id=%s,
                        recommended_at=now(), updated_at=now()
                    where id=%s
                    """,
                    (body.recommendation, body.reason_code, body.comment, actor.user_id, request_id),
                )
                _audit(cursor, actor_user_id=actor.user_id, action=f"renewal.collector.{body.recommendation}", request_id=request_id, details=f"{body.reason_code}: {body.comment}")
                updated = _renewal_row(cursor, request_id=request_id)
                data = _payload(cursor, updated)
        return {"success": True, "data": {"request": data}}

    @router.post("/api/v1/management/renewals/{request_id}/terms")
    @router.post("/api/mobile/v1/management/renewals/{request_id}/terms", include_in_schema=False)
    def management_terms(
        request_id: UUID,
        body: ManagementRenewalTermsBody,
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
            permission="renewal.manage",
            permission_error="Management renewal permission is required.",
        )
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                row = _renewal_row(cursor, request_id=request_id)
                if row["status"] != "pending":
                    raise HTTPException(status_code=409, detail={"code": "renewal_not_pending", "message": "This renewal is no longer pending."})
                if row["collector_recommendation"] is None:
                    raise HTTPException(status_code=409, detail={"code": "collector_recommendation_required", "message": "Wait for the permanently assigned Collector recommendation first."})
                if body.decision == "rejected":
                    if len(body.review_note) < 3:
                        raise HTTPException(status_code=422, detail={"code": "renewal_rejection_reason_required", "message": "A Management rejection reason is required."})
                    cursor.execute(
                        """
                        update lending.client_renewal_requests
                        set status='rejected', reviewed_by_user_id=%s, review_note=%s,
                            reviewed_at=now(), updated_at=now()
                        where id=%s
                        """,
                        (actor.user_id, body.review_note, request_id),
                    )
                else:
                    if body.approved_principal is None:
                        raise HTTPException(status_code=422, detail={"code": "approved_principal_required", "message": "Management must set the approved new principal."})
                    if row["collector_recommendation"] == "do_not_recommend" and len(body.override_reason) < 3:
                        raise HTTPException(status_code=422, detail={"code": "renewal_override_reason_required", "message": "Management override reason is required when approving against the Collector recommendation."})
                    cursor.execute("delete from lending.renewal_required_signers where renewal_request_id=%s", (request_id,))
                    for signer in body.signers:
                        cursor.execute(
                            """
                            insert into lending.renewal_required_signers (
                                renewal_request_id, party_role, full_name, user_id,
                                government_id_verified_at, selfie_verified_at
                            ) values (%s,%s,%s,%s,
                                case when %s then now() else null end,
                                case when %s then now() else null end)
                            """,
                            (request_id, signer.party_role, signer.full_name.strip(), signer.user_id, signer.government_id_verified, signer.selfie_verified),
                        )
                    required_ready = bool(body.signers) and all(
                        signer.user_id is not None and signer.government_id_verified and signer.selfie_verified
                        for signer in body.signers
                    )
                    office_required = body.office_processing_required or any(signer.user_id is None for signer in body.signers)
                    signer_status = "office_required" if office_required else ("ready" if required_ready else "pending")
                    cursor.execute(
                        """
                        update lending.client_renewal_requests
                        set status='approved', approved_principal=%s,
                            management_override_reason=%s, reviewed_by_user_id=%s,
                            review_note=%s, reviewed_at=now(),
                            signer_readiness_status=%s, office_processing_required=%s,
                            updated_at=now()
                        where id=%s
                        """,
                        (body.approved_principal, body.override_reason, actor.user_id, body.review_note, signer_status, office_required, request_id),
                    )
                _audit(cursor, actor_user_id=actor.user_id, action=f"renewal.management.{body.decision}", request_id=request_id, details=body.review_note)
                data = _payload(cursor, _renewal_row(cursor, request_id=request_id))
        return {"success": True, "data": {"request": data}}

    @router.post("/api/v1/client/renewals/{request_id}/decision")
    @router.post("/api/mobile/v1/client/renewals/{request_id}/decision", include_in_schema=False)
    def client_decision(
        request_id: UUID,
        body: ClientRenewalDecisionBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
    ) -> dict[str, object]:
        actor = authenticated_device_context(authorization=authorization, device_identifier=x_device_id, auth=auth, accounts=accounts)
        if "client" not in actor.roles:
            raise HTTPException(status_code=403, detail={"code": "client_role_required", "message": "Only the borrower can accept or decline the approved renewal."})
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                row = _renewal_row(cursor, request_id=request_id)
                cursor.execute("select 1 from lending.clients where id=%s and user_id=%s", (row["client_id"], actor.user_id))
                if cursor.fetchone() is None:
                    raise HTTPException(status_code=403, detail={"code": "renewal_borrower_required", "message": "This renewal does not belong to your borrower account."})
                if row["status"] != "approved":
                    raise HTTPException(status_code=409, detail={"code": "renewal_not_approved", "message": "Management must approve terms before client consent."})
                cursor.execute("update lending.client_renewal_requests set client_decision=%s, client_decided_at=now(), updated_at=now() where id=%s", (body.decision, request_id))
                _audit(cursor, actor_user_id=actor.user_id, action=f"renewal.client.{body.decision}", request_id=request_id)
                data = _payload(cursor, _renewal_row(cursor, request_id=request_id))
        return {"success": True, "data": {"request": data}}

    @router.post("/api/v1/management/renewals/{request_id}/release-to-collector")
    @router.post("/api/mobile/v1/management/renewals/{request_id}/release-to-collector", include_in_schema=False)
    def management_release_to_collector(
        request_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
    ) -> dict[str, object]:
        actor = authenticated_device_context(authorization=authorization, device_identifier=x_device_id, auth=auth, accounts=accounts, permission="renewal.manage", permission_error="Management renewal permission is required.")
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                row = _renewal_row(cursor, request_id=request_id)
                if row["status"] != "approved" or row["client_decision"] != "accepted":
                    raise HTTPException(status_code=409, detail={"code": "renewal_client_acceptance_required", "message": "The client must Accept & Continue before cash release."})
                if row["office_processing_required"] or row["signer_readiness_status"] != "ready":
                    raise HTTPException(status_code=409, detail={"code": "renewal_signers_not_ready", "message": "All required remote signers must have their own app and complete identity verification/signing, otherwise process at the office."})
                approved = Decimal(row["approved_principal"] or 0)
                offset = Decimal(row["remaining_balance"] or 0).quantize(Decimal("0.01"))
                net = (approved - offset).quantize(Decimal("0.01"))
                if net < 0:
                    raise HTTPException(status_code=409, detail={"code": "renewal_net_release_negative", "message": "Approved principal is below the remaining old-loan balance."})
                cursor.execute(
                    """
                    update lending.client_renewal_requests
                    set renewal_offset_amount=%s, net_release_amount=%s,
                        amount_locked_at=now(), cash_released_by_user_id=%s,
                        cash_released_to_collector_at=now(),
                        activation_status='released_pending_management', updated_at=now()
                    where id=%s and amount_locked_at is null
                    """,
                    (offset, net, actor.user_id, request_id),
                )
                if cursor.rowcount != 1:
                    raise HTTPException(status_code=409, detail={"code": "renewal_amount_already_locked", "message": "Renewal cash amount is already locked."})
                _audit(cursor, actor_user_id=actor.user_id, action="renewal.cash.released_to_collector", request_id=request_id, details=f"offset={offset};net={net}")
                data = _payload(cursor, _renewal_row(cursor, request_id=request_id))
        return {"success": True, "data": {"request": data}}

    def _collector_cash_action(request_id: UUID, actor_user_id: UUID, action: str):
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                row = _renewal_row(cursor, request_id=request_id)
                _assert_assigned(row, actor_user_id)
                if action == "received":
                    if row["cash_released_to_collector_at"] is None:
                        raise HTTPException(status_code=409, detail={"code": "renewal_cash_not_released", "message": "Management has not released the locked cash amount to you yet."})
                    cursor.execute("update lending.client_renewal_requests set collector_cash_received_at=coalesce(collector_cash_received_at, now()), updated_at=now() where id=%s", (request_id,))
                else:
                    if row["collector_cash_received_at"] is None:
                        raise HTTPException(status_code=409, detail={"code": "renewal_cash_not_received", "message": "Confirm Cash Received from Management first."})
                    cursor.execute("update lending.client_renewal_requests set cash_given_to_client_at=coalesce(cash_given_to_client_at, now()), updated_at=now() where id=%s", (request_id,))
                _audit(cursor, actor_user_id=actor_user_id, action=f"renewal.cash.collector_{action}", request_id=request_id)
                return _payload(cursor, _renewal_row(cursor, request_id=request_id))

    @router.post("/api/v1/collector/renewals/{request_id}/cash-received")
    @router.post("/api/mobile/v1/collector/renewals/{request_id}/cash-received", include_in_schema=False)
    def collector_cash_received(
        request_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
    ) -> dict[str, object]:
        actor = authenticated_device_context(authorization=authorization, device_identifier=x_device_id, auth=auth, accounts=accounts, permission="renewal.cash_custody.assigned", permission_error="Assigned Collector renewal cash permission is required.")
        return {"success": True, "data": {"request": _collector_cash_action(request_id, actor.user_id, "received")}}

    @router.post("/api/v1/collector/renewals/{request_id}/cash-given")
    @router.post("/api/mobile/v1/collector/renewals/{request_id}/cash-given", include_in_schema=False)
    def collector_cash_given(
        request_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
    ) -> dict[str, object]:
        actor = authenticated_device_context(authorization=authorization, device_identifier=x_device_id, auth=auth, accounts=accounts, permission="renewal.cash_custody.assigned", permission_error="Assigned Collector renewal cash permission is required.")
        return {"success": True, "data": {"request": _collector_cash_action(request_id, actor.user_id, "given")}}

    @router.post("/api/v1/collector/renewals/{request_id}/handover-photo")
    @router.post("/api/mobile/v1/collector/renewals/{request_id}/handover-photo", include_in_schema=False)
    async def upload_handover_photo(
        request_id: UUID,
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        x_file_name: str | None = Header(default=None, alias="X-File-Name"),
        content_type: str | None = Header(default=None, alias="Content-Type"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
    ) -> dict[str, object]:
        actor = authenticated_device_context(authorization=authorization, device_identifier=x_device_id, auth=auth, accounts=accounts, permission="renewal.cash_custody.assigned", permission_error="Assigned Collector renewal cash permission is required.")
        data = await request.body()
        actual_type = (content_type or "").split(";", 1)[0].strip().lower()
        if actual_type not in ALLOWED_PROOF_TYPES or not data or len(data) > MAX_PROOF_BYTES:
            raise HTTPException(status_code=422, detail={"code": "renewal_proof_invalid", "message": "Upload a JPEG, PNG or WebP handover photo up to 8 MB."})
        digest = hashlib.sha256(data).hexdigest()
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                row = _renewal_row(cursor, request_id=request_id)
                _assert_assigned(row, actor.user_id)
                if row["cash_given_to_client_at"] is None:
                    raise HTTPException(status_code=409, detail={"code": "renewal_cash_not_given", "message": "Confirm Cash Given to Client before uploading handover proof."})
                cursor.execute("select coalesce(max(version),0)+1 as next_version from lending.renewal_handover_photos where renewal_request_id=%s", (request_id,))
                version = int(cursor.fetchone()["next_version"])
                cursor.execute(
                    """
                    insert into lending.renewal_handover_photos (
                        renewal_request_id, version, uploaded_by_user_id,
                        original_filename, content_type, byte_size, sha256_hex, photo_data
                    ) values (%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (request_id, version, actor.user_id, x_file_name or "renewal-handover.jpg", actual_type, len(data), digest, data),
                )
                cursor.execute("update lending.client_renewal_requests set handover_proof_status='under_review', updated_at=now() where id=%s", (request_id,))
                _audit(cursor, actor_user_id=actor.user_id, action="renewal.handover_proof.submitted", request_id=request_id, details=f"version={version};sha256={digest}")
        return {"success": True, "data": {"version": version, "sha256": digest, "status": "under_review"}}

    @router.get("/api/v1/renewals/{request_id}/handover-photo")
    @router.get("/api/mobile/v1/renewals/{request_id}/handover-photo", include_in_schema=False)
    def view_handover_photo(
        request_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
    ) -> Response:
        actor = authenticated_device_context(authorization=authorization, device_identifier=x_device_id, auth=auth, accounts=accounts)
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                row = _renewal_row(cursor, request_id=request_id)
                is_client = False
                if "client" in actor.roles:
                    cursor.execute("select 1 from lending.clients where id=%s and user_id=%s", (row["client_id"], actor.user_id))
                    is_client = cursor.fetchone() is not None
                is_assigned = row["assigned_collector_user_id"] == actor.user_id
                is_management = "renewal.manage" in actor.permissions
                if not (is_client or is_assigned or is_management):
                    raise HTTPException(status_code=403, detail={"code": "renewal_proof_forbidden", "message": "You cannot view this renewal handover proof."})
                cursor.execute("select original_filename, content_type, photo_data, version, sha256_hex from lending.renewal_handover_photos where renewal_request_id=%s order by version desc limit 1", (request_id,))
                photo = cursor.fetchone()
                if photo is None:
                    raise HTTPException(status_code=404, detail={"code": "renewal_proof_not_found", "message": "No renewal handover photo has been submitted."})
        safe_name = str(photo["original_filename"]).replace('"', "").replace("\r", "").replace("\n", "")
        return Response(content=bytes(photo["photo_data"]), media_type=photo["content_type"], headers={"Cache-Control": "private, no-store", "Content-Disposition": f'inline; filename="{safe_name}"', "X-Photo-Version": str(photo["version"]), "X-Photo-SHA256": str(photo["sha256_hex"])})

    @router.post("/api/v1/client/renewals/{request_id}/cash-confirm")
    @router.post("/api/mobile/v1/client/renewals/{request_id}/cash-confirm", include_in_schema=False)
    def client_cash_confirm(
        request_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
    ) -> dict[str, object]:
        actor = authenticated_device_context(authorization=authorization, device_identifier=x_device_id, auth=auth, accounts=accounts)
        if "client" not in actor.roles:
            raise HTTPException(status_code=403, detail={"code": "client_role_required", "message": "Only the borrower can confirm cash received."})
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                row = _renewal_row(cursor, request_id=request_id)
                cursor.execute("select 1 from lending.clients where id=%s and user_id=%s", (row["client_id"], actor.user_id))
                if cursor.fetchone() is None:
                    raise HTTPException(status_code=403, detail={"code": "renewal_borrower_required", "message": "This renewal does not belong to your borrower account."})
                if row["cash_given_to_client_at"] is None:
                    raise HTTPException(status_code=409, detail={"code": "renewal_cash_not_given", "message": "Collector has not confirmed cash handover yet."})
                cursor.execute("update lending.client_renewal_requests set client_cash_confirmed_at=coalesce(client_cash_confirmed_at, now()), updated_at=now() where id=%s", (request_id,))
                _audit(cursor, actor_user_id=actor.user_id, action="renewal.cash.client_confirmed", request_id=request_id)
                data = _payload(cursor, _renewal_row(cursor, request_id=request_id))
        return {"success": True, "data": {"request": data}}

    @router.post("/api/v1/management/renewals/{request_id}/proof-review")
    @router.post("/api/mobile/v1/management/renewals/{request_id}/proof-review", include_in_schema=False)
    def management_proof_review(
        request_id: UUID,
        body: ManagementProofReviewBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
    ) -> dict[str, object]:
        actor = authenticated_device_context(authorization=authorization, device_identifier=x_device_id, auth=auth, accounts=accounts, permission="renewal.manage", permission_error="Management renewal permission is required.")
        mapped = {"approved": "approved", "request_new_photo": "correction_required", "flag_for_review": "flagged"}[body.decision]
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                row = _renewal_row(cursor, request_id=request_id)
                if row["handover_proof_status"] not in {"under_review", "correction_required", "flagged"}:
                    raise HTTPException(status_code=409, detail={"code": "renewal_proof_not_reviewable", "message": "There is no submitted handover proof ready for review."})
                cursor.execute("update lending.client_renewal_requests set handover_proof_status=%s, updated_at=now() where id=%s", (mapped, request_id))
                _audit(cursor, actor_user_id=actor.user_id, action=f"renewal.handover_proof.{mapped}", request_id=request_id, details=body.note)
                data = _payload(cursor, _renewal_row(cursor, request_id=request_id))
        return {"success": True, "data": {"request": data}}

    return router

"""Contract 1: decimal text, explicit instants, bounded typed treasury commands."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StringConstraints,
    TypeAdapter,
    model_validator,
)
from spina_mobile_collections.contracts import PaymentAllocationIntent

from .combined_collection_api import (
    CombinedExtraAllocationChoice,
    CombinedPastDueFollowup,
)


def exact_money(value: str) -> str:
    # NUMERIC(18,2) is the existing protected source's storage ceiling.
    if Decimal(value) > Decimal("9999999999999999.99"):
        raise ValueError("Amount exceeds the exact PHP storage limit.")
    return value


Money = Annotated[
    str,
    StringConstraints(pattern=r"^(0|[1-9][0-9]{0,15})\.[0-9]{2}$"),
    AfterValidator(exact_money),
]


def positive(value: str) -> str:
    if Decimal(value) <= 0:
        raise ValueError("A movement or payment amount must be positive.")
    return value


PositiveMoney = Annotated[Money, AfterValidator(positive)]
Version = Annotated[StrictInt, Field(ge=1)]
Text = Annotated[
    str, StringConstraints(min_length=1, max_length=1000, strip_whitespace=True)
]
Reference = Annotated[
    str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)
]
Digest = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
ContextKind = Literal["owner_operations", "corporate_legal", "synthetic"]
Permission = Literal[
    "treasury.account.manage",
    "treasury.view",
    "treasury.proof.submit.assigned",
    "treasury.proof.review",
    "treasury.receipt.verify",
    "treasury.payment.apply",
    "treasury.disbursement.record",
    "treasury.transfer.record",
    "treasury.reconcile",
    "treasury.adjust",
    "treasury.collector_surplus.receive",
    "treasury.collector_surplus.resolve",
    "treasury.collector_surplus.settle",
    "treasury.collector_surplus.view",
]


def aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("A timezone-aware instant is required.")
    return value


Instant = Annotated[datetime, AfterValidator(aware)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Command(StrictModel):
    request_id: UUID
    account_id: UUID
    expected_version: Version


class AccountConfigure(Command):
    action: Literal["account_configure"]
    expected_version: Annotated[StrictInt, Field(ge=0)]
    ledger_context_id: UUID
    context: ContextKind
    kind: Literal["physical_cash", "gcash", "bank", "transit"]
    alias: Annotated[
        str, StringConstraints(min_length=1, max_length=120, strip_whitespace=True)
    ]
    ownership: Literal["owner_personal", "owner_business", "corporate", "synthetic"]
    custodian_user_id: UUID
    masked_identifier: Annotated[str, StringConstraints(max_length=100)] = ""
    payment_instructions: Annotated[str, StringConstraints(max_length=1000)] = ""
    designated_receiving: StrictBool = False
    active: StrictBool = True


class AccountGrant(Command):
    action: Literal["account_grant"]
    user_id: UUID
    permissions: list[Permission] = Field(max_length=14)
    private_history: StrictBool = False
    enabled: StrictBool = True


class OpeningPrepare(Command):
    action: Literal["opening_prepare"]
    cutoff: Instant
    amount: Money
    evidence_id: UUID
    reason: Text
    personal_amount: Money | None = None
    third_party_amount: Money | None = None
    transit_amount: Money | None = None


class OpeningActivate(Command):
    action: Literal["opening_activate"]
    opening_id: UUID
    opening_version: Version
    confirmed: Literal[True]
    reason: Text


class ClaimMetadata(StrictModel):
    request_id: UUID
    account_id: UUID
    account_version: Version
    client_id: UUID
    loan_ids: list[UUID] = Field(min_length=1, max_length=2)
    amount: PositiveMoney
    reference: Reference
    claimed_at: Instant
    sender_note: Annotated[str, StringConstraints(max_length=1000)] = ""
    expected_version: Version | None = None


class ClaimReview(Command):
    action: Literal["claim_review"]
    claim_id: UUID
    claim_version: Version
    decision: Literal["reviewed", "correction_required", "rejected"]
    reason: Text


class ReceiptVerify(Command):
    action: Literal["receipt_verify"]
    client_id: UUID
    claim_id: UUID | None = None
    claim_version: Version | None = None
    amount: PositiveMoney
    provider: Reference
    reference: Reference
    effective_at: Instant
    evidence_id: UUID
    recipient_attestation: Text
    reason: Text = "Manually verified recipient-side transaction."


class Allocation(StrictModel):
    loan_id: UUID
    expected_version: Version
    amount: PositiveMoney
    covered_dates: list[date] = Field(default_factory=list, max_length=366)
    intent: Literal["scheduled", "advance", "extra_principal"] = "scheduled"


class LoanChoice(StrictModel):
    loan_id: UUID
    expected_version: Annotated[StrictInt, Field(ge=0)]


class ApplicationInput(StrictModel):
    mode: Literal["single", "combined"]
    total_amount: PositiveMoney
    loans: list[LoanChoice] = Field(min_length=1, max_length=2)
    intent: PaymentAllocationIntent = PaymentAllocationIntent.SCHEDULED
    covered_dates: list[date] = Field(default_factory=list, max_length=366)
    extra_choice: CombinedExtraAllocationChoice | None = None
    regular_past_due_followup: CombinedPastDueFollowup | None = None
    effective_date: date


class AllocationPreview(ApplicationInput):
    expected_version: Version


class ReceiptApply(Command, ApplicationInput):
    action: Literal["receipt_apply"]
    receipt_id: UUID
    digest: Digest


class DisbursementRecord(Command):
    action: Literal["disbursement_record"]
    amount: PositiveMoney
    fee: Money = "0.00"
    provider: Reference
    reference: Reference | None
    effective_at: Instant
    evidence_id: UUID
    recipient_attestation: Text
    direction: Literal["credit", "debit"] = "debit"
    purpose: Literal[
        "unclassified",
        "personal",
        "loan_release",
        "renewal",
        "payroll",
        "salary_advance",
        "expense",
        "refund",
        "owner_contribution",
        "owner_withdrawal",
        "deposit",
        "collector_surplus_return",
        "collector_custody_exception_return",
    ]
    source_id: UUID | None = None
    source_version: Version | None = None
    payee_id: UUID | None = None
    destination_confirmed: StrictBool = False
    destination_evidence_id: UUID | None = None
    payee_acknowledgment: Text | None = None
    receipt_id: UUID | None = None
    reason: Text


class TransferRecord(Command):
    action: Literal["transfer_record"]
    transfer_id: UUID
    leg: Literal["source", "destination"]
    other_account_id: UUID
    other_account_version: Version
    amount: PositiveMoney
    fee: Money = "0.00"
    provider: Reference
    reference: Reference
    effective_at: Instant
    evidence_id: UUID
    recipient_attestation: Text
    reason: Text


class MovementClassify(Command):
    action: Literal["movement_classify"]
    event_id: UUID
    event_version: Version
    classification: Literal[
        "personal", "owner_contribution", "owner_withdrawal", "unclassified"
    ]
    reason: Text


class MovementCorrect(Command):
    action: Literal["movement_correct"]
    event_id: UUID
    event_version: Version
    evidence_id: UUID
    reason: Text
    correction: Literal["false_observation"]


class ReceiptApplicationReverse(Command):
    action: Literal["receipt_application_reverse"]
    receipt_id: UUID
    application_id: UUID
    reason: Text


class ReconciliationObserve(Command):
    action: Literal["reconciliation_observe"]
    reconciliation_id: UUID
    coverage_start: Instant
    cutoff: Instant
    actual_balance: Money
    evidence_id: UUID
    complete_history: StrictBool
    rows: list[ObservationRow] = Field(max_length=500)


class ObservationRow(StrictModel):
    id: UUID
    provider: Reference
    reference: Reference | None
    direction: Literal["credit", "debit"]
    amount: PositiveMoney
    effective_at: Instant


class ReconciliationMatch(Command):
    action: Literal["reconciliation_match"]
    reconciliation_id: UUID
    reconciliation_version: Version
    observation_id: UUID
    event_id: UUID
    component: Literal["total", "principal", "fee"] = "total"
    exception_reason: Text | None = None


class ReconciliationCloseFields(Command):
    reconciliation_id: UUID
    reconciliation_version: Version
    opening_id: UUID
    movement_watermark: Annotated[StrictInt, Field(ge=0)]
    reason: Text


class ReconciliationClose(ReconciliationCloseFields):
    action: Literal["reconciliation_close"]


class ReconciliationSupersede(ReconciliationCloseFields):
    action: Literal["reconciliation_supersede"]
    prior_reconciliation_id: UUID


class RetainedCashSelection(StrictModel):
    retained_exception_id: UUID | None = None
    retained_exception_version: Version | None = None

    @model_validator(mode="after")
    def paired_retained_selection(self):
        if (self.retained_exception_id is None) != (
            self.retained_exception_version is None
        ):
            raise ValueError(
                "Select the retained cash record and its exact version together."
            )
        return self


class SettlementPreview(RetainedCashSelection):
    account_id: UUID
    expected_version: Version
    credit_application_id: UUID | None = None
    credit_application_version: Version | None = None


class CollectorCountRecord(Command, RetainedCashSelection):
    action: Literal["collector_count_record"]
    remittance_id: UUID
    source_digest: Digest
    counted_amount: Money
    counted_at: Instant
    evidence_id: UUID
    recipient_attestation: Text
    review_acknowledged: StrictBool


class CollectorCountAccept(Command):
    action: Literal["collector_count_accept"]
    count_id: UUID
    count_version: Version
    source_digest: Digest
    physical_receipt_acknowledged: StrictBool
    credit_application_id: UUID | None = None
    credit_application_version: Version | None = None


class CollectorSurplusRecognize(Command):
    source_review_acknowledged: StrictBool
    action: Literal["collector_surplus_recognize"]
    case_id: UUID
    case_version: Version
    amount: PositiveMoney
    source_digest: Digest
    evidence_id: UUID
    reason: Text


class Destination(StrictModel):
    kind: Literal["physical_cash", "gcash", "bank"]
    recipient_reference: Reference | None

    @model_validator(mode="after")
    def method_reference(self):
        if (self.kind == "physical_cash") != (self.recipient_reference is None):
            raise ValueError(
                "Cash has no wallet identifier; wallet/bank requires a private recipient reference."
            )
        return self


class OwnCreditCommand(StrictModel):
    request_id: UUID
    credit_id: UUID
    credit_version: Version


class CollectorSurplusReturnRequest(OwnCreditCommand):
    action: Literal["collector_surplus_return_request"]
    amount: PositiveMoney
    destination: Destination
    reason: Text


class CollectorSurplusApplicationRequest(OwnCreditCommand):
    action: Literal["collector_surplus_application_request"]
    remittance_id: UUID
    source_digest: Digest
    amount: PositiveMoney
    reason: Text


class AcknowledgmentFields(StrictModel):
    action_id: UUID
    action_version: Version
    event_id: UUID
    event_version: Version
    reviewed_amount: PositiveMoney
    confirmation: Literal["received", "not_received"]
    acknowledged_at: Instant
    reason: Text


class CollectorSurplusReturnAcknowledge(OwnCreditCommand, AcknowledgmentFields):
    action: Literal["collector_surplus_return_acknowledge"]


class CollectorSurplusReturnPrepare(Command):
    action: Literal["collector_surplus_return_prepare"]
    credit_id: UUID
    credit_version: Version
    collector_request_id: UUID
    collector_request_version: Version
    amount: PositiveMoney
    destination: Destination
    evidence_id: UUID
    reason: Text


class CollectorSurplusApplicationPrepare(Command):
    action: Literal["collector_surplus_application_prepare"]
    credit_id: UUID
    credit_version: Version
    collector_request_id: UUID
    collector_request_version: Version
    remittance_id: UUID
    source_digest: Digest
    amount: PositiveMoney
    evidence_id: UUID
    reason: Text


class CollectorSurplusReturnRecord(Command):
    action: Literal["collector_surplus_return_record"]
    action_id: UUID
    action_version: Version
    event_id: UUID
    event_version: Version
    acknowledgment_id: UUID
    acknowledgment_version: Version
    reason: Text


class CollectorSurplusReturnReverse(Command):
    action: Literal["collector_surplus_return_reverse"]
    action_id: UUID
    action_version: Version
    amount: PositiveMoney
    provider: Reference
    reference: Reference
    effective_at: Instant
    evidence_id: UUID
    recipient_attestation: Text
    reason: Text


class CollectorSurplusActionCancel(Command):
    action: Literal["collector_surplus_action_cancel"]
    action_id: UUID
    action_version: Version
    evidence_id: UUID
    reason: Text


class CollectorSurplusResolveSource(Command):
    action: Literal["collector_surplus_resolve_source"]
    case_id: UUID | None = None
    case_version: Version | None = None
    credit_id: UUID | None = None
    credit_version: Version | None = None
    source_id: UUID
    source_digest: Digest
    amount: PositiveMoney
    evidence_id: UUID
    reason: Text

    @model_validator(mode="after")
    def one_target(self):
        if (self.case_id is None) == (self.credit_id is None):
            raise ValueError("Select exactly one case or credit.")
        if (
            self.case_id
            and self.case_version is None
            or self.credit_id
            and self.credit_version is None
        ):
            raise ValueError("Exact target version is required.")
        return self


class CollectorSurplusOpeningPrepare(Command):
    anchor_kind: Literal["credit", "pending_excess"] = "credit"
    action: Literal["collector_surplus_opening_prepare"]
    collector_user_id: UUID
    opening_id: UUID
    opening_version: Version
    amount: PositiveMoney
    evidence_id: UUID
    overlap_review_acknowledged: StrictBool
    reason: Text


class CollectorSurplusOpeningActivate(Command):
    action: Literal["collector_surplus_opening_activate"]
    anchor_id: UUID
    anchor_version: Version
    reason: Text


class CollectorCustodyExceptionRecord(Command):
    action: Literal["collector_custody_exception_record"]
    count_id: UUID
    count_version: Version
    source_digest: Digest
    retained_amount: PositiveMoney
    retained_at: Instant
    evidence_id: UUID
    holder_attestation: Text
    reason: Text


class CollectorCustodyExceptionReturnPrepare(Command):
    action: Literal["collector_custody_exception_return_prepare"]
    exception_id: UUID
    exception_version: Version
    amount: PositiveMoney
    evidence_id: UUID
    reason: Text


class CollectorCustodyExceptionReturnAcknowledge(AcknowledgmentFields):
    action: Literal["collector_custody_exception_return_acknowledge"]
    request_id: UUID
    exception_id: UUID
    exception_version: Version


SurplusCommand = Annotated[
    CollectorCountRecord
    | CollectorCountAccept
    | CollectorSurplusRecognize
    | CollectorSurplusReturnRequest
    | CollectorSurplusApplicationRequest
    | CollectorSurplusReturnAcknowledge
    | CollectorSurplusReturnPrepare
    | CollectorSurplusApplicationPrepare
    | CollectorSurplusReturnRecord
    | CollectorSurplusReturnReverse
    | CollectorSurplusActionCancel
    | CollectorSurplusResolveSource
    | CollectorSurplusOpeningPrepare
    | CollectorSurplusOpeningActivate
    | CollectorCustodyExceptionRecord
    | CollectorCustodyExceptionReturnPrepare
    | CollectorCustodyExceptionReturnAcknowledge,
    Field(discriminator="action"),
]


TreasuryCommand = Annotated[
    AccountConfigure
    | AccountGrant
    | OpeningPrepare
    | OpeningActivate
    | ClaimReview
    | ReceiptVerify
    | ReceiptApply
    | DisbursementRecord
    | TransferRecord
    | MovementClassify
    | MovementCorrect
    | ReceiptApplicationReverse
    | ReconciliationObserve
    | ReconciliationMatch
    | ReconciliationClose
    | ReconciliationSupersede
    | SurplusCommand,
    Field(discriminator="action"),
]
COMMAND_ADAPTER = TypeAdapter(TreasuryCommand)


def command_hash(command: BaseModel) -> str:
    payload = command.model_dump(mode="json")
    # Preserve durable retries saved before this optional count extension existed.
    if (
        payload.get("action") == "collector_count_record"
        and payload.get("retained_exception_id") is None
    ):
        payload.pop("retained_exception_id", None)
        payload.pop("retained_exception_version", None)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


class TreasuryResult(StrictModel):
    contract_version: Literal[1] = 1
    request_id: UUID
    action: str
    status: Literal["saved", "blocked"]
    target_id: UUID
    version: Version
    result: dict

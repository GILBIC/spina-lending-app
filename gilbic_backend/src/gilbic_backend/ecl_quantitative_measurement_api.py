from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .ecl_quantitative_measurement_repository import (
    EclQuantitativeMeasurement,
    EclQuantitativeMeasurementBlocked,
    EclQuantitativeMeasurementError,
    EclQuantitativeMeasurementNotFound,
    EclQuantitativeMeasurementQueueItem,
    PostgresEclQuantitativeMeasurementRepository,
)
from .request_auth import authenticated_device_context


MEASURE_PERMISSION = "accounting.ecl.measurement.review"


class StrictEclMeasurementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExpectedCashFlowRequest(StrictEclMeasurementRequest):
    cash_date: date
    amount: Decimal = Field(gt=0)

    @field_validator("amount")
    @classmethod
    def exact_currency_cents(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("Expected cash-flow amounts must use exact currency-cent precision.")
        return value


class EclScenarioRequest(StrictEclMeasurementRequest):
    scenario_key: str = Field(min_length=1, max_length=120)
    probability: Decimal = Field(gt=0, le=1)
    evidence_reference: str = Field(min_length=1, max_length=1000)
    management_rationale: str = Field(min_length=20, max_length=4000)
    forward_evidence_ids: list[UUID] = Field(min_length=1, max_length=50)
    expected_cash_flows: list[ExpectedCashFlowRequest] = Field(max_length=1000)

    @field_validator("scenario_key", "evidence_reference", "management_rationale")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("probability")
    @classmethod
    def exact_probability_precision(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.000000000001")):
            raise ValueError("Scenario probability supports at most 12 decimal places.")
        return value

    @model_validator(mode="after")
    def reject_duplicate_evidence_and_cash_dates(self):
        if len(set(self.forward_evidence_ids)) != len(self.forward_evidence_ids):
            raise ValueError("Duplicate forward-looking evidence ids are not allowed in a scenario.")
        dates = [item.cash_date for item in self.expected_cash_flows]
        if len(set(dates)) != len(dates):
            raise ValueError("Expected cash-flow dates must be unique within a scenario.")
        return self


class RecordEclMeasurementRequest(StrictEclMeasurementRequest):
    measurement_date: date
    scenarios: list[EclScenarioRequest] = Field(min_length=2, max_length=20)
    review_rationale: str = Field(min_length=20, max_length=4000)

    @field_validator("review_rationale")
    @classmethod
    def normalize_rationale(cls, value: str) -> str:
        return " ".join(value.split())

    @model_validator(mode="after")
    def validate_scenarios(self):
        keys = [scenario.scenario_key for scenario in self.scenarios]
        if len(set(keys)) != len(keys):
            raise ValueError("Scenario keys must be unique.")
        total = sum((scenario.probability for scenario in self.scenarios), Decimal("0"))
        if total != Decimal("1.000000000000"):
            raise ValueError("Scenario probabilities must sum exactly to 1.000000000000.")
        for scenario in self.scenarios:
            if any(flow.cash_date < self.measurement_date for flow in scenario.expected_cash_flows):
                raise ValueError("Expected cash-flow dates cannot precede the measurement date.")
        return self


def ecl_quantitative_measurement_repository_dependency() -> (
    PostgresEclQuantitativeMeasurementRepository
):
    return PostgresEclQuantitativeMeasurementRepository()


def _money(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def _queue_payload(item: EclQuantitativeMeasurementQueueItem) -> dict[str, object]:
    return {
        "loan_id": str(item.loan_id),
        "loan_number": item.loan_number,
        "loan_status": item.loan_status,
        "loan_type_code": item.loan_type_code,
        "loan_type_name": item.loan_type_name,
        "calculation_mode": item.calculation_mode,
        "schedule_id": str(item.schedule_id) if item.schedule_id else None,
        "schedule_version": item.schedule_version,
        "contract_reference": item.contract_reference,
        "stage_label": item.stage_label,
        "review_id": item.review_id,
        "review_version": item.review_version,
        "blocker_codes": list(item.blocker_codes),
        "blockers": list(item.blockers),
        "quantitative_input_ready": item.quantitative_input_ready,
        "measurement_id": str(item.measurement_id) if item.measurement_id else None,
        "measurement_version": item.measurement_version,
        "measurement_date": item.measurement_date.isoformat() if item.measurement_date else None,
        "loss_horizon": item.loss_horizon,
        "calculation_digest": item.calculation_digest,
        "measurement_forward_evidence_current": item.measurement_forward_evidence_current,
        "measurement_status": item.measurement_status,
        "authoritative_ecl_amount": _money(item.authoritative_ecl_amount),
        "read_only_ecl_calculation_enabled": item.read_only_ecl_calculation_enabled,
        "account_1190_posting_enabled": item.account_1190_posting_enabled,
        "automatic_source_posting": item.automatic_source_posting,
    }


def _measurement_payload(item: EclQuantitativeMeasurement) -> dict[str, object]:
    return {
        "id": str(item.id),
        "loan_id": str(item.loan_id),
        "measurement_version": item.measurement_version,
        "measurement_date": item.measurement_date.isoformat(),
        "stage_label": item.stage_label,
        "loss_horizon": item.loss_horizon,
        "schedule_id": str(item.schedule_id),
        "schedule_version": item.schedule_version,
        "contract_reference": item.contract_reference,
        "label_review_id": item.label_review_id,
        "label_review_version": item.label_review_version,
        "original_eir_source_key": item.original_eir_source_key,
        "original_eir_policy_version": item.original_eir_policy_version,
        "original_daily_eir": format(item.original_daily_eir, "f"),
        "original_initial_gross_carrying_amount": _money(
            item.original_initial_gross_carrying_amount
        ),
        "forward_evidence_ids": [str(value) for value in item.forward_evidence_ids],
        "input_snapshot": item.input_snapshot,
        "contractual_cash_flow_snapshot": list(item.contractual_cash_flow_snapshot),
        "scenario_snapshot": list(item.scenario_snapshot),
        "scenario_count": item.scenario_count,
        "probability_total": format(item.probability_total, "f"),
        "contractual_cash_flow_pv": format(item.contractual_cash_flow_pv, "f"),
        "weighted_expected_cash_shortfall": format(
            item.weighted_expected_cash_shortfall, "f"
        ),
        "ecl_amount": _money(item.ecl_amount),
        "calculation_policy_version": item.calculation_policy_version,
        "discount_basis": item.discount_basis,
        "rounding_policy": item.rounding_policy,
        "calculation_digest": item.calculation_digest,
        "review_rationale": item.review_rationale,
        "reviewed_by_user_id": str(item.reviewed_by_user_id),
        "reviewed_at": item.reviewed_at.isoformat(),
        "read_only_ecl_calculation_enabled": True,
        "account_1190_posting_enabled": False,
        "automatic_source_posting": False,
    }


def _exception(error: EclQuantitativeMeasurementError) -> HTTPException:
    if isinstance(error, EclQuantitativeMeasurementNotFound):
        status_code = 404
    elif isinstance(error, EclQuantitativeMeasurementBlocked):
        status_code = 409
    else:
        status_code = 500
    return HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    )


def _require_management(actor) -> None:
    if "management" not in actor.roles:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "management_role_required",
                "message": "Management access is required for quantitative ECL measurement.",
            },
        )


def _require_measure_permission(actor) -> None:
    _require_management(actor)
    if MEASURE_PERMISSION not in actor.permissions:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "quantitative_ecl_measurement_permission_required",
                "message": "Quantitative ECL measurement Management permission is required.",
            },
        )


def create_ecl_quantitative_measurement_router() -> APIRouter:
    router = APIRouter(tags=["management financial accounting"])

    @router.get(
        "/api/v1/management/financial-accounting/ecl-quantitative-measurements"
    )
    @router.get(
        "/api/mobile/v1/management/financial-accounting/ecl-quantitative-measurements",
        include_in_schema=False,
    )
    def list_measurements(
        status: Literal[
            "all",
            "input_blocked",
            "measurement_required",
            "new_measurement_required",
            "measured_read_only",
            "ready",
        ] = Query(default="all"),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        measurements: PostgresEclQuantitativeMeasurementRepository = Depends(
            ecl_quantitative_measurement_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_management(actor)
        items = measurements.list_queue(status=status, limit=limit, offset=offset)
        summary = measurements.summary()
        return {
            "success": True,
            "data": {
                "items": [_queue_payload(item) for item in items],
                "summary": {
                    **summary,
                    "authoritative_ecl_total": _money(summary["authoritative_ecl_total"]),
                },
                "filter": status,
                "limit": limit,
                "offset": offset,
                "measure_permission": MEASURE_PERMISSION in actor.permissions,
                "notice": (
                    "A3 is read-only quantitative ECL. Blocked loans expose no authoritative amount; "
                    "account 1190 posting and automatic source posting remain disabled."
                ),
            },
        }

    @router.post(
        "/api/v1/management/financial-accounting/ecl-quantitative-measurements/{loan_id}"
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/ecl-quantitative-measurements/{loan_id}",
        include_in_schema=False,
    )
    def record_measurement(
        loan_id: UUID,
        request: RecordEclMeasurementRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        measurements: PostgresEclQuantitativeMeasurementRepository = Depends(
            ecl_quantitative_measurement_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_measure_permission(actor)
        scenario_payloads: list[dict[str, object]] = []
        for scenario in request.scenarios:
            scenario_payloads.append(
                {
                    "scenario_key": scenario.scenario_key,
                    "probability": scenario.probability,
                    "evidence_reference": scenario.evidence_reference,
                    "management_rationale": scenario.management_rationale,
                    "forward_evidence_ids": scenario.forward_evidence_ids,
                    "expected_cash_flows": [
                        {"cash_date": flow.cash_date, "amount": flow.amount}
                        for flow in scenario.expected_cash_flows
                    ],
                }
            )
        try:
            item = measurements.record_measurement(
                loan_id=loan_id,
                measurement_date=request.measurement_date,
                scenarios=scenario_payloads,
                review_rationale=request.review_rationale,
                actor_user_id=actor.user_id,
            )
        except EclQuantitativeMeasurementError as error:
            raise _exception(error) from error
        return {"success": True, "data": _measurement_payload(item)}

    return router

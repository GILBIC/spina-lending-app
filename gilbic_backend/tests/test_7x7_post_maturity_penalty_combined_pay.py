from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from gilbic_backend import combined_collection_api
from gilbic_backend.collection_api import collection_actor_dependency
from gilbic_backend.combined_collection_api import create_combined_collection_router
from gilbic_backend.contract_schedule_registration_service import (
    register_verified_contract_schedule,
)
from gilbic_backend.seven_by_seven_collection_posting import (
    SEVEN_BY_SEVEN_MOBILE_SETTING,
)
from gilbic_backend.seven_by_seven_penalty_coordinator import (
    project_verified_seven_by_seven_penalty_state,
)
from gilbic_backend.seven_by_seven_signed_schedule import (
    generate_signed_seven_by_seven_schedule,
)
from spina_mobile_collections.contracts import ActorContext
from spina_mobile_collections.service import CONTRACT_VERSION


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

RELEASE_DATE = date(2097, 8, 1)
FIRST_DUE_DATE = RELEASE_DATE + timedelta(days=1)


@dataclass(frozen=True, slots=True)
class CombinedPenaltyCase:
    collector_id: UUID
    device_record_id: UUID
    installation_id: str
    client_id: UUID
    regular_loan_id: UUID
    seven_loan_id: UUID

    @property
    def actor(self) -> ActorContext:
        return ActorContext(
            account_id=str(self.collector_id),
            device_id=self.installation_id,
            registered_device_id=str(self.device_record_id),
            permissions=frozenset({"collection.create"}),
        )


def _connect() -> psycopg.Connection:
    assert DATABASE_URL is not None
    return psycopg.connect(DATABASE_URL)


def _setup_case() -> CombinedPenaltyCase:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:12]
    installation_id = f"p6-t6-combined-{suffix}"
    seven_settings = {
        "mobile_collections_enabled": True,
        "mobile_balance_mode": "direct_remaining_balance",
        SEVEN_BY_SEVEN_MOBILE_SETTING: True,
    }
    regular_settings = {
        "mobile_collections_enabled": True,
        "mobile_balance_mode": "direct_remaining_balance",
    }

    with _connect() as connection:
        collector_id = connection.execute(
            """
            insert into core.users (username, full_name, status)
            values (%s, %s, 'active') returning id
            """,
            (f"p6-t6-{suffix}", f"P6 Task 6 Collector {suffix}"),
        ).fetchone()[0]
        device_record_id = connection.execute(
            """
            insert into core.devices (
                user_id, device_identifier_hash, platform, app_version, status
            ) values (%s, %s, 'android', 'p6-task6-test', 'active')
            returning id
            """,
            (collector_id, f"hash-{suffix}"),
        ).fetchone()[0]
        client_id = connection.execute(
            """
            insert into lending.clients (client_code, full_name, area, status)
            values (%s, %s, %s, 'active') returning id
            """,
            (
                f"P6T6C-{suffix}",
                f"P6 Task 6 Combined Client {suffix}",
                f"P6 Task 6 Area {suffix}",
            ),
        ).fetchone()[0]
        regular_type_id = connection.execute(
            """
            insert into lending.loan_types (
                code, name, description, term_days, calculation_mode,
                daily_interest_per_1000, settings, is_active
            ) values (%s, %s, 'P6 Task 6 Regular', 120,
                      'fixed_daily', 0.00, %s, true)
            returning id
            """,
            (
                f"P6T6R-{suffix}",
                f"P6 Task 6 Regular {suffix}",
                Jsonb(regular_settings),
            ),
        ).fetchone()[0]
        seven_type_id = connection.execute(
            """
            insert into lending.loan_types (
                code, name, description, term_days, calculation_mode,
                daily_interest_per_1000, settings, is_active
            ) values (%s, %s, 'P6 Task 6 7x7', 120,
                      'seven_by_seven', 7.00, %s, true)
            returning id
            """,
            (
                f"P6T67-{suffix}",
                f"P6 Task 6 7x7 {suffix}",
                Jsonb(seven_settings),
            ),
        ).fetchone()[0]
        regular_loan_id = connection.execute(
            """
            insert into lending.loans (
                loan_number, client_id, loan_type_id, principal, daily_amount,
                date_released, due_date, status, created_by_user_id
            ) values (%s, %s, %s, 5000.00, 50.00, %s, %s, 'active', %s)
            returning id
            """,
            (
                f"P6T6RL-{suffix}",
                client_id,
                regular_type_id,
                RELEASE_DATE,
                RELEASE_DATE + timedelta(days=120),
                collector_id,
            ),
        ).fetchone()[0]
        seven_loan_id = connection.execute(
            """
            insert into lending.loans (
                loan_number, client_id, loan_type_id, principal, daily_amount,
                date_released, due_date, status, created_by_user_id
            ) values (%s, %s, %s, 3000.00, 50.00, %s, %s, 'active', %s)
            returning id
            """,
            (
                f"P6T67L-{suffix}",
                client_id,
                seven_type_id,
                RELEASE_DATE,
                RELEASE_DATE + timedelta(days=120),
                collector_id,
            ),
        ).fetchone()[0]
        for loan_id, balance in (
            (regular_loan_id, Decimal("5000.00")),
            (seven_loan_id, Decimal("3000.00")),
        ):
            connection.execute(
                """
                insert into lending.loan_collection_state (
                    loan_id, remaining_balance, is_reconciled, state_version
                ) values (%s, %s, true, 0)
                """,
                (loan_id, balance),
            )

        fingerprint = (suffix + "a" * 64)[:64]
        review_id = connection.execute(
            """
            insert into lending.seven_by_seven_pricing_compliance_reviews (
                loan_id, terms_fingerprint,
                applicability_review_ready, pricing_cap_review_ready,
                disclosure_ready, total_cost_cap_review_ready,
                evidence_reference, review_note, reviewed_by_user_id,
                penalty_policy_version, penalty_monthly_rate,
                penalty_proration_days, penalty_rate_ceiling,
                lifetime_nonprincipal_cost_ceiling,
                counted_nonprincipal_cost_at_contract_lock
            ) values (
                %s, %s, true, true, true, true, %s, %s, %s,
                '7x7-penalty-v1', 0.030000, 30, 0.030000,
                3000.00, 0.00
            ) returning id
            """,
            (
                seven_loan_id,
                fingerprint,
                f"P6-T6-PENALTY-{suffix}",
                "Exact signed penalty authority for Combined Pay Task 6.",
                collector_id,
            ),
        ).fetchone()[0]
        schedule_settings = {
            "seven_by_seven_penalty_policy": {
                "policy_version": "7x7-penalty-v1",
                "review_id": review_id,
                "terms_fingerprint": fingerprint,
                "contractual_monthly_rate": "0.030000",
                "proration_days": 30,
                "legal_rate_ceiling": "0.030000",
                "lifetime_nonprincipal_cost_ceiling": "3000.00",
                "counted_nonprincipal_cost_at_contract_lock": "0.00",
            }
        }
        schedule_rows = generate_signed_seven_by_seven_schedule(
            original_principal=Decimal("3000.00"),
            agreed_daily_payment=Decimal("50.00"),
            daily_interest_per_1000=Decimal("7.00"),
            first_due_date=FIRST_DUE_DATE,
        )
        with connection.cursor() as cursor:
            schedule_id = register_verified_contract_schedule(
                cursor,
                loan_id=seven_loan_id,
                payment_frequency="daily",
                contract_reference=f"P6-T6-CONTRACT-{suffix}",
                contract_signed_date=RELEASE_DATE,
                effective_from=RELEASE_DATE,
                grace_days=0,
                installments=schedule_rows,
                evidence_basis="signed_contract",
                evidence_reference=f"P6-T6-SIGNED-{suffix}",
                verification_note=(
                    "Borrower accepted exact signed 7x7 schedule and penalty disclosure."
                ),
                verified_by_user_id=collector_id,
                agreed_daily_payment=Decimal("50.00"),
                schedule_settings=schedule_settings,
                confirmed=True,
            )
        connection.execute(
            """
            insert into lending.loan_schedule_operational_state (
                schedule_id, operational_version, updated_by_user_id
            ) values (%s, 0, %s)
            on conflict (schedule_id) do nothing
            """,
            (schedule_id, collector_id),
        )
        connection.execute(
            """
            insert into lending.collector_area_assignments (
                collector_user_id, area, sort_order, is_active
            ) values (%s, %s, 0, true)
            """,
            (collector_id, f"P6 Task 6 Area {suffix}"),
        )

    return CombinedPenaltyCase(
        collector_id=collector_id,
        device_record_id=device_record_id,
        installation_id=installation_id,
        client_id=client_id,
        regular_loan_id=regular_loan_id,
        seven_loan_id=seven_loan_id,
    )


def _client_for(case: CombinedPenaltyCase) -> TestClient:
    app = FastAPI()
    app.include_router(create_combined_collection_router())
    app.dependency_overrides[collection_actor_dependency] = lambda: case.actor
    return TestClient(app)


def _maturity(case: CombinedPenaltyCase) -> date:
    with _connect() as connection:
        return connection.execute(
            """
            select max(installment.due_date)
            from lending.loan_contract_schedules schedule
            join lending.loan_contract_installments installment
              on installment.schedule_id = schedule.id
            where schedule.loan_id = %s
              and schedule.status = 'active'
            """,
            (case.seven_loan_id,),
        ).fetchone()[0]


def _contractual_collectible(case: CombinedPenaltyCase, collection_date: date) -> Decimal:
    with _connect() as connection:
        value = connection.execute(
            """
            select coalesce(sum(installment.operational_amount), 0)::numeric(18,2)
            from lending.loan_contract_schedules schedule
            join lending.loan_contract_installments_operational installment
              on installment.schedule_id = schedule.id
            where schedule.loan_id = %s
              and schedule.status = 'active'
              and installment.effective_due_date <= %s
              and installment.removed_from_operational_schedule = false
            """,
            (case.seven_loan_id, collection_date),
        ).fetchone()[0]
    return Decimal(value)


def _projected_penalty(case: CombinedPenaltyCase, collection_date: date) -> Decimal:
    with _connect() as connection, connection.cursor() as cursor:
        state = project_verified_seven_by_seven_penalty_state(
            cursor,
            loan_id=case.seven_loan_id,
            as_of_date=collection_date,
        )
    assert state.status == "projected"
    assert state.projected_penalty > Decimal("0.00")
    return state.projected_penalty


def _body(
    case: CombinedPenaltyCase,
    *,
    collection_date: date,
    cash_received_amount: Decimal,
) -> tuple[UUID, dict[str, object]]:
    key = uuid4()
    body: dict[str, object] = {
        "client_transaction_id": str(key),
        "client_id": str(case.client_id),
        "collection_date": collection_date.isoformat(),
        "recorded_at": datetime.combine(
            collection_date,
            datetime.min.time(),
            tzinfo=timezone.utc,
        ).isoformat(),
        "device_id": case.installation_id,
        "device_sequence": 1,
        "cash_received_amount": format(cash_received_amount, "f"),
        "legs": [
            {
                "route_entry_id": str(case.regular_loan_id),
                "loan_id": str(case.regular_loan_id),
                "route_revision": f"loan:{case.regular_loan_id}:v0",
            },
            {
                "route_entry_id": str(case.seven_loan_id),
                "loan_id": str(case.seven_loan_id),
                "route_revision": f"loan:{case.seven_loan_id}:v0",
            },
        ],
    }
    return key, body


def _headers(case: CombinedPenaltyCase, key: UUID) -> dict[str, str]:
    return {
        "Idempotency-Key": str(key),
        "X-Client-Transaction-Id": str(key),
        "X-Gilbic-Contract-Version": CONTRACT_VERSION,
    }


def test_combined_preview_counts_projected_penalty_inside_7x7_before_regular(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _setup_case()
    collection_date = _maturity(case) + timedelta(days=1)
    monkeypatch.setattr(
        combined_collection_api,
        "_current_business_date",
        lambda: collection_date,
    )
    contractual = _contractual_collectible(case, collection_date)
    penalty = _projected_penalty(case, collection_date)
    key, body = _body(
        case,
        collection_date=collection_date,
        cash_received_amount=Decimal("1.00"),
    )

    response = _client_for(case).post(
        "/api/v1/collector/collections/combined/preview",
        headers=_headers(case, key),
        json=body,
    )

    assert response.status_code == 200, response.text
    preview = response.json()["data"]
    seven = next(
        leg for leg in preview["legs"] if leg["loan_type"] == "seven_by_seven"
    )
    regular = next(leg for leg in preview["legs"] if leg["loan_type"] == "regular")
    assert preview["allocation_order"] == ["seven_by_seven", "regular"]
    assert Decimal(seven["collectible_amount"]) == contractual + penalty
    assert Decimal(regular["collectible_amount"]) == Decimal("50.00")


def test_combined_exact_post_maturity_cash_freezes_and_pays_penalty_before_regular(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _setup_case()
    collection_date = _maturity(case) + timedelta(days=1)
    monkeypatch.setattr(
        combined_collection_api,
        "_current_business_date",
        lambda: collection_date,
    )
    contractual = _contractual_collectible(case, collection_date)
    penalty = _projected_penalty(case, collection_date)
    expected_seven = contractual + penalty
    expected_total = expected_seven + Decimal("50.00")
    key, body = _body(
        case,
        collection_date=collection_date,
        cash_received_amount=expected_total,
    )

    response = _client_for(case).post(
        "/api/v1/collector/collections/combined",
        headers=_headers(case, key),
        json=body,
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert Decimal(data["total_amount"]) == expected_total
    seven_leg = next(
        leg for leg in data["legs"] if leg["loan_id"] == str(case.seven_loan_id)
    )
    regular_leg = next(
        leg for leg in data["legs"] if leg["loan_id"] == str(case.regular_loan_id)
    )
    assert Decimal(seven_leg["amount"]) == expected_seven
    assert Decimal(regular_leg["amount"]) == Decimal("50.00")

    with _connect() as connection:
        assessed = Decimal(
            connection.execute(
                """
                select coalesce(sum(assessed_penalty_amount), 0)
                from lending.seven_by_seven_penalty_assessments
                where loan_id = %s
                """,
                (case.seven_loan_id,),
            ).fetchone()[0]
        )
        paid = Decimal(
            connection.execute(
                """
                select coalesce(sum(allocation.amount_applied), 0)
                from lending.seven_by_seven_penalty_payment_allocations allocation
                join lending.collection_transactions transaction
                  on transaction.id = allocation.transaction_id
                where allocation.loan_id = %s
                  and transaction.is_voided = false
                """,
                (case.seven_loan_id,),
            ).fetchone()[0]
        )
    assert assessed == penalty
    assert paid == penalty

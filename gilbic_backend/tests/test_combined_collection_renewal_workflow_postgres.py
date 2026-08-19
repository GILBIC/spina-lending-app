from __future__ import annotations

import os
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from gilbic_backend.collection_api import collection_actor_dependency
from gilbic_backend.collector_route_renewal_repository import (
    PostgresCollectorRouteRenewalRepository,
)
from gilbic_backend.combined_collection_api import create_combined_collection_router
from gilbic_backend.renewal_repository import (
    PostgresRenewalRepository,
    RenewalLoanNotEligible,
)
from gilbic_backend.seven_by_seven_collection_posting import (
    SEVEN_BY_SEVEN_MOBILE_SETTING,
)
from spina_mobile_collections.contracts import ActorContext
from spina_mobile_collections.service import CONTRACT_VERSION


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)


class CombinedCase:
    def __init__(
        self,
        *,
        collector_id: UUID,
        device_id: UUID,
        installation_id: str,
        client_id: UUID,
        regular_loan_id: UUID,
        seven_loan_id: UUID,
    ) -> None:
        self.collector_id = collector_id
        self.device_id = device_id
        self.installation_id = installation_id
        self.client_id = client_id
        self.regular_loan_id = regular_loan_id
        self.seven_loan_id = seven_loan_id

    @property
    def actor(self) -> ActorContext:
        return ActorContext(
            account_id=str(self.collector_id),
            device_id=self.installation_id,
            registered_device_id=str(self.device_id),
            permissions=frozenset({"collection.create"}),
        )


def _connect() -> psycopg.Connection:
    assert DATABASE_URL is not None
    return psycopg.connect(DATABASE_URL)


def _setup_combined_case() -> CombinedCase:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    installation_id = f"combined-{suffix}"
    release = date(2097, 8, 1)
    with _connect() as connection:
        collector_id = connection.execute(
            """
            insert into core.users (username, full_name, status)
            values (%s,%s,'active') returning id
            """,
            (f"combined-{suffix}", f"Combined Collector {suffix}"),
        ).fetchone()[0]
        device_id = connection.execute(
            """
            insert into core.devices (
                user_id, device_identifier_hash, platform, app_version, status
            ) values (%s,%s,'android','atomic-test','active') returning id
            """,
            (collector_id, f"hash-{suffix}"),
        ).fetchone()[0]
        client_id = connection.execute(
            """
            insert into lending.clients (client_code, full_name, area, status)
            values (%s,%s,%s,'active') returning id
            """,
            (f"COMB-{suffix}", f"Combined Client {suffix}", f"Atomic Area {suffix}"),
        ).fetchone()[0]
        regular_type_id = connection.execute(
            """
            insert into lending.loan_types (
                code, name, description, term_days, calculation_mode,
                daily_interest_per_1000, settings, is_active
            ) values (%s,'Regular','atomic combined test',120,'fixed_daily',0,%s,true)
            returning id
            """,
            (
                f"COMB-REG-{suffix}",
                Jsonb(
                    {
                        "mobile_collections_enabled": True,
                        "mobile_balance_mode": "direct_remaining_balance",
                    }
                ),
            ),
        ).fetchone()[0]
        seven_type_id = connection.execute(
            """
            insert into lending.loan_types (
                code, name, description, term_days, calculation_mode,
                daily_interest_per_1000, settings, is_active
            ) values (%s,'7x7','atomic combined test',120,'seven_by_seven',7,%s,true)
            returning id
            """,
            (
                f"COMB-7-{suffix}",
                Jsonb(
                    {
                        "mobile_collections_enabled": True,
                        "mobile_balance_mode": "direct_remaining_balance",
                        SEVEN_BY_SEVEN_MOBILE_SETTING: True,
                    }
                ),
            ),
        ).fetchone()[0]
        regular_loan_id = connection.execute(
            """
            insert into lending.loans (
                loan_number, client_id, loan_type_id, principal, daily_amount,
                date_released, due_date, status, created_by_user_id
            ) values (%s,%s,%s,5000,50,%s,%s,'active',%s) returning id
            """,
            (
                f"COMB-R-{suffix}",
                client_id,
                regular_type_id,
                release,
                date(2097, 11, 29),
                collector_id,
            ),
        ).fetchone()[0]
        seven_loan_id = connection.execute(
            """
            insert into lending.loans (
                loan_number, client_id, loan_type_id, principal, daily_amount,
                date_released, due_date, status, created_by_user_id
            ) values (%s,%s,%s,3000,21,%s,%s,'active',%s) returning id
            """,
            (
                f"COMB-7-{suffix}",
                client_id,
                seven_type_id,
                release,
                date(2097, 11, 29),
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
                ) values (%s,%s,true,0)
                """,
                (loan_id, balance),
            )
        connection.execute(
            """
            insert into lending.collector_area_assignments (
                collector_user_id, area, sort_order, is_active
            ) values (%s,%s,0,true)
            """,
            (collector_id, f"Atomic Area {suffix}"),
        )
    return CombinedCase(
        collector_id=collector_id,
        device_id=device_id,
        installation_id=installation_id,
        client_id=client_id,
        regular_loan_id=regular_loan_id,
        seven_loan_id=seven_loan_id,
    )


def _client_for(case: CombinedCase) -> TestClient:
    app = FastAPI()
    app.include_router(create_combined_collection_router())
    app.dependency_overrides[collection_actor_dependency] = lambda: case.actor
    return TestClient(app)


def _body(case: CombinedCase, *, stale_seven: bool = False) -> tuple[UUID, dict[str, object]]:
    key = uuid4()
    return key, {
        "client_transaction_id": str(key),
        "client_id": str(case.client_id),
        "collection_date": "2097-08-02",
        "recorded_at": "2097-08-02T01:00:00Z",
        "device_id": case.installation_id,
        "device_sequence": 1,
        "legs": [
            {
                "route_entry_id": str(case.regular_loan_id),
                "loan_id": str(case.regular_loan_id),
                "route_revision": f"loan:{case.regular_loan_id}:v0",
                "amount": "50.00",
            },
            {
                "route_entry_id": str(case.seven_loan_id),
                "loan_id": str(case.seven_loan_id),
                "route_revision": (
                    f"loan:{case.seven_loan_id}:v99"
                    if stale_seven
                    else f"loan:{case.seven_loan_id}:v0"
                ),
                "amount": "21.00",
            },
        ],
    }


def _headers(case: CombinedCase, key: UUID) -> dict[str, str]:
    return {
        "Idempotency-Key": str(key),
        "X-Client-Transaction-Id": str(key),
        "X-Gilbic-Contract-Version": CONTRACT_VERSION,
    }


def test_combined_regular_plus_7x7_is_atomic_and_retry_safe() -> None:
    case = _setup_combined_case()
    client = _client_for(case)
    key, body = _body(case)

    response = client.post(
        "/api/v1/collector/collections/combined",
        headers=_headers(case, key),
        json=body,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "accepted"
    assert data["duplicate"] is False
    assert data["total_amount"] == "71.00"
    assert len(data["legs"]) == 2
    assert all(item["receipt_number"].startswith("GBC-20970802-") for item in data["legs"])

    with _connect() as connection:
        rows = connection.execute(
            """
            select loan_id, amount, applied_amount, official_balance,
                   details->>'seven_by_seven_interest_paid',
                   details->>'seven_by_seven_principal_paid'
            from lending.collection_transactions
            where loan_id = any(%s)
            order by loan_id
            """,
            ([case.regular_loan_id, case.seven_loan_id],),
        ).fetchall()
        parent_count = connection.execute(
            """
            select count(*)
            from mobile.gilbic_combined_collection_idempotency
            where idempotency_key=%s
            """,
            (key,),
        ).fetchone()[0]
    assert len(rows) == 2
    assert parent_count == 1
    regular = next(row for row in rows if row[0] == case.regular_loan_id)
    seven = next(row for row in rows if row[0] == case.seven_loan_id)
    assert regular[1:4] == (
        Decimal("50.00"),
        Decimal("50.00"),
        Decimal("4950.00"),
    )
    assert seven[1:] == (
        Decimal("21.00"),
        Decimal("21.00"),
        Decimal("3000.00"),
        "21.00",
        "0.00",
    )

    duplicate = client.post(
        "/api/v1/collector/collections/combined",
        headers=_headers(case, key),
        json=body,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["status"] == "duplicate"
    with _connect() as connection:
        assert connection.execute(
            "select count(*) from lending.collection_transactions where loan_id = any(%s)",
            ([case.regular_loan_id, case.seven_loan_id],),
        ).fetchone()[0] == 2


def test_combined_second_leg_failure_rolls_back_first_leg() -> None:
    case = _setup_combined_case()
    client = _client_for(case)
    key, body = _body(case, stale_seven=True)

    response = client.post(
        "/api/v1/collector/collections/combined",
        headers=_headers(case, key),
        json=body,
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "route_revision_changed"

    with _connect() as connection:
        assert connection.execute(
            "select count(*) from lending.collection_transactions where loan_id = any(%s)",
            ([case.regular_loan_id, case.seven_loan_id],),
        ).fetchone()[0] == 0
        assert connection.execute(
            "select count(*) from mobile.gilbic_combined_collection_idempotency where idempotency_key=%s",
            (key,),
        ).fetchone()[0] == 0


def _setup_renewal_client(*, mode: str) -> tuple[UUID, UUID, UUID, UUID]:
    suffix = uuid4().hex[:10]
    with _connect() as connection:
        borrower_user_id = connection.execute(
            """
            insert into core.users (username, full_name, status)
            values (%s,%s,'active') returning id
            """,
            (f"borrower-{suffix}", f"Borrower {suffix}"),
        ).fetchone()[0]
        collector_id = connection.execute(
            """
            insert into core.users (username, full_name, status)
            values (%s,%s,'active') returning id
            """,
            (f"collector-renew-{suffix}", f"Renew Collector {suffix}"),
        ).fetchone()[0]
        area = f"Renew Area {suffix}"
        client_id = connection.execute(
            """
            insert into lending.clients (
                client_code, full_name, area, status, user_id
            ) values (%s,%s,%s,'active',%s) returning id
            """,
            (f"REN-{suffix}", f"Renew Client {suffix}", area, borrower_user_id),
        ).fetchone()[0]
        settings = {
            "mobile_collections_enabled": True,
            "mobile_balance_mode": "direct_remaining_balance",
        }
        if mode == "seven_by_seven":
            settings[SEVEN_BY_SEVEN_MOBILE_SETTING] = True
        loan_type_id = connection.execute(
            """
            insert into lending.loan_types (
                code, name, description, term_days, calculation_mode,
                daily_interest_per_1000, settings, is_active
            ) values (%s,%s,'renewal policy test',120,%s,%s,%s,true)
            returning id
            """,
            (
                f"REN-T-{suffix}",
                "7x7" if mode == "seven_by_seven" else "Regular",
                mode,
                Decimal("7.00") if mode == "seven_by_seven" else Decimal("0.00"),
                Jsonb(settings),
            ),
        ).fetchone()[0]
        loan_id = connection.execute(
            """
            insert into lending.loans (
                loan_number, client_id, loan_type_id, principal, daily_amount,
                date_released, due_date, status, created_by_user_id
            ) values (%s,%s,%s,3000,%s,'2097-08-01','2097-11-29','active',%s)
            returning id
            """,
            (
                f"REN-L-{suffix}",
                client_id,
                loan_type_id,
                Decimal("21.00") if mode == "seven_by_seven" else Decimal("50.00"),
                collector_id,
            ),
        ).fetchone()[0]
        connection.execute(
            """
            insert into lending.loan_collection_state (
                loan_id, remaining_balance, is_reconciled, state_version
            ) values (%s,3000,true,0)
            """,
            (loan_id,),
        )
        connection.execute(
            """
            insert into lending.collector_area_assignments (
                collector_user_id, area, sort_order, is_active
            ) values (%s,%s,0,true)
            """,
            (collector_id, area),
        )
    return borrower_user_id, collector_id, client_id, loan_id


def test_regular_below_fifty_percent_blocks_but_7x7_can_request() -> None:
    repository = PostgresRenewalRepository()
    regular_user, _, _, regular_loan = _setup_renewal_client(mode="fixed_daily")
    with pytest.raises(RenewalLoanNotEligible) as blocked:
        repository.submit_for_user(
            user_id=regular_user,
            loan_id=regular_loan,
            requested_amount=Decimal("3000.00"),
            client_message="Regular below fifty percent",
        )
    assert "50%" in str(blocked.value)

    seven_user, seven_collector, seven_client, seven_loan = _setup_renewal_client(
        mode="seven_by_seven"
    )
    request = repository.submit_for_user(
        user_id=seven_user,
        loan_id=seven_loan,
        requested_amount=Decimal("3000.00"),
        client_message="7x7 request for consideration",
    )
    assert request.status == "pending"
    assert request.loan_id == seven_loan

    badges = PostgresCollectorRouteRenewalRepository().get_for_clients(
        collector_user_id=seven_collector,
        client_ids=(seven_client,),
    )
    assert seven_client in badges
    assert len(badges[seven_client]) == 1
    assert badges[seven_client][0].request_id == request.request_id
    assert badges[seven_client][0].is_seven_by_seven is True

    stranger = uuid4()
    with _connect() as connection:
        connection.execute(
            "insert into core.users (id, username, full_name, status) values (%s,%s,%s,'active')",
            (stranger, f"stranger-{uuid4().hex[:8]}", "Stranger Collector"),
        )
    assert PostgresCollectorRouteRenewalRepository().get_for_clients(
        collector_user_id=stranger,
        client_ids=(seven_client,),
    ) == {}


def test_renewal_permissions_and_schema_are_installed() -> None:
    with _connect() as connection:
        permissions = {
            row[0]
            for row in connection.execute(
                """
                select rp.permission_code
                from core.role_permissions rp
                join core.roles r on r.id=rp.role_id
                where r.code='collector'
                  and rp.permission_code in (
                      'renewal.recommend.assigned',
                      'renewal.cash_custody.assigned'
                  )
                """
            ).fetchall()
        }
        assert permissions == {
            "renewal.recommend.assigned",
            "renewal.cash_custody.assigned",
        }
        assert connection.execute(
            "select to_regclass('mobile.gilbic_combined_collection_idempotency')"
        ).fetchone()[0] is not None
        assert connection.execute(
            "select to_regclass('lending.renewal_required_signers')"
        ).fetchone()[0] is not None
        assert connection.execute(
            "select to_regclass('lending.renewal_handover_photos')"
        ).fetchone()[0] is not None

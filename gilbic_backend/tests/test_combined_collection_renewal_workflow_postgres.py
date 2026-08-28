from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from decimal import Decimal
from threading import Event
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from gilbic_backend.collection_api import collection_actor_dependency
from gilbic_backend.collector_route_renewal_repository import (
    PostgresCollectorRouteRenewalRepository,
)
from gilbic_backend.combined_collection_api import (
    CombinedPaymentRequest,
    _hash,
    _legacy_canonical_payload,
    create_combined_collection_router,
)
from gilbic_backend.concurrent_receipt_collection_posting import (
    ConcurrentReceiptSafeCollectionPostingBridge,
)
from gilbic_backend.contract_collection_activation_repository import (
    PostgresContractCollectionActivationRepository,
)
from gilbic_backend.contract_collection_posting import CONTRACT_ALLOCATION_SETTING
from gilbic_backend.contract_schedule_engine import generate_contract_installments
from gilbic_backend.contract_schedule_registration_service import (
    register_verified_contract_schedule,
)
from gilbic_backend.renewal_repository import (
    PostgresRenewalRepository,
    RenewalLoanNotEligible,
)
from gilbic_backend.seven_by_seven_collection_posting import (
    SEVEN_BY_SEVEN_MOBILE_SETTING,
)
from gilbic_backend.seven_by_seven_signed_schedule import (
    generate_signed_seven_by_seven_schedule,
)
from psycopg.types.json import Jsonb
from spina_mobile_collections.contracts import (
    ActorContext,
    CollectionCommand,
    CollectionEntryType,
    PastDueFollowupInput,
    PastDueReasonCode,
)
from spina_mobile_collections.service import (
    CONTRACT_VERSION,
    CollectionConflict,
    CollectionRejected,
)

from gilbic_backend import combined_collection_api

DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)


@pytest.fixture(autouse=True)
def _fixed_business_date(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        combined_collection_api,
        "_current_business_date",
        lambda: date(2097, 8, 2),
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


def _setup_combined_case(
    *,
    verified_seven_schedule: bool = False,
    verified_regular_schedule: bool = False,
    regular_first_due: date = date(2097, 8, 2),
) -> CombinedCase:
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
                        **(
                            {CONTRACT_ALLOCATION_SETTING: True}
                            if verified_regular_schedule
                            else {}
                        ),
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
        if verified_seven_schedule:
            schedule_rows = generate_signed_seven_by_seven_schedule(
                original_principal=Decimal("3000.00"),
                agreed_daily_payment=Decimal("50.00"),
                daily_interest_per_1000=Decimal("7.00"),
                first_due_date=date(2097, 8, 2),
            )
            with connection.cursor() as cursor:
                schedule_id = register_verified_contract_schedule(
                    cursor,
                    loan_id=seven_loan_id,
                    payment_frequency="daily",
                    contract_reference=f"SIGNED-COMB-7-{suffix}",
                    contract_signed_date=release,
                    effective_from=release,
                    grace_days=0,
                    installments=schedule_rows,
                    evidence_basis="signed_contract",
                    evidence_reference=f"SIGNED-COMB-7-DOC-{suffix}",
                    verification_note="Borrower accepted the signed combined-pay 7x7 schedule.",
                    verified_by_user_id=collector_id,
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
        if verified_regular_schedule:
            schedule_rows = generate_contract_installments(
                payment_frequency="daily",
                contractual_total=Decimal("5000.00"),
                first_due_date=regular_first_due,
                installment_count=100,
                regular_installment_amount=Decimal("50.00"),
            )
            with connection.cursor() as cursor:
                schedule_id = register_verified_contract_schedule(
                    cursor,
                    loan_id=regular_loan_id,
                    payment_frequency="daily",
                    contract_reference=f"SIGNED-COMB-R-{suffix}",
                    contract_signed_date=release,
                    effective_from=release,
                    grace_days=0,
                    installments=schedule_rows,
                    evidence_basis="signed_contract",
                    evidence_reference=f"SIGNED-COMB-R-DOC-{suffix}",
                    verification_note=(
                        "Borrower accepted the signed combined-pay Regular schedule."
                    ),
                    verified_by_user_id=collector_id,
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
            ) values (%s,%s,0,true)
            """,
            (collector_id, f"Atomic Area {suffix}"),
        )
    if verified_regular_schedule:
        PostgresContractCollectionActivationRepository().activate(
            loan_id=regular_loan_id,
            acted_by_user_id=collector_id,
            activation_note="Synthetic verified Regular combined-pay activation.",
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


def _body(
    case: CombinedCase,
    *,
    stale_seven: bool = False,
    cash_received_amount: str = "71.00",
    extra_allocation_choice: str | None = None,
) -> tuple[UUID, dict[str, object]]:
    key = uuid4()
    body: dict[str, object] = {
        "client_transaction_id": str(key),
        "client_id": str(case.client_id),
        "collection_date": "2097-08-02",
        "recorded_at": "2097-08-02T01:00:00Z",
        "device_id": case.installation_id,
        "device_sequence": 1,
        "cash_received_amount": cash_received_amount,
        "legs": [
            {
                "route_entry_id": str(case.regular_loan_id),
                "loan_id": str(case.regular_loan_id),
                "route_revision": f"loan:{case.regular_loan_id}:v0",
            },
            {
                "route_entry_id": str(case.seven_loan_id),
                "loan_id": str(case.seven_loan_id),
                "route_revision": (
                    f"loan:{case.seven_loan_id}:v99"
                    if stale_seven
                    else f"loan:{case.seven_loan_id}:v0"
                ),
            },
        ],
    }
    if extra_allocation_choice is not None:
        body["extra_allocation_choice"] = extra_allocation_choice
    return key, body


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
    assert all(
        item["receipt_number"].startswith("GBC-20970802-") for item in data["legs"]
    )

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
        assert (
            connection.execute(
                "select count(*) from lending.collection_transactions where loan_id = any(%s)",
                ([case.regular_loan_id, case.seven_loan_id],),
            ).fetchone()[0]
            == 2
        )


def test_combined_preview_derives_exact_split_from_one_cash_total() -> None:
    case = _setup_combined_case()
    client = _client_for(case)
    key, body = _body(case)

    response = client.post(
        "/api/v1/collector/collections/combined/preview",
        headers=_headers(case, key),
        json=body,
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "exact"
    assert data["requires_review"] is False
    assert data["cash_received_amount"] == "71.00"
    assert data["expected_total_amount"] == "71.00"
    assert data["allocation_order"] == ["seven_by_seven", "regular"]
    seven = next(item for item in data["legs"] if item["loan_type"] == "seven_by_seven")
    regular = next(item for item in data["legs"] if item["loan_type"] == "regular")
    assert seven["scheduled_amount"] == "21.00"
    assert regular["scheduled_amount"] == "50.00"


@pytest.mark.parametrize(
    "path",
    (
        "/api/v1/collector/collections/combined/preview",
        "/api/v1/collector/collections/combined",
    ),
)
@pytest.mark.parametrize("submitted_date", ("2097-08-01", "2097-08-03"))
def test_combined_rejects_non_current_route_dates(
    path: str,
    submitted_date: str,
) -> None:
    case = _setup_combined_case()
    client = _client_for(case)
    key, body = _body(case)
    body["collection_date"] = submitted_date

    response = client.post(
        path,
        headers=_headers(case, key),
        json=body,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "combined_collection_date_changed",
        "message": (
            "Combined Pay only accepts today's Philippine route date. "
            "Refresh the collector route and try again."
        ),
        "expected_collection_date": "2097-08-02",
    }


def test_combined_regular_collectible_includes_multiple_due_schedule_rows() -> None:
    case = _setup_combined_case(
        verified_regular_schedule=True,
        regular_first_due=date(2097, 8, 1),
    )
    client = _client_for(case)
    key, body = _body(case, cash_received_amount="121.00")

    response = client.post(
        "/api/v1/collector/collections/combined/preview",
        headers=_headers(case, key),
        json=body,
    )

    assert response.status_code == 200, response.text
    preview = response.json()["data"]
    regular = next(item for item in preview["legs"] if item["loan_type"] == "regular")
    assert regular["collectible_amount"] == "100.00"
    assert regular["scheduled_amount"] == "100.00"
    assert regular["authoritative_evidence"]["schedule_version"] == 1
    assert regular["authoritative_evidence"]["installment_state_digest"]


def test_prior_exact_two_leg_body_is_recomputed_by_the_server() -> None:
    case = _setup_combined_case()
    client = _client_for(case)
    key, body = _body(case)
    del body["cash_received_amount"]
    body["legs"][0]["amount"] = "1.00"
    body["legs"][1]["amount"] = "70.00"

    response = client.post(
        "/api/v1/collector/collections/combined",
        headers=_headers(case, key),
        json=body,
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["total_amount"] == "71.00"
    seven = next(
        item for item in data["legs"] if item["loan_id"] == str(case.seven_loan_id)
    )
    regular = next(
        item for item in data["legs"] if item["loan_id"] == str(case.regular_loan_id)
    )
    assert seven["amount"] == "21.00"
    assert regular["amount"] == "50.00"


def test_prior_two_leg_idempotency_hash_replays_after_contract_upgrade() -> None:
    case = _setup_combined_case()
    client = _client_for(case)
    key, body = _body(case)
    del body["cash_received_amount"]
    body["legs"][0]["amount"] = "50.00"
    body["legs"][1]["amount"] = "21.00"
    parsed = CombinedPaymentRequest.model_validate(body)
    legacy_canonical = _legacy_canonical_payload(parsed)
    assert legacy_canonical is not None
    prior_result = {
        "status": "accepted",
        "duplicate": False,
        "client_transaction_id": str(key),
        "client_id": str(case.client_id),
        "total_amount": "71.00",
        "legs": [],
        "message": "Saved by the prior combined contract.",
    }
    with _connect() as connection:
        connection.execute(
            """
            insert into mobile.gilbic_combined_collection_idempotency (
                idempotency_key,
                collector_account_id,
                registered_device_id,
                canonical_request_hash,
                request_payload,
                result_payload
            ) values (%s, %s, %s, %s, %s, %s)
            """,
            (
                key,
                case.collector_id,
                case.device_id,
                _hash(legacy_canonical),
                Jsonb(legacy_canonical),
                Jsonb(prior_result),
            ),
        )

    response = client.post(
        "/api/v1/collector/collections/combined",
        headers=_headers(case, key),
        json=body,
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "duplicate"
    assert response.json()["data"]["total_amount"] == "71.00"


def _post_prior_seven_advance(
    case: CombinedCase,
    *,
    collection_date: date,
    covered_date: date,
    amount: Decimal,
    clear_due_amount: Decimal | None = None,
) -> None:
    installation_id = f"advance-{uuid4().hex[:10]}"
    with _connect() as connection:
        device_id = connection.execute(
            """
            insert into core.devices (
                user_id, device_identifier_hash, platform, app_version, status
            ) values (%s, %s, 'android', 'atomic-test', 'active') returning id
            """,
            (case.collector_id, f"hash-{installation_id}"),
        ).fetchone()[0]
        actor = ActorContext(
            account_id=str(case.collector_id),
            device_id=installation_id,
            registered_device_id=str(device_id),
            permissions=frozenset({"collection.create"}),
        )
        if clear_due_amount is not None:
            ConcurrentReceiptSafeCollectionPostingBridge().post_collection(
                connection,
                actor,
                CollectionCommand(
                    idempotency_key=uuid4(),
                    route_entry_id=str(case.seven_loan_id),
                    client_id=str(case.client_id),
                    loan_id=str(case.seven_loan_id),
                    collection_date=collection_date,
                    entry_type=CollectionEntryType.PAYMENT,
                    amount=clear_due_amount,
                    recorded_at=datetime.combine(
                        collection_date,
                        datetime.min.time(),
                        tzinfo=UTC,
                    ),
                    device_id=installation_id,
                    device_sequence=1,
                    route_revision=f"loan:{case.seven_loan_id}:v0",
                ),
            )
        ConcurrentReceiptSafeCollectionPostingBridge().post_collection(
            connection,
            actor,
            CollectionCommand(
                idempotency_key=uuid4(),
                route_entry_id=str(case.seven_loan_id),
                client_id=str(case.client_id),
                loan_id=str(case.seven_loan_id),
                collection_date=collection_date,
                entry_type=CollectionEntryType.ADVANCE,
                amount=amount,
                advance_from=covered_date,
                advance_until=covered_date,
                covered_dates=(covered_date,),
                recorded_at=datetime.combine(
                    collection_date,
                    datetime.min.time(),
                    tzinfo=UTC,
                ),
                device_id=installation_id,
                device_sequence=2 if clear_due_amount is not None else 1,
                route_revision=(
                    f"loan:{case.seven_loan_id}:v1"
                    if clear_due_amount is not None
                    else f"loan:{case.seven_loan_id}:v0"
                ),
            ),
        )


def test_combined_short_payment_requires_review_then_saves_7x7_first() -> None:
    case = _setup_combined_case()
    client = _client_for(case)
    key, body = _body(case, cash_received_amount="40.00")

    preview_response = client.post(
        "/api/v1/collector/collections/combined/preview",
        headers=_headers(case, key),
        json=body,
    )
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()["data"]
    assert preview["status"] == "short"
    assert preview["requires_review"] is True
    seven = next(
        item for item in preview["legs"] if item["loan_type"] == "seven_by_seven"
    )
    regular = next(item for item in preview["legs"] if item["loan_type"] == "regular")
    assert seven["scheduled_amount"] == "21.00"
    assert regular["scheduled_amount"] == "19.00"

    unreviewed = client.post(
        "/api/v1/collector/collections/combined",
        headers=_headers(case, key),
        json=body,
    )
    assert unreviewed.status_code == 409
    assert unreviewed.json()["detail"]["code"] == "combined_allocation_review_required"

    body["reviewed_allocation_hash"] = preview["allocation_hash"]
    body["regular_past_due_followup"] = {
        "reason_code": "business_slow",
        "note": "Client paid a partial combined amount.",
    }
    accepted = client.post(
        "/api/v1/collector/collections/combined",
        headers=_headers(case, key),
        json=body,
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["data"]["total_amount"] == "40.00"
    assert accepted.json()["data"]["allocation_status"] == "short"

    changed_retry = dict(body)
    changed_retry.pop("reviewed_allocation_hash")
    conflict = client.post(
        "/api/v1/collector/collections/combined",
        headers=_headers(case, key),
        json=changed_retry,
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "combined_idempotency_mismatch"
    with _connect() as connection:
        stored_request = connection.execute(
            """
            select request_payload
            from mobile.gilbic_combined_collection_idempotency
            where idempotency_key = %s
            """,
            (key,),
        ).fetchone()[0]
    assert stored_request["reviewed_allocation_hash"] == preview["allocation_hash"]


def test_combined_exact_payment_rejects_contradictory_review_hash() -> None:
    case = _setup_combined_case()
    client = _client_for(case)
    key, body = _body(case)
    body["reviewed_allocation_hash"] = "0" * 64

    response = client.post(
        "/api/v1/collector/collections/combined",
        headers=_headers(case, key),
        json=body,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "combined_allocation_review_required"


def test_combined_excess_requires_explicit_borrower_direction() -> None:
    case = _setup_combined_case()
    client = _client_for(case)
    key, body = _body(case, cash_received_amount="80.00")

    preview_response = client.post(
        "/api/v1/collector/collections/combined/preview",
        headers=_headers(case, key),
        json=body,
    )
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()["data"]
    assert preview["status"] == "extra_choice_required"
    assert preview["extra_amount"] == "9.00"
    assert preview["extra_choice_required"] is True

    rejected = client.post(
        "/api/v1/collector/collections/combined",
        headers=_headers(case, key),
        json=body,
    )
    assert rejected.status_code == 422
    assert (
        rejected.json()["detail"]["code"] == "combined_extra_allocation_choice_required"
    )

    with _connect() as connection:
        assert (
            connection.execute(
                "select count(*) from lending.collection_transactions where loan_id = any(%s)",
                ([case.regular_loan_id, case.seven_loan_id],),
            ).fetchone()[0]
            == 0
        )


def test_combined_exact_payment_rejects_an_inapplicable_extra_choice() -> None:
    case = _setup_combined_case()
    client = _client_for(case)
    key, body = _body(
        case,
        extra_allocation_choice="regular_principal_reduction",
    )

    response = client.post(
        "/api/v1/collector/collections/combined/preview",
        headers=_headers(case, key),
        json=body,
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"]["code"]
        == "combined_extra_allocation_choice_not_needed"
    )


@pytest.mark.parametrize(
    "choice",
    ["regular_advance", "regular_principal_reduction"],
)
def test_combined_regular_extra_choice_saves_scheduled_and_extra_atomically(
    choice: str,
) -> None:
    case = _setup_combined_case(verified_regular_schedule=True)
    client = _client_for(case)
    key, body = _body(
        case,
        cash_received_amount="80.00",
        extra_allocation_choice=choice,
    )

    preview_response = client.post(
        "/api/v1/collector/collections/combined/preview",
        headers=_headers(case, key),
        json=body,
    )
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()["data"]
    body["reviewed_allocation_hash"] = preview["allocation_hash"]

    response = client.post(
        "/api/v1/collector/collections/combined",
        headers=_headers(case, key),
        json=body,
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["total_amount"] == "80.00"
    assert data["extra_allocation_choice"] == choice
    assert len(data["legs"]) == 2
    regular = next(
        item for item in data["legs"] if item["loan_id"] == str(case.regular_loan_id)
    )
    assert regular["allocation_component"] == "regular_scheduled_and_extra"
    assert regular["amount"] == "59.00"
    assert regular["applied_amount"] == "59.00"
    assert regular["unallocated_amount"] == "0.00"
    expected_basis = (
        "future_advance_oldest_first"
        if choice == "regular_advance"
        else "voluntary_extra_tail"
    )
    with _connect() as connection:
        allocation = connection.execute(
            """
            select coalesce(sum(allocation.amount_applied), 0)
            from lending.loan_installment_payment_allocations allocation
            where allocation.transaction_id = %s
              and allocation.allocation_basis = %s
            """,
            (UUID(regular["transaction_id"]), expected_basis),
        ).fetchone()[0]
    assert allocation == Decimal("9.00")


def test_combined_regular_extra_choice_requires_activated_signed_schedule() -> None:
    case = _setup_combined_case()
    client = _client_for(case)
    key, body = _body(
        case,
        cash_received_amount="80.00",
        extra_allocation_choice="regular_principal_reduction",
    )

    response = client.post(
        "/api/v1/collector/collections/combined/preview",
        headers=_headers(case, key),
        json=body,
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"]["code"]
        == "combined_regular_extra_schedule_required"
    )


@pytest.mark.parametrize(
    "choice",
    ["seven_by_seven_advance", "seven_by_seven_extra_principal"],
)
def test_combined_7x7_extra_choice_requires_verified_schedule(choice: str) -> None:
    case = _setup_combined_case()
    client = _client_for(case)
    key, body = _body(
        case,
        cash_received_amount="80.00",
        extra_allocation_choice=choice,
    )

    response = client.post(
        "/api/v1/collector/collections/combined/preview",
        headers=_headers(case, key),
        json=body,
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"]["code"]
        == "combined_seven_by_seven_extra_schedule_required"
    )


def test_combined_7x7_advance_over_future_capacity_fails_during_preview() -> None:
    case = _setup_combined_case(verified_seven_schedule=True)
    client = _client_for(case)
    key, body = _body(
        case,
        cash_received_amount="10000.00",
        extra_allocation_choice="seven_by_seven_advance",
    )

    response = client.post(
        "/api/v1/collector/collections/combined/preview",
        headers=_headers(case, key),
        json=body,
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"]["code"]
        == "seven_by_seven_advance_capacity_exceeded"
    )


def test_combined_preview_virtually_activates_matured_partial_7x7_advance() -> None:
    case = _setup_combined_case(verified_seven_schedule=True)
    _post_prior_seven_advance(
        case,
        collection_date=date(2097, 8, 1),
        covered_date=date(2097, 8, 2),
        amount=Decimal("25.00"),
    )
    client = _client_for(case)
    key, body = _body(case, cash_received_amount="75.00")
    body["legs"][1]["route_revision"] = f"loan:{case.seven_loan_id}:v1"

    preview_response = client.post(
        "/api/v1/collector/collections/combined/preview",
        headers=_headers(case, key),
        json=body,
    )

    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()["data"]
    seven = next(
        item for item in preview["legs"] if item["loan_type"] == "seven_by_seven"
    )
    assert seven["collectible_amount"] == "25.00"
    assert seven["cash_projection"]["scheduled"]["closing_principal"] == "2971.00"

    accepted = client.post(
        "/api/v1/collector/collections/combined",
        headers=_headers(case, key),
        json=body,
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["data"]["total_amount"] == "75.00"


def test_combined_rejects_when_same_day_payment_clears_7x7_before_future_advance(
) -> None:
    case = _setup_combined_case(verified_seven_schedule=True)
    _post_prior_seven_advance(
        case,
        collection_date=date(2097, 8, 2),
        covered_date=date(2097, 8, 3),
        amount=Decimal("50.00"),
        clear_due_amount=Decimal("50.00"),
    )
    client = _client_for(case)
    key, body = _body(case, cash_received_amount="50.00")
    body["legs"][1]["route_revision"] = f"loan:{case.seven_loan_id}:v2"

    response = client.post(
        "/api/v1/collector/collections/combined/preview",
        headers=_headers(case, key),
        json=body,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "combined_obligation_changed"


def test_combined_signed_regular_schedule_fails_closed_when_posting_gate_is_off() -> None:
    case = _setup_combined_case(verified_regular_schedule=True)
    PostgresContractCollectionActivationRepository().deactivate(
        loan_id=case.regular_loan_id,
        acted_by_user_id=case.collector_id,
        activation_note="Synthetic combined-pay gate-off proof.",
    )
    client = _client_for(case)
    key, body = _body(case)

    response = client.post(
        "/api/v1/collector/collections/combined/preview",
        headers=_headers(case, key),
        json=body,
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"]["code"]
        == "combined_regular_contract_schedule_not_ready"
    )


def test_combined_preview_rejects_cash_above_exact_payoff_capacity() -> None:
    case = _setup_combined_case(verified_regular_schedule=True)
    client = _client_for(case)
    key, body = _body(
        case,
        cash_received_amount="6000.00",
        extra_allocation_choice="regular_principal_reduction",
    )
    preview_response = client.post(
        "/api/v1/collector/collections/combined/preview",
        headers=_headers(case, key),
        json=body,
    )
    assert preview_response.status_code == 422
    assert preview_response.json()["detail"]["code"] == "combined_amount_exceeds_payoff"
    with _connect() as connection:
        assert (
            connection.execute(
                "select count(*) from lending.collection_transactions where loan_id = any(%s)",
                ([case.regular_loan_id, case.seven_loan_id],),
            ).fetchone()[0]
            == 0
        )


@pytest.mark.parametrize(
    "choice",
    ["seven_by_seven_advance", "seven_by_seven_extra_principal"],
)
def test_combined_7x7_extra_choice_saves_a_separate_verified_component(
    choice: str,
) -> None:
    case = _setup_combined_case(verified_seven_schedule=True)
    client = _client_for(case)
    key, body = _body(
        case,
        cash_received_amount="109.00",
        extra_allocation_choice=choice,
    )

    preview_response = client.post(
        "/api/v1/collector/collections/combined/preview",
        headers=_headers(case, key),
        json=body,
    )
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()["data"]
    body["reviewed_allocation_hash"] = preview["allocation_hash"]

    response = client.post(
        "/api/v1/collector/collections/combined",
        headers=_headers(case, key),
        json=body,
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["total_amount"] == "109.00"
    assert data["extra_allocation_choice"] == choice
    assert len(data["legs"]) == 3
    extra = next(
        item
        for item in data["legs"]
        if item["allocation_component"]
        in {"seven_by_seven_advance", "seven_by_seven_extra_principal"}
    )
    assert extra["allocation_component"] == choice
    assert extra["amount"] == "9.00"
    assert extra["applied_amount"] == "9.00"
    assert extra["unallocated_amount"] == "0.00"
    if choice == "seven_by_seven_extra_principal":
        result = extra["result"]
        assert result["allocation_type"] == "seven_by_seven_extra_principal"
        assert result["adjustment_id"]
        assert result["interest_contribution"] == "0.00"
        assert result["refund_due"] == "0.00"
        assert result["resulting_operational_version"] == 1
        assert result["operational_state_digest"]
        assert result["automatic_source_posting"] is False

    duplicate = client.post(
        "/api/v1/collector/collections/combined",
        headers=_headers(case, key),
        json=body,
    )
    assert duplicate.status_code == 200, duplicate.text
    duplicate_extra = next(
        item
        for item in duplicate.json()["data"]["legs"]
        if item["allocation_component"] == choice
    )
    assert duplicate_extra == extra


def test_combined_preview_hides_loans_outside_collectors_assigned_route() -> None:
    case = _setup_combined_case()
    suffix = uuid4().hex[:10]
    with _connect() as connection:
        collector_id = connection.execute(
            """
            insert into core.users (username, full_name, status)
            values (%s, %s, 'active') returning id
            """,
            (f"unassigned-{suffix}", f"Unassigned Collector {suffix}"),
        ).fetchone()[0]
        device_id = connection.execute(
            """
            insert into core.devices (
                user_id, device_identifier_hash, platform, app_version, status
            ) values (%s, %s, 'android', 'atomic-test', 'active') returning id
            """,
            (collector_id, f"unassigned-hash-{suffix}"),
        ).fetchone()[0]
    outsider = CombinedCase(
        collector_id=collector_id,
        device_id=device_id,
        installation_id=f"unassigned-{suffix}",
        client_id=case.client_id,
        regular_loan_id=case.regular_loan_id,
        seven_loan_id=case.seven_loan_id,
    )
    client = _client_for(outsider)
    key, body = _body(outsider)

    response = client.post(
        "/api/v1/collector/collections/combined/preview",
        headers=_headers(outsider, key),
        json=body,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "combined_route_not_assigned"


def test_combined_preview_rejects_unreconciled_or_disabled_loan_state() -> None:
    case = _setup_combined_case()
    with _connect() as connection:
        connection.execute(
            """
            update lending.loan_collection_state
            set is_reconciled = false
            where loan_id = %s
            """,
            (case.regular_loan_id,),
        )
    client = _client_for(case)
    key, body = _body(case)

    response = client.post(
        "/api/v1/collector/collections/combined/preview",
        headers=_headers(case, key),
        json=body,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "combined_collection_not_ready"


def test_combined_daily_fallback_does_not_double_subtract_prior_receipt_near_payoff(
) -> None:
    case = _setup_combined_case()
    second_installation = f"prior-{uuid4().hex[:10]}"
    with _connect() as connection:
        second_device = connection.execute(
            """
            insert into core.devices (
                user_id, device_identifier_hash, platform, app_version, status
            ) values (%s, %s, 'android', 'atomic-test', 'active') returning id
            """,
            (case.collector_id, f"hash-{second_installation}"),
        ).fetchone()[0]
        connection.execute(
            """
            update lending.loan_collection_state
            set remaining_balance = 50.00
            where loan_id = %s
            """,
            (case.regular_loan_id,),
        )
        prior_actor = ActorContext(
            account_id=str(case.collector_id),
            device_id=second_installation,
            registered_device_id=str(second_device),
            permissions=frozenset({"collection.create"}),
        )
        command = CollectionCommand(
            idempotency_key=uuid4(),
            route_entry_id=str(case.regular_loan_id),
            client_id=str(case.client_id),
            loan_id=str(case.regular_loan_id),
            collection_date=date(2097, 8, 2),
            entry_type=CollectionEntryType.PAYMENT,
            amount=Decimal("20.00"),
            covered_dates=(date(2097, 8, 2),),
            recorded_at=datetime(2097, 8, 2, 0, 30, tzinfo=UTC),
            device_id=second_installation,
            device_sequence=1,
            route_revision=f"loan:{case.regular_loan_id}:v0",
            past_due_followup=PastDueFollowupInput(
                reason_code=PastDueReasonCode.BUSINESS_SLOW,
                note="Prior partial receipt for near-payoff fallback proof.",
            ),
        )
        ConcurrentReceiptSafeCollectionPostingBridge().post_collection(
            connection,
            prior_actor,
            command,
        )

    client = _client_for(case)
    key, body = _body(case, cash_received_amount="51.00")
    body["legs"][0]["route_revision"] = f"loan:{case.regular_loan_id}:v1"
    response = client.post(
        "/api/v1/collector/collections/combined/preview",
        headers=_headers(case, key),
        json=body,
    )

    assert response.status_code == 200, response.text
    preview = response.json()["data"]
    assert preview["expected_total_amount"] == "51.00"
    regular = next(item for item in preview["legs"] if item["loan_type"] == "regular")
    assert regular["collectible_amount"] == "30.00"
    assert regular["scheduled_amount"] == "30.00"


def test_combined_and_direct_receipt_share_lock_order_without_deadlock() -> None:
    case = _setup_combined_case()
    second_installation = f"concurrent-{uuid4().hex[:10]}"
    with _connect() as connection:
        second_device = connection.execute(
            """
            insert into core.devices (
                user_id, device_identifier_hash, platform, app_version, status
            ) values (%s, %s, 'android', 'atomic-test', 'active') returning id
            """,
            (case.collector_id, f"hash-{second_installation}"),
        ).fetchone()[0]
    direct_actor = ActorContext(
        account_id=str(case.collector_id),
        device_id=second_installation,
        registered_device_id=str(second_device),
        permissions=frozenset({"collection.create"}),
    )
    direct_posted = Event()
    allow_direct_commit = Event()

    def post_direct() -> None:
        with _connect() as connection:
            ConcurrentReceiptSafeCollectionPostingBridge().post_collection(
                connection,
                direct_actor,
                CollectionCommand(
                    idempotency_key=uuid4(),
                    route_entry_id=str(case.regular_loan_id),
                    client_id=str(case.client_id),
                    loan_id=str(case.regular_loan_id),
                    collection_date=date(2097, 8, 2),
                    entry_type=CollectionEntryType.PAYMENT,
                    amount=Decimal("10.00"),
                    covered_dates=(date(2097, 8, 2),),
                    recorded_at=datetime(2097, 8, 2, 0, 30, tzinfo=UTC),
                    device_id=second_installation,
                    device_sequence=1,
                    route_revision=f"loan:{case.regular_loan_id}:v0",
                    past_due_followup=PastDueFollowupInput(
                        reason_code=PastDueReasonCode.BUSINESS_SLOW,
                        note="Concurrent direct receipt lock-order proof.",
                    ),
                ),
            )
            direct_posted.set()
            assert allow_direct_commit.wait(timeout=5)

    client = _client_for(case)
    key, body = _body(case, cash_received_amount="61.00")
    with ThreadPoolExecutor(max_workers=2) as executor:
        direct_future = executor.submit(post_direct)
        assert direct_posted.wait(timeout=5)
        combined_future = executor.submit(
            client.post,
            "/api/v1/collector/collections/combined",
            headers=_headers(case, key),
            json=body,
        )
        allow_direct_commit.set()
        direct_future.result(timeout=8)
        response = combined_future.result(timeout=8)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["total_amount"] == "61.00"
    with _connect() as connection:
        assert (
            connection.execute(
                "select count(*) from lending.collection_transactions where loan_id = any(%s)",
                ([case.regular_loan_id, case.seven_loan_id],),
            ).fetchone()[0]
            == 3
        )


def test_combined_stale_leg_is_rejected_before_any_posting() -> None:
    case = _setup_combined_case()
    client = _client_for(case)
    key, body = _body(case, stale_seven=True)

    response = client.post(
        "/api/v1/collector/collections/combined",
        headers=_headers(case, key),
        json=body,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "combined_route_revision_changed"

    with _connect() as connection:
        assert (
            connection.execute(
                "select count(*) from lending.collection_transactions where loan_id = any(%s)",
                ([case.regular_loan_id, case.seven_loan_id],),
            ).fetchone()[0]
            == 0
        )


def test_combined_second_component_failure_rolls_back_first_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _setup_combined_case()
    client = _client_for(case)
    key, body = _body(case)
    original = ConcurrentReceiptSafeCollectionPostingBridge.post_collection

    def fail_regular(self, connection, actor, command):
        if command.loan_id == str(case.regular_loan_id):
            raise CollectionConflict(
                "Synthetic second-component conflict.",
                code="synthetic_second_component_conflict",
            )
        return original(self, connection, actor, command)

    monkeypatch.setattr(
        ConcurrentReceiptSafeCollectionPostingBridge,
        "post_collection",
        fail_regular,
    )
    response = client.post(
        "/api/v1/collector/collections/combined",
        headers=_headers(case, key),
        json=body,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "synthetic_second_component_conflict"
    with _connect() as connection:
        assert (
            connection.execute(
                "select count(*) from lending.collection_transactions where loan_id = any(%s)",
                ([case.regular_loan_id, case.seven_loan_id],),
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "select count(*) from mobile.gilbic_combined_collection_idempotency where idempotency_key=%s",
                (key,),
            ).fetchone()[0]
            == 0
        )


def test_combined_third_component_failure_rolls_back_all_prior_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _setup_combined_case(verified_seven_schedule=True)
    client = _client_for(case)
    key, body = _body(
        case,
        cash_received_amount="109.00",
        extra_allocation_choice="seven_by_seven_extra_principal",
    )
    preview = client.post(
        "/api/v1/collector/collections/combined/preview",
        headers=_headers(case, key),
        json=body,
    )
    assert preview.status_code == 200, preview.text
    body["reviewed_allocation_hash"] = preview.json()["data"]["allocation_hash"]
    original = ConcurrentReceiptSafeCollectionPostingBridge.post_collection

    def fail_extra(self, connection, actor, command):
        if command.note.endswith("seven_by_seven_extra_principal"):
            raise CollectionRejected(
                "Synthetic third-component rejection.",
                code="synthetic_third_component_rejection",
            )
        return original(self, connection, actor, command)

    monkeypatch.setattr(
        ConcurrentReceiptSafeCollectionPostingBridge,
        "post_collection",
        fail_extra,
    )
    response = client.post(
        "/api/v1/collector/collections/combined",
        headers=_headers(case, key),
        json=body,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "synthetic_third_component_rejection"
    with _connect() as connection:
        assert (
            connection.execute(
                "select count(*) from lending.collection_transactions where loan_id = any(%s)",
                ([case.regular_loan_id, case.seven_loan_id],),
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "select count(*) from lending.seven_by_seven_extra_principal_adjustments where loan_id=%s",
                (case.seven_loan_id,),
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "select count(*) from mobile.gilbic_combined_collection_idempotency where idempotency_key=%s",
                (key,),
            ).fetchone()[0]
            == 0
        )


def test_combined_downstream_underallocation_rolls_back_every_component(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _setup_combined_case(verified_seven_schedule=True)
    client = _client_for(case)
    key, body = _body(
        case,
        cash_received_amount="109.00",
        extra_allocation_choice="seven_by_seven_extra_principal",
    )
    preview = client.post(
        "/api/v1/collector/collections/combined/preview",
        headers=_headers(case, key),
        json=body,
    )
    assert preview.status_code == 200, preview.text
    body["reviewed_allocation_hash"] = preview.json()["data"]["allocation_hash"]
    original = ConcurrentReceiptSafeCollectionPostingBridge.post_collection

    def underallocate_extra(self, connection, actor, command):
        posted = original(self, connection, actor, command)
        if command.note.endswith("seven_by_seven_extra_principal"):
            connection.execute(
                """
                update lending.collection_transactions
                set applied_amount = applied_amount - 1.00,
                    unallocated_amount = unallocated_amount + 1.00,
                    allocation_state = 'partially_allocated'
                where id = %s
                """,
                (UUID(posted.server_transaction_id),),
            )
        return posted

    monkeypatch.setattr(
        ConcurrentReceiptSafeCollectionPostingBridge,
        "post_collection",
        underallocate_extra,
    )
    response = client.post(
        "/api/v1/collector/collections/combined",
        headers=_headers(case, key),
        json=body,
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"]["code"]
        == "combined_cash_allocation_contradiction"
    )
    with _connect() as connection:
        assert (
            connection.execute(
                "select count(*) from lending.collection_transactions where loan_id = any(%s)",
                ([case.regular_loan_id, case.seven_loan_id],),
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "select count(*) from lending.seven_by_seven_extra_principal_adjustments where loan_id=%s",
                (case.seven_loan_id,),
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "select count(*) from mobile.gilbic_combined_collection_idempotency where idempotency_key=%s",
                (key,),
            ).fetchone()[0]
            == 0
        )


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
    assert (
        PostgresCollectorRouteRenewalRepository().get_for_clients(
            collector_user_id=stranger,
            client_ids=(seven_client,),
        )
        == {}
    )


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
        assert (
            connection.execute(
                "select to_regclass('mobile.gilbic_combined_collection_idempotency')"
            ).fetchone()[0]
            is not None
        )
        assert (
            connection.execute(
                "select to_regclass('lending.renewal_required_signers')"
            ).fetchone()[0]
            is not None
        )
        assert (
            connection.execute(
                "select to_regclass('lending.renewal_handover_photos')"
            ).fetchone()[0]
            is not None
        )

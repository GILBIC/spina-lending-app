from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest

from gilbic_backend.seven_by_seven_penalty_coordinator import (
    SevenBySevenPenaltyState,
    allocate_verified_seven_by_seven_penalty_cash,
    freeze_verified_seven_by_seven_penalty_assessment,
    project_verified_seven_by_seven_penalty_state,
)


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
RELEASE_DATE = date(2099, 1, 1)
MATURITY = date(2099, 1, 3)
FIRST_PENALTY_DAY = MATURITY + timedelta(days=1)


def _transaction_body(source: str) -> str:
    body = source.strip()
    if body.startswith("BEGIN;") and body.endswith("COMMIT;"):
        body = body[len("BEGIN;") :].lstrip()
        body = body[: -len("COMMIT;")].rstrip()
    return body


def _priority6_migrations() -> tuple[Path, ...]:
    migrations: list[tuple[int, Path]] = []
    for path in SQL_ROOT.glob("[0-9][0-9][0-9][0-9]_*.sql"):
        number = int(path.name[:4])
        if 60 <= number <= 118:
            migrations.append((number, path))
    migrations.sort(key=lambda item: (item[0], item[1].name))
    return tuple(path for _, path in migrations)


@pytest.fixture(scope="module", autouse=True)
def _install_post_0059_schema() -> None:
    if not DATABASE_URL:
        return
    with psycopg.connect(DATABASE_URL) as connection:
        for path in _priority6_migrations():
            connection.execute(_transaction_body(path.read_text(encoding="utf-8")))
            connection.commit()


def _seed_case(
    connection,
    *,
    suffix: str,
    penalty_authority: bool = True,
    legal_rate_ceiling: Decimal = Decimal("0.030000"),
    lifetime_ceiling: Decimal = Decimal("5000.00"),
    counted_cost_at_lock: Decimal = Decimal("14.00"),
) -> dict[str, object]:
    actor_id = connection.execute(
        """
        insert into core.users (username, full_name, status)
        values (%s, %s, 'active') returning id
        """,
        (f"x7-pen-{suffix}", f"7x7 Penalty {suffix}"),
    ).fetchone()[0]
    device_id = connection.execute(
        """
        insert into core.devices (
            user_id, device_identifier_hash, platform, status
        ) values (%s, %s, 'desktop', 'active') returning id
        """,
        (actor_id, f"x7-pen-device-{suffix}"),
    ).fetchone()[0]
    client_id = connection.execute(
        """
        insert into lending.clients (client_code, full_name, status)
        values (%s, %s, 'active') returning id
        """,
        (f"X7-PEN-C-{suffix}", f"7x7 Penalty Client {suffix}"),
    ).fetchone()[0]
    loan_type_id = connection.execute(
        """
        insert into lending.loan_types (
            code, name, term_days, calculation_mode,
            daily_interest_per_1000, settings
        ) values (%s, %s, 60, 'seven_by_seven', 7.00, '{}'::jsonb)
        returning id
        """,
        (f"X7-PEN-{suffix}", f"7x7 Penalty {suffix}"),
    ).fetchone()[0]
    loan_id = connection.execute(
        """
        insert into lending.loans (
            loan_number, client_id, loan_type_id, principal, daily_amount,
            date_released, due_date, status, created_by_user_id
        ) values (
            %s, %s, %s, 1000.00, 507.00,
            %s, %s, 'active', %s
        ) returning id
        """,
        (
            f"X7-PEN-L-{suffix}",
            client_id,
            loan_type_id,
            RELEASE_DATE,
            MATURITY,
            actor_id,
        ),
    ).fetchone()[0]

    fingerprint = (suffix * 64)[:64].replace("-", "a")
    fingerprint = "".join(
        char if char in "0123456789abcdef" else "a" for char in fingerprint.lower()
    )
    fingerprint = (fingerprint + "a" * 64)[:64]

    if penalty_authority:
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
                '7x7-penalty-v1', 0.030000, 30, %s, %s, %s
            ) returning id
            """,
            (
                loan_id,
                fingerprint,
                f"X7-PEN-EVIDENCE-{suffix}",
                "Exact signed penalty policy and terms-bound legal authority reviewed.",
                actor_id,
                legal_rate_ceiling,
                lifetime_ceiling,
                counted_cost_at_lock,
            ),
        ).fetchone()[0]
        settings = {
            "seven_by_seven_penalty_policy": {
                "policy_version": "7x7-penalty-v1",
                "review_id": review_id,
                "terms_fingerprint": fingerprint,
                "contractual_monthly_rate": "0.030000",
                "proration_days": 30,
                "legal_rate_ceiling": format(legal_rate_ceiling, "f"),
                "lifetime_nonprincipal_cost_ceiling": format(lifetime_ceiling, "f"),
                "counted_nonprincipal_cost_at_contract_lock": format(
                    counted_cost_at_lock, "f"
                ),
            }
        }
    else:
        review_id = connection.execute(
            """
            insert into lending.seven_by_seven_pricing_compliance_reviews (
                loan_id, terms_fingerprint,
                applicability_review_ready, pricing_cap_review_ready,
                disclosure_ready, total_cost_cap_review_ready,
                evidence_reference, review_note, reviewed_by_user_id
            ) values (%s, %s, true, true, true, true, %s, %s, %s)
            returning id
            """,
            (
                loan_id,
                fingerprint,
                f"X7-LEGACY-EVIDENCE-{suffix}",
                "Legacy exact-term review intentionally has no signed penalty tuple.",
                actor_id,
            ),
        ).fetchone()[0]
        settings = {}

    schedule_id = connection.execute(
        """
        insert into lending.loan_contract_schedules (
            loan_id, schedule_version, status, payment_frequency,
            contract_reference, contract_signed_date, effective_from,
            grace_days, settings, created_by_user_id
        ) values (
            %s, 1, 'active', 'daily', %s, %s, %s,
            0, %s::jsonb, %s
        ) returning id
        """,
        (
            loan_id,
            f"X7-PEN-CONTRACT-{suffix}",
            RELEASE_DATE,
            RELEASE_DATE,
            __import__("json").dumps(settings),
            actor_id,
        ),
    ).fetchone()[0]
    rows = connection.execute(
        """
        insert into lending.loan_contract_installments (
            schedule_id, installment_number, due_date,
            contractual_amount, principal_component, interest_component
        ) values
            (%s, 1, %s, 507.00, 500.00, 7.00),
            (%s, 2, %s, 507.00, 500.00, 7.00)
        returning id, installment_number
        """,
        (schedule_id, RELEASE_DATE + timedelta(days=1), schedule_id, MATURITY),
    ).fetchall()
    installment_ids = {int(number): installment_id for installment_id, number in rows}
    connection.execute(
        """
        insert into lending.loan_contract_schedule_registrations (
            schedule_id, evidence_basis, evidence_reference,
            verification_note, verified_by_user_id
        ) values (%s, 'signed_contract', %s, %s, %s)
        """,
        (
            schedule_id,
            f"X7-PEN-SIGNED-{suffix}",
            "Borrower accepted the exact immutable 7x7 schedule and disclosure.",
            actor_id,
        ),
    )
    return {
        "actor_id": actor_id,
        "device_id": device_id,
        "client_id": client_id,
        "loan_id": loan_id,
        "schedule_id": schedule_id,
        "review_id": review_id,
        "fingerprint": fingerprint,
        "installments": installment_ids,
    }


def _payment(
    connection,
    *,
    case: dict[str, object],
    collection_date: date,
    amount: Decimal,
    sequence: int,
    accepted_at: datetime | None = None,
) -> UUID:
    accepted = accepted_at or datetime.now(timezone.utc)
    return connection.execute(
        """
        insert into lending.collection_transactions (
            idempotency_key, loan_id, client_id, collector_user_id,
            registered_device_id, route_entry_id, collection_date,
            entry_type, amount, applied_amount, unallocated_amount,
            allocation_state, accepted_at, recorded_at, device_sequence,
            note, previous_balance, official_balance, pass_count_after,
            advance_until_after, receipt_number, details
        ) values (
            %s, %s, %s, %s, %s, %s, %s,
            'payment', %s, %s, 0.00, 'fully_allocated',
            %s, %s, %s, '', 1000.00, 1000.00, 0,
            null, %s, '{}'::jsonb
        ) returning id
        """,
        (
            uuid4(),
            case["loan_id"],
            case["client_id"],
            case["actor_id"],
            case["device_id"],
            case["loan_id"],
            collection_date,
            amount,
            amount,
            accepted,
            accepted,
            sequence,
            f"X7-PEN-R-{uuid4().hex[:10]}",
        ),
    ).fetchone()[0]


def _project(connection, *, case: dict[str, object], as_of_date: date) -> SevenBySevenPenaltyState:
    with connection.cursor() as cursor:
        return project_verified_seven_by_seven_penalty_state(
            cursor,
            loan_id=case["loan_id"],
            as_of_date=as_of_date,
        )


def _declare_management_no_collection(
    connection,
    *,
    case: dict[str, object],
    no_collection_date: date,
    new_effective_due_date: date,
) -> None:
    installment_id = case["installments"][2]
    adjustment_id = uuid4()
    connection.execute(
        """
        insert into lending.loan_schedule_operational_state (
            schedule_id, operational_version, updated_by_user_id
        ) values (%s, 1, %s)
        on conflict (schedule_id) do update
        set operational_version = excluded.operational_version,
            updated_by_user_id = excluded.updated_by_user_id,
            updated_at = now()
        """,
        (case["schedule_id"], case["actor_id"]),
    )
    connection.execute(
        """
        insert into lending.loan_schedule_adjustments (
            id, loan_id, schedule_id, adjustment_type,
            no_collection_date, event_date, reason, expected_operational_version,
            resulting_operational_version, actor_user_id
        ) values (%s, %s, %s, 'no_collection', %s, %s, %s, 0, 1, %s)
        """,
        (
            adjustment_id,
            case["loan_id"],
            case["schedule_id"],
            no_collection_date,
            no_collection_date,
            "Management-approved weather suspension",
            case["actor_id"],
        ),
    )
    connection.execute(
        """
        insert into lending.loan_schedule_adjustment_items (
            adjustment_id, installment_id, installment_number,
            contractual_due_date, prior_effective_due_date,
            new_effective_due_date, contractual_amount
        ) values (%s, %s, 2, %s, %s, %s, 507.00)
        """,
        (
            adjustment_id,
            installment_id,
            MATURITY,
            MATURITY,
            new_effective_due_date,
        ),
    )
    connection.execute(
        """
        insert into lending.loan_installment_operational_dates (
            installment_id, effective_due_date, last_adjustment_id,
            updated_by_user_id
        ) values (%s, %s, %s, %s)
        on conflict (installment_id) do update
        set effective_due_date = excluded.effective_due_date,
            last_adjustment_id = excluded.last_adjustment_id,
            updated_by_user_id = excluded.updated_by_user_id,
            updated_at = now()
        """,
        (
            installment_id,
            new_effective_due_date,
            adjustment_id,
            case["actor_id"],
        ),
    )


def test_legacy_signed_schedule_without_penalty_authority_fails_closed() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        case = _seed_case(connection, suffix=uuid4().hex[:10], penalty_authority=False)
        state = _project(connection, case=case, as_of_date=FIRST_PENALTY_DAY)
        assert state.status == "management_review_required"
        assert state.projected_penalty == Decimal("0.00")
        assert state.assessed_penalty_balance == Decimal("0.00")
        assert state.management_review_required_reason
        connection.rollback()


def test_signed_maturity_boundary_and_lower_legal_rate_are_authoritative() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        normal = _seed_case(connection, suffix=uuid4().hex[:10])
        at_maturity = _project(connection, case=normal, as_of_date=MATURITY)
        assert at_maturity.status == "not_applicable"
        assert at_maturity.projected_penalty == Decimal("0.00")

        first_day = _project(connection, case=normal, as_of_date=FIRST_PENALTY_DAY)
        assert first_day.contractual_maturity == MATURITY
        assert first_day.penalty_base == Decimal("1014.00")
        assert first_day.effective_monthly_rate == Decimal("0.030000")
        assert first_day.projected_penalty == Decimal("1.01")

        lower = _seed_case(
            connection,
            suffix=uuid4().hex[:10],
            legal_rate_ceiling=Decimal("0.020000"),
        )
        day30 = _project(
            connection,
            case=lower,
            as_of_date=FIRST_PENALTY_DAY + timedelta(days=29),
        )
        assert day30.effective_monthly_rate == Decimal("0.020000")
        assert day30.projected_penalty == Decimal("20.28")
        connection.rollback()


def test_lifetime_headroom_clamps_and_never_uses_payment_to_recreate_capacity() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        case = _seed_case(
            connection,
            suffix=uuid4().hex[:10],
            lifetime_ceiling=Decimal("20.00"),
            counted_cost_at_lock=Decimal("14.00"),
        )
        state = _project(
            connection,
            case=case,
            as_of_date=FIRST_PENALTY_DAY + timedelta(days=29),
        )
        assert state.remaining_cost_headroom == Decimal("6.00")
        assert state.projected_penalty == Decimal("6.00")
        connection.rollback()


def test_management_no_collection_protects_only_deferred_amount_until_effective_due_date() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        case = _seed_case(connection, suffix=uuid4().hex[:10])
        protected_through = MATURITY + timedelta(days=3)
        _declare_management_no_collection(
            connection,
            case=case,
            no_collection_date=FIRST_PENALTY_DAY,
            new_effective_due_date=protected_through,
        )

        first_day = _project(connection, case=case, as_of_date=FIRST_PENALTY_DAY)
        assert first_day.penalty_base == Decimal("507.00")
        assert first_day.projected_penalty == Decimal("0.51")

        effective_day = _project(connection, case=case, as_of_date=protected_through)
        assert effective_day.projected_penalty == Decimal("1.52")

        first_unprotected = _project(
            connection,
            case=case,
            as_of_date=protected_through + timedelta(days=1),
        )
        assert first_unprotected.projected_penalty == Decimal("2.54")
        connection.rollback()


def test_post_maturity_payment_reduces_penalty_base_only_starting_next_day() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        case = _seed_case(connection, suffix=uuid4().hex[:10])
        payment_day = FIRST_PENALTY_DAY + timedelta(days=4)
        _payment(
            connection,
            case=case,
            collection_date=payment_day,
            amount=Decimal("514.00"),
            sequence=1,
        )
        state = _project(
            connection,
            case=case,
            as_of_date=FIRST_PENALTY_DAY + timedelta(days=9),
        )
        assert state.projected_penalty == Decimal("7.57")
        assert state.penalty_base == Decimal("500.00")
        connection.rollback()


def test_freeze_is_same_day_idempotent_and_evidence_is_immutable() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        case = _seed_case(connection, suffix=uuid4().hex[:10])
        first_tx = _payment(
            connection,
            case=case,
            collection_date=FIRST_PENALTY_DAY,
            amount=Decimal("2.00"),
            sequence=1,
        )
        with connection.cursor() as cursor:
            frozen = freeze_verified_seven_by_seven_penalty_assessment(
                cursor,
                loan_id=case["loan_id"],
                through_date=FIRST_PENALTY_DAY,
                source_transaction_id=first_tx,
            )
        assert frozen.assessed_penalty_balance == Decimal("1.01")

        second_tx = _payment(
            connection,
            case=case,
            collection_date=FIRST_PENALTY_DAY,
            amount=Decimal("2.00"),
            sequence=2,
        )
        with connection.cursor() as cursor:
            second = freeze_verified_seven_by_seven_penalty_assessment(
                cursor,
                loan_id=case["loan_id"],
                through_date=FIRST_PENALTY_DAY,
                source_transaction_id=second_tx,
            )
        assert second.assessed_penalty_balance == Decimal("1.01")
        assert connection.execute(
            "select count(*) from lending.seven_by_seven_penalty_assessments where loan_id = %s",
            (case["loan_id"],),
        ).fetchone()[0] == 1

        assessment_id = connection.execute(
            "select id from lending.seven_by_seven_penalty_assessments where loan_id = %s",
            (case["loan_id"],),
        ).fetchone()[0]
        connection.execute("savepoint immutable_penalty")
        with pytest.raises(psycopg.Error):
            connection.execute(
                "update lending.seven_by_seven_penalty_assessments set assessed_penalty_amount = 9.99 where id = %s",
                (assessment_id,),
            )
        connection.execute("rollback to savepoint immutable_penalty")
        connection.rollback()


def test_penalty_cash_allocation_is_aggregate_capped_and_idempotent_per_transaction() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        case = _seed_case(connection, suffix=uuid4().hex[:10])
        tx = _payment(
            connection,
            case=case,
            collection_date=FIRST_PENALTY_DAY,
            amount=Decimal("5.00"),
            sequence=1,
        )
        with connection.cursor() as cursor:
            freeze_verified_seven_by_seven_penalty_assessment(
                cursor,
                loan_id=case["loan_id"],
                through_date=FIRST_PENALTY_DAY,
                source_transaction_id=tx,
            )
            first = allocate_verified_seven_by_seven_penalty_cash(
                cursor,
                loan_id=case["loan_id"],
                transaction_id=tx,
                amount_applied=Decimal("1.01"),
            )
            repeated = allocate_verified_seven_by_seven_penalty_cash(
                cursor,
                loan_id=case["loan_id"],
                transaction_id=tx,
                amount_applied=Decimal("1.01"),
            )
        assert first == repeated
        assert connection.execute(
            "select count(*), sum(amount_applied) from lending.seven_by_seven_penalty_payment_allocations where transaction_id = %s",
            (tx,),
        ).fetchone() == (1, Decimal("1.01"))
        connection.rollback()


def test_voided_assessment_source_or_later_backdated_cash_forces_management_review() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        case = _seed_case(connection, suffix=uuid4().hex[:10])
        through_date = FIRST_PENALTY_DAY + timedelta(days=4)
        source_tx = _payment(
            connection,
            case=case,
            collection_date=through_date,
            amount=Decimal("2.00"),
            sequence=1,
        )
        with connection.cursor() as cursor:
            freeze_verified_seven_by_seven_penalty_assessment(
                cursor,
                loan_id=case["loan_id"],
                through_date=through_date,
                source_transaction_id=source_tx,
            )
        connection.commit()

        voided_at = datetime.now(timezone.utc)
        void_reason = "Task 4 synthetic audited source void"
        connection.execute(
            """
            insert into lending.collection_transaction_voids (
                transaction_id,
                voided_by_user_id,
                reason,
                transaction_snapshot,
                previous_covered_dates,
                state_before,
                state_after,
                voided_at
            ) values (
                %s, %s, %s,
                '{}'::jsonb,
                ARRAY[]::date[],
                '{}'::jsonb,
                '{}'::jsonb,
                %s
            )
            """,
            (
                source_tx,
                case["actor_id"],
                void_reason,
                voided_at,
            ),
        )
        connection.execute(
            """
            update lending.collection_transactions
            set is_voided = true,
                voided_at = %s,
                voided_by_user_id = %s,
                void_reason = %s
            where id = %s
            """,
            (
                voided_at,
                case["actor_id"],
                void_reason,
                source_tx,
            ),
        )
        voided = _project(
            connection,
            case=case,
            as_of_date=through_date + timedelta(days=1),
        )
        assert voided.status == "management_review_required"
        assert voided.projected_penalty == Decimal("0.00")
        connection.rollback()

    with psycopg.connect(DATABASE_URL) as connection:
        case = _seed_case(connection, suffix=uuid4().hex[:10])
        source_tx = _payment(
            connection,
            case=case,
            collection_date=through_date,
            amount=Decimal("2.00"),
            sequence=1,
        )
        with connection.cursor() as cursor:
            freeze_verified_seven_by_seven_penalty_assessment(
                cursor,
                loan_id=case["loan_id"],
                through_date=through_date,
                source_transaction_id=source_tx,
            )
        connection.commit()

        _payment(
            connection,
            case=case,
            collection_date=FIRST_PENALTY_DAY + timedelta(days=1),
            amount=Decimal("10.00"),
            sequence=2,
            accepted_at=datetime.now(timezone.utc) + timedelta(seconds=1),
        )
        backdated = _project(
            connection,
            case=case,
            as_of_date=through_date + timedelta(days=1),
        )
        assert backdated.status == "management_review_required"
        assert backdated.projected_penalty == Decimal("0.00")
        connection.rollback()


def test_concurrent_same_day_freeze_serializes_to_one_new_assessment() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as setup:
        case = _seed_case(setup, suffix=suffix)
        tx1 = _payment(
            setup,
            case=case,
            collection_date=FIRST_PENALTY_DAY,
            amount=Decimal("2.00"),
            sequence=1,
        )
        tx2 = _payment(
            setup,
            case=case,
            collection_date=FIRST_PENALTY_DAY,
            amount=Decimal("2.00"),
            sequence=2,
        )
        setup.commit()

    def freeze(transaction_id: UUID) -> Decimal:
        assert DATABASE_URL is not None
        with psycopg.connect(DATABASE_URL) as connection:
            with connection.cursor() as cursor:
                state = freeze_verified_seven_by_seven_penalty_assessment(
                    cursor,
                    loan_id=case["loan_id"],
                    through_date=FIRST_PENALTY_DAY,
                    source_transaction_id=transaction_id,
                )
            connection.commit()
            return state.assessed_penalty_balance

    with ThreadPoolExecutor(max_workers=2) as pool:
        balances = tuple(pool.map(freeze, (tx1, tx2)))

    assert balances == (Decimal("1.01"), Decimal("1.01"))
    with psycopg.connect(DATABASE_URL) as check:
        row = check.execute(
            "select count(*), sum(assessed_penalty_amount) from lending.seven_by_seven_penalty_assessments where loan_id = %s",
            (case["loan_id"],),
        ).fetchone()
        assert row == (1, Decimal("1.01"))

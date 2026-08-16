from __future__ import annotations

from pathlib import Path


CALC_RULES = Path("spina_app/calculation_rules.py")
PARITY_MATRIX = Path(
    "gilbic_backend/tests/test_seven_by_seven_desktop_server_parity_matrix.py"
)
POSTGRES_PARITY = Path(
    "gilbic_backend/tests/test_seven_by_seven_desktop_server_postgres_parity.py"
)
MOBILE_POSTGRES = Path(
    "gilbic_backend/tests/test_seven_by_seven_mobile_collection_postgres.py"
)
CONTRACT_TEST = Path("gilbic_backend/tests/test_contract_collection_posting.py")


def replace_between(
    text: str,
    *,
    start_marker: str,
    end_marker: str | None,
    replacement: str,
    label: str,
) -> str:
    start = text.find(start_marker)
    if start < 0:
        if replacement in text:
            return text
        raise RuntimeError(f"{label}: start marker not found")
    if end_marker is None:
        end = len(text)
    else:
        end = text.find(end_marker, start + len(start_marker))
        if end < 0:
            raise RuntimeError(f"{label}: end marker not found")
    return text[:start] + replacement + text[end:]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count == 1:
        return text.replace(old, new, 1)
    if count == 0 and new in text:
        return text
    raise RuntimeError(f"{label}: expected one old match, got {count}")


def patch_desktop_allocator() -> None:
    text = CALC_RULES.read_text(encoding="utf-8")
    replacement = '''def allocate_x7_payments(
    principal: Any,
    payment_start: Any,
    payments: Iterable[Any],
    as_of_date: Any = None,
) -> dict[str, float]:
    """Allocate every distinct positive 7x7 receipt to interest first, then principal.

    Daily interest is fixed from the recorded loan principal for the whole cycle;
    a falling remaining balance does not lower it. Multiple genuine receipts may
    occur on the same calendar date. They are preserved in authoritative input
    order: the first receipt for a date accrues the elapsed calendar-day interest,
    while later same-day receipts accrue zero additional days and continue settling
    that day's interest/principal. Technical retries must be removed by the
    transaction/idempotency layer before reaching this pure allocator.
    """
    principal_f = max(0.0, _as_float(principal))
    fixed_daily_interest = x7_daily_interest(principal_f)
    start = _as_date(payment_start) or date.today()
    end = _as_date(as_of_date) or date.today()
    if end < start:
        end = start

    effective_receipts: list[tuple[date, int, float]] = []
    for index, item in enumerate(payments or ()):
        raw_date, raw_amount = _payment_parts(item)
        pay_date = _as_date(raw_date)
        amount = _as_float(raw_amount)
        if pay_date is None or amount <= 0.0 or pay_date < start or pay_date > end:
            continue
        effective_receipts.append((pay_date, index, amount))
    effective_receipts.sort(key=lambda row: (row[0], row[1]))

    remaining_principal = principal_f
    interest_arrears = 0.0
    interest_paid_total = 0.0
    principal_paid_total = 0.0
    total_collected = 0.0
    previous_date = start - timedelta(days=1)

    for pay_date, _, amount in effective_receipts:
        gap = max(0, (pay_date - previous_date).days)
        interest_due = fixed_daily_interest * float(gap) + interest_arrears
        interest_paid = min(amount, interest_due)
        principal_paid = min(remaining_principal, max(0.0, amount - interest_paid))

        interest_paid_total += interest_paid
        principal_paid_total += principal_paid
        total_collected += amount
        remaining_principal = max(0.0, remaining_principal - principal_paid)
        interest_arrears = max(0.0, interest_due - interest_paid)
        previous_date = pay_date

        if remaining_principal <= 0.004 and interest_arrears <= 0.004:
            remaining_principal = 0.0
            interest_arrears = 0.0
            break

    if remaining_principal > 0.0:
        tail_gap = max(0, (end - previous_date).days)
        if tail_gap:
            interest_arrears += fixed_daily_interest * float(tail_gap)

    payoff = max(0.0, remaining_principal + interest_arrears)
    completion = (principal_paid_total / principal_f * 100.0) if principal_f > 0.0 else 0.0
    return {
        "principal": round(principal_f, 2),
        "interest_basis_principal": round(principal_f, 2),
        "daily_interest": round(fixed_daily_interest, 2),
        "total_collected": round(total_collected, 2),
        "interest_paid": round(interest_paid_total, 2),
        "principal_paid": round(principal_paid_total, 2),
        "remaining_principal": round(remaining_principal, 2),
        "interest_arrears": round(interest_arrears, 2),
        "payoff_with_interest": round(payoff, 2),
        "completion_pct": float(completion),
    }
'''
    text = replace_between(
        text,
        start_marker="def allocate_x7_payments(",
        end_marker=None,
        replacement=replacement,
        label="desktop 7x7 allocator",
    )
    CALC_RULES.write_text(text, encoding="utf-8")


def patch_parity_matrix() -> None:
    text = PARITY_MATRIX.read_text(encoding="utf-8")
    helper = '''def _effective_server_events(
    payments: Sequence[Mapping[str, Any]],
    *,
    payment_start: date,
    as_of_date: date,
) -> tuple[SevenBySevenCashEvent, ...]:
    """Preserve every distinct positive receipt in authoritative date/input order."""

    eligible: list[tuple[date, int, Mapping[str, Any]]] = []
    for index, payment in enumerate(payments, start=1):
        payment_date = payment.get("date")
        amount = _money(payment.get("payment", payment.get("amount", 0)))
        if not isinstance(payment_date, date):
            continue
        if amount <= Decimal("0.00"):
            continue
        if payment_date < payment_start or payment_date > as_of_date:
            continue
        eligible.append((payment_date, index, payment))

    return tuple(
        SevenBySevenCashEvent(
            event_id=_event_id(index, payment),
            collection_date=payment_date,
            amount=_money(payment.get("payment", payment.get("amount", 0))),
        )
        for payment_date, index, payment in sorted(
            eligible,
            key=lambda item: (item[0], item[1]),
        )
    )


'''
    text = replace_between(
        text,
        start_marker="def _effective_server_events(",
        end_marker="def _assert_case_parity(",
        replacement=helper,
        label="parity event boundary",
    )
    same_day_test = '''def test_distinct_same_day_receipts_are_preserved_in_authoritative_order() -> None:
    case = ParityCase(
        name="distinct_same_day_receipts",
        principal=Decimal("3000.00"),
        payment_start=date(2026, 8, 1),
        payments=(
            {"event_id": "first", "date": date(2026, 8, 1), "payment": "10.00"},
            {"event_id": "second", "date": date(2026, 8, 1), "payment": "50.00"},
            {"event_id": "ignored-zero", "date": date(2026, 8, 2), "payment": "0.00"},
            {"event_id": "next", "date": date(2026, 8, 3), "payment": "42.00"},
        ),
    )

    _assert_case_parity(case)
    events = _effective_server_events(
        case.payments,
        payment_start=case.payment_start,
        as_of_date=date(2026, 8, 3),
    )
    assert [event.event_id for event in events] == ["first", "second", "next"]
    assert [event.amount for event in events] == [
        Decimal("10.00"),
        Decimal("50.00"),
        Decimal("42.00"),
    ]


'''
    text = replace_between(
        text,
        start_marker="def test_latest_positive_payment_per_date_is_canonicalized_before_server_allocation()",
        end_marker="def test_renewal_boundary_starts_a_new_independent_original_principal_cycle()",
        replacement=same_day_test,
        label="same-day synthetic parity test",
    )
    PARITY_MATRIX.write_text(text, encoding="utf-8")


def patch_postgres_parity() -> None:
    text = POSTGRES_PARITY.read_text(encoding="utf-8")
    replacement = '''def test_same_day_protected_source_preserves_distinct_receipts_for_server() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    case = b2_matrix.ParityCase(
        name="postgres_same_day_distinct_receipts",
        principal=Decimal("3000.00"),
        payment_start=date(2026, 8, 1),
        payments=(
            {"event_id": "a", "date": date(2026, 8, 1), "payment": "40.00"},
            {"event_id": "b", "date": date(2026, 8, 1), "payment": "50.00"},
        ),
    )

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0064))
            actor_id, _, _, loan_id, device_id = _create_operational_loan(
                connection,
                suffix=suffix,
                principal=case.principal,
                payment_start=case.payment_start,
            )
            _insert_source_rows(
                connection,
                case=case,
                suffix=suffix,
                actor_id=actor_id,
                device_id=device_id,
                loan_id=loan_id,
            )
            active = [row for row in _protected_inventory(connection, loan_id) if row[5]]
            assert len(active) == 2
            assert {row[6] for row in active} == {2}

            server = allocate_seven_by_seven_payments(
                original_principal=case.principal,
                daily_interest_per_1000="7.00",
                payment_start=case.payment_start,
                events=tuple(
                    SevenBySevenCashEvent(
                        event_id=str(row[0]),
                        collection_date=row[1],
                        amount=row[3],
                    )
                    for row in active
                ),
            )
            desktop = allocate_x7_payments(
                principal=case.principal,
                payment_start=case.payment_start,
                payments=case.payments,
                as_of_date=case.payment_start,
            )

            assert [line.gap_days for line in server.allocations] == [1, 0]
            assert server.total_interest_paid == Decimal("21.00")
            assert server.total_principal_paid == Decimal("69.00")
            assert server.closing_remaining_principal == Decimal("2931.00")
            assert server.total_interest_paid == _money(desktop["interest_paid"])
            assert server.total_principal_paid == _money(desktop["principal_paid"])
            assert server.closing_remaining_principal == _money(
                desktop["remaining_principal"]
            )
            assert _money(desktop["total_collected"]) == Decimal("90.00")

            assert connection.execute(
                """
                select coalesce((loan_type.settings->>'mobile_collections_enabled')::boolean, false)
                from lending.loans loan
                join lending.loan_types loan_type on loan_type.id=loan.loan_type_id
                where loan.id=%s
                """,
                (loan_id,),
            ).fetchone()[0] is False
        finally:
            connection.rollback()
'''
    text = replace_between(
        text,
        start_marker="def test_same_day_protected_source_ambiguity_is_not_silently_normalized_for_server()",
        end_marker=None,
        replacement=replacement,
        label="same-day PostgreSQL parity test",
    )
    POSTGRES_PARITY.write_text(text, encoding="utf-8")


def patch_mobile_policy_expectation() -> None:
    text = MOBILE_POSTGRES.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '"seven_by_seven_operational_allocator_v1",',
        '"seven_by_seven_operational_allocator_v2",',
        "mobile 7x7 policy expectation",
    )
    MOBILE_POSTGRES.write_text(text, encoding="utf-8")


def patch_contract_bridge_test() -> None:
    text = CONTRACT_TEST.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from gilbic_backend.collection_correction_repository import CollectionCorrectionInvalid\n",
        "from gilbic_backend.collection_correction_repository import CollectionCorrectionInvalid\n"
        "from gilbic_backend.concurrent_receipt_collection_posting import (\n"
        "    ConcurrentReceiptSafeCollectionPostingBridge,\n"
        ")\n",
        "concurrent bridge import",
    )
    text = replace_once(
        text,
        "from gilbic_backend.per_loan_contract_collection import (\n"
        "    PerLoanContractAwareCrossCollectorCollectionPostingBridge,\n"
        ")\n",
        "from gilbic_backend.per_loan_contract_collection import (\n"
        "    PerLoanContractAwareCrossCollectorCollectionPostingBridge,\n"
        ")\n"
        "from gilbic_backend.seven_by_seven_collection_posting import (\n"
        "    SevenBySevenAwarePerLoanContractCollectionPostingBridge,\n"
        ")\n",
        "7x7 bridge import",
    )
    replacement = '''def test_stage5e46b_live_collection_api_preserves_per_loan_contract_bridge() -> None:
    assert "ConcurrentReceiptSafeCollectionPostingBridge" in COLLECTION_API
    assert "posting_bridge=ConcurrentReceiptSafeCollectionPostingBridge()" in COLLECTION_API
    assert issubclass(
        ConcurrentReceiptSafeCollectionPostingBridge,
        SevenBySevenAwarePerLoanContractCollectionPostingBridge,
    )
    assert "PerLoanContractAwareCrossCollectorCollectionPostingBridge" in SEVEN_BY_SEVEN_COLLECTION
    assert "class SevenBySevenAwarePerLoanContractCollectionPostingBridge" in SEVEN_BY_SEVEN_COLLECTION


'''
    text = replace_between(
        text,
        start_marker="def test_stage5e46b_live_collection_api_preserves_per_loan_contract_bridge()",
        end_marker="def test_stage5e44_correction_api_uses_contract_safe_repository()",
        replacement=replacement,
        label="live collection bridge test",
    )
    CONTRACT_TEST.write_text(text, encoding="utf-8")


def main() -> None:
    patch_desktop_allocator()
    patch_parity_matrix()
    patch_postgres_parity()
    patch_mobile_policy_expectation()
    patch_contract_bridge_test()
    print("Patched Desktop/server same-day 7x7 receipt parity and current live bridge assertions.")


if __name__ == "__main__":
    main()

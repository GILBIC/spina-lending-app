from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from gilbic_backend.eir_cash_allocation import EirDailyAccrual
from gilbic_backend.greenfield_regular_eir_rollforward import (
    GreenfieldRegularRenewalRollForward,
)
from gilbic_backend.greenfield_regular_renewal_boundary_eir import (
    build_greenfield_regular_renewal_boundary_eir_preview,
)
from gilbic_backend.regular_eir_accrual_journal_preview import (
    AccountingFiscalPeriodReference,
)


LOAN_ID = UUID("11111111-1111-4111-8111-111111111111")
EXECUTION_ID = UUID("22222222-2222-4222-8222-222222222222")
P1 = UUID("33333333-3333-4333-8333-333333333333")
P2 = UUID("44444444-4444-4444-8444-444444444444")


def _rollforward(*, target: date, daily_rows, tail: str):
    rows = tuple(daily_rows)
    anchor = rows[0].accrual_date - timedelta(days=1) if rows else target - timedelta(days=1)
    return GreenfieldRegularRenewalRollForward(
        loan_id=LOAN_ID,
        anchor_date=anchor,
        target_date=target,
        contractual_due_date=date(2026, 11, 29),
        daily_eir=Decimal("0.003"),
        initial_gross_carrying_amount=Decimal("5000.00"),
        initial_accrued_interest_component=Decimal("0.00"),
        initial_loan_component=Decimal("5000.00"),
        source_event_count=0,
        allocation_count=0,
        disposition="greenfield_regular_renewal_rollforward_preview_ready",
        blocker_code=None,
        message="ready",
        total_effective_interest_accrued=Decimal(tail),
        tail_effective_interest_accrued=Decimal(tail),
        gross_carrying_amount_at_target=Decimal("5000.00") + Decimal(tail),
        accrued_interest_component_at_target=Decimal(tail),
        loan_component_at_target=Decimal("5000.00"),
        allocations=(),
        tail_daily_accruals=rows,
        measurement_preview_ready=True,
        accounting_carrying_amount_ready=False,
        journal_lines_enabled=False,
        automatic_source_posting=False,
    )


def _daily(day: date, opening: str, interest: str):
    opening_value = Decimal(opening)
    interest_value = Decimal(interest)
    return EirDailyAccrual(
        accrual_date=day,
        opening_gross_carrying_raw=opening_value,
        effective_interest_raw=interest_value,
        closing_gross_carrying_raw=opening_value + interest_value,
    )


def test_single_period_renewal_boundary_eir_preview_is_balanced_and_read_only():
    rollforward = _rollforward(
        target=date(2026, 8, 3),
        tail="30.05",
        daily_rows=(
            _daily(date(2026, 8, 2), "5000.00", "15.00"),
            _daily(date(2026, 8, 3), "5015.00", "15.045"),
        ),
    )
    periods = (
        AccountingFiscalPeriodReference(
            period_id=P1,
            label="August 2026",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
            status="open",
        ),
    )

    preview = build_greenfield_regular_renewal_boundary_eir_preview(
        rollforward,
        renewal_execution_event_id=EXECUTION_ID,
        fiscal_periods=periods,
    )

    assert preview.disposition == "renewal_boundary_eir_journal_preview_ready"
    assert preview.blocker_code is None
    assert preview.amount == Decimal("30.05")
    assert preview.total_debit == Decimal("30.05")
    assert preview.total_credit == Decimal("30.05")
    assert preview.balanced is True
    assert preview.posting_eligible is False
    assert preview.automatic_source_posting is False
    assert len(preview.period_proposals) == 1
    proposal = preview.period_proposals[0]
    assert proposal.fiscal_period_id == P1
    assert proposal.posting_date == date(2026, 8, 3)
    assert proposal.source_type == "regular_renewal_eir_accrual"
    assert proposal.source_event_key == (
        f"renewal_eir_accrual:{EXECUTION_ID}:fiscal_period:{P1}"
    )
    assert [
        (line.account_system_key, line.side, line.amount)
        for line in proposal.proposed_lines
    ] == [
        ("accrued_interest_receivable", "debit", Decimal("30.05")),
        ("interest_income_regular", "credit", Decimal("30.05")),
    ]


def test_cross_period_tail_reuses_exact_deterministic_cent_allocation():
    rollforward = _rollforward(
        target=date(2026, 9, 1),
        tail="30.05",
        daily_rows=(
            _daily(date(2026, 8, 31), "5000.00", "15.001"),
            _daily(date(2026, 9, 1), "5015.001", "15.044"),
        ),
    )
    periods = (
        AccountingFiscalPeriodReference(
            period_id=P1,
            label="August 2026",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
            status="open",
        ),
        AccountingFiscalPeriodReference(
            period_id=P2,
            label="September 2026",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
            status="open",
        ),
    )

    preview = build_greenfield_regular_renewal_boundary_eir_preview(
        rollforward,
        renewal_execution_event_id=EXECUTION_ID,
        fiscal_periods=periods,
    )

    assert preview.disposition == "renewal_boundary_eir_journal_preview_ready"
    assert preview.amount == Decimal("30.05")
    assert [item.amount for item in preview.period_proposals] == [
        Decimal("15.00"),
        Decimal("15.05"),
    ]
    assert sum(
        (item.amount for item in preview.period_proposals), Decimal("0")
    ) == Decimal("30.05")
    assert preview.total_debit == preview.total_credit == Decimal("30.05")
    assert preview.posting_eligible is False


def test_boundary_preview_fails_closed_when_fiscal_period_is_not_open():
    rollforward = _rollforward(
        target=date(2026, 8, 2),
        tail="15.00",
        daily_rows=(
            _daily(date(2026, 8, 2), "5000.00", "15.00"),
        ),
    )
    periods = (
        AccountingFiscalPeriodReference(
            period_id=P1,
            label="August 2026",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
            status="closed",
        ),
    )

    preview = build_greenfield_regular_renewal_boundary_eir_preview(
        rollforward,
        renewal_execution_event_id=EXECUTION_ID,
        fiscal_periods=periods,
    )

    assert preview.disposition == "renewal_boundary_eir_journal_preview_blocked"
    assert preview.blocker_code == "renewal_boundary_fiscal_period_not_ready"
    assert preview.period_proposals == ()
    assert preview.posting_eligible is False
    assert preview.automatic_source_posting is False

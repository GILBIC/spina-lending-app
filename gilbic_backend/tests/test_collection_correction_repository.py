from datetime import date

from gilbic_backend.collection_correction_repository import PostgresCollectionCorrectionRepository


def test_pass_correction_preserves_existing_advance_until() -> None:
    result = PostgresCollectionCorrectionRepository._corrected_advance_until_after(
        entry_type="pass",
        advance_until_before=date(2026, 8, 5),
        selected_dates=(),
    )
    assert result == date(2026, 8, 5)


def test_payment_correction_does_not_extend_advance_from_payment_date() -> None:
    result = PostgresCollectionCorrectionRepository._corrected_advance_until_after(
        entry_type="payment",
        advance_until_before=date(2026, 8, 5),
        selected_dates=(date(2026, 8, 16),),
    )
    assert result == date(2026, 8, 5)


def test_advance_correction_may_extend_existing_advance_until() -> None:
    result = PostgresCollectionCorrectionRepository._corrected_advance_until_after(
        entry_type="advance",
        advance_until_before=date(2026, 8, 5),
        selected_dates=(date(2026, 8, 10), date(2026, 8, 16)),
    )
    assert result == date(2026, 8, 16)


def test_advance_correction_never_shortens_existing_advance_until() -> None:
    result = PostgresCollectionCorrectionRepository._corrected_advance_until_after(
        entry_type="advance",
        advance_until_before=date(2026, 8, 20),
        selected_dates=(date(2026, 8, 16),),
    )
    assert result == date(2026, 8, 20)

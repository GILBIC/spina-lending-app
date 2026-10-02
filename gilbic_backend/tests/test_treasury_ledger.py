from datetime import datetime, timezone
from decimal import Decimal


def test_cutoff_includes_only_verified_later_movements():
    from gilbic_backend.treasury_repository import expected_balance

    opening = {
        "amount": Decimal("10000.00"),
        "cutoff": datetime(2026, 10, 1, tzinfo=timezone.utc),
    }
    cutoff = datetime(2026, 10, 2, tzinfo=timezone.utc)
    lines = [
        {"signed_amount": Decimal(value), "effective_at": cutoff}
        for value in ["1000", "-2000", "-300", "-15"]
    ]
    lines += [{"signed_amount": Decimal(1234), "effective_at": opening["cutoff"]}]
    assert expected_balance(opening, lines, cutoff) == Decimal("8685.00")
    assert Decimal("8670.00") - expected_balance(opening, lines, cutoff) == Decimal(
        "-15.00"
    )
    assert expected_balance(None, lines, cutoff) is None

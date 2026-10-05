from types import SimpleNamespace

from gilbic_backend.collector_accounting_capability import (
    collector_accounting_capability,
)


def test_incremental_deployment_keeps_missing_adapter_unavailable():
    conn = SimpleNamespace(
        execute=lambda statement: SimpleNamespace(fetchone=lambda: {"available": False})
    )
    state = collector_accounting_capability(conn)
    assert state["available"] is False
    assert state["supported_source_families"] == []
    assert state["automatic_posting"] is False


def test_installed_adapter_advertises_only_explicit_reviewed_source_families():
    conn = SimpleNamespace(
        execute=lambda statement: SimpleNamespace(fetchone=lambda: {"available": True})
    )
    state = collector_accounting_capability(conn)
    assert state["available"] is True
    assert state["supported_source_families"] == [
        "settlement",
        "recognition",
        "return_debit",
        "return_confirmation",
        "return_reversal",
    ]
    assert state["automatic_posting"] is False
    assert state["review_required"] is True
    assert state["comprehensive_source_coverage"] is False
    assert "opening" in state["unsupported_source_families"]
    assert "historical_correction" in state["unsupported_source_families"]

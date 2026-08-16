from __future__ import annotations

from uuid import UUID


def collector_may_correct_unremitted(
    *,
    actor_user_id: UUID,
    recorder_user_id: UUID,
    assigned_collector_user_id: UUID | None,
    collection_origin: str,
) -> bool:
    """Return whether a Collector may correct one unlocked receipt.

    The original recorder always keeps pre-remittance correction authority.
    For a true cross-collector receipt, the assigned route owner shares that
    authority. No other collection origin grants an assigned-area bypass.
    Remittance/lock checks remain the caller's separate hard gate.
    """

    if actor_user_id == recorder_user_id:
        return True
    return (
        collection_origin.strip().lower() == "cross_collector"
        and assigned_collector_user_id is not None
        and actor_user_id == assigned_collector_user_id
    )


def correction_revision_is_current(
    *,
    expected_route_revision: str,
    loan_id: UUID,
    state_version: int,
) -> bool:
    """Fail stale correction drafts closed against current loan state."""

    current = f"loan:{loan_id}:v{state_version}"
    return expected_route_revision.strip() == current

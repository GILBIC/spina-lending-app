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

    Collector correction authority stays with the original recorder. Temporary
    delegated area access never transfers ownership of another Collector's
    historical receipt to the assigned route owner. Remittance/lock checks
    remain the caller's separate hard gate.
    """

    del assigned_collector_user_id, collection_origin
    return actor_user_id == recorder_user_id


def correction_revision_is_current(
    *,
    expected_route_revision: str,
    loan_id: UUID,
    state_version: int,
) -> bool:
    """Fail stale correction drafts closed against current loan state."""

    current = f"loan:{loan_id}:v{state_version}"
    return expected_route_revision.strip() == current

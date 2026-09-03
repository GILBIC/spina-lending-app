from __future__ import annotations

from uuid import UUID

from gilbic_backend.collection_correction_authority import (
    collector_may_correct_unremitted,
    correction_revision_is_current,
)


RECORDER = UUID("11111111-1111-4111-8111-111111111111")
ASSIGNED = UUID("22222222-2222-4222-8222-222222222222")
OTHER = UUID("33333333-3333-4333-8333-333333333333")
LOAN = UUID("44444444-4444-4444-8444-444444444444")


def test_original_recorder_keeps_unremitted_correction_authority() -> None:
    assert collector_may_correct_unremitted(
        actor_user_id=RECORDER,
        recorder_user_id=RECORDER,
        assigned_collector_user_id=ASSIGNED,
        collection_origin="cross_collector",
    )


def test_assigned_owner_cannot_correct_visiting_collectors_receipt() -> None:
    assert not collector_may_correct_unremitted(
        actor_user_id=ASSIGNED,
        recorder_user_id=RECORDER,
        assigned_collector_user_id=ASSIGNED,
        collection_origin="cross_collector",
    )


def test_assigned_owner_does_not_gain_other_origin_bypass() -> None:
    for origin in ("management_direct", "unassigned_intake", "assigned_route"):
        assert not collector_may_correct_unremitted(
            actor_user_id=ASSIGNED,
            recorder_user_id=RECORDER,
            assigned_collector_user_id=ASSIGNED,
            collection_origin=origin,
        )


def test_unrelated_collector_cannot_correct_cross_collector_receipt() -> None:
    assert not collector_may_correct_unremitted(
        actor_user_id=OTHER,
        recorder_user_id=RECORDER,
        assigned_collector_user_id=ASSIGNED,
        collection_origin="cross_collector",
    )


def test_route_revision_guard_rejects_stale_second_editor() -> None:
    assert correction_revision_is_current(
        expected_route_revision=f"loan:{LOAN}:v7",
        loan_id=LOAN,
        state_version=7,
    )
    assert not correction_revision_is_current(
        expected_route_revision=f"loan:{LOAN}:v7",
        loan_id=LOAN,
        state_version=8,
    )

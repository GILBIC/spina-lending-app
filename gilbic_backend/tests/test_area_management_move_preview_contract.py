from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from gilbic_backend.area_management_api import _move_payload
from gilbic_backend.area_management_repository import AreaCollector


AREA_ID = UUID("33333333-3333-4333-8333-333333333333")
OTHER_AREA_ID = UUID("44444444-4444-4444-8444-444444444444")
COLLECTOR_A_ID = UUID("55555555-5555-4555-8555-555555555551")
COLLECTOR_C_ID = UUID("55555555-5555-4555-8555-555555555553")


def test_move_preview_payload_exposes_operational_impact_for_confirmation() -> None:
    collector_a = AreaCollector(
        user_id=COLLECTOR_A_ID,
        username="collector.a",
        full_name="Collector A",
    )
    collector_c = AreaCollector(
        user_id=COLLECTOR_C_ID,
        username="collector.c",
        full_name="Collector C",
    )
    preview = SimpleNamespace(
        area_uid=AREA_ID,
        old_parent_area_uid=None,
        new_parent_area_uid=OTHER_AREA_ID,
        old_path="Cardona › Calahan",
        new_path="Morong › Destination › Calahan",
        affected_node_count=5,
        clients_affected=23,
        descendant_areas_affected=4,
        effective_collector_before=collector_a,
        effective_collector_after=collector_c,
        stale_delegated_access_count=1,
    )

    payload = _move_payload(preview)

    assert payload["clients_affected"] == 23
    assert payload["descendant_areas_affected"] == 4
    assert payload["effective_collector_before"] == {
        "user_id": str(COLLECTOR_A_ID),
        "username": "collector.a",
        "full_name": "Collector A",
    }
    assert payload["effective_collector_after"] == {
        "user_id": str(COLLECTOR_C_ID),
        "username": "collector.c",
        "full_name": "Collector C",
    }
    assert payload["stale_delegated_access_count"] == 1
    assert payload["affected_node_count"] == 5

"""Source counts govern closing; private amounts still require wallet access."""

import os
from types import SimpleNamespace

import psycopg
from test_period_close_postgres import _move_to_review
from test_source_close_guard_postgres import _event, _post, _prepare
from test_source_close_guard_postgres import source_close as _source_close

from gilbic_backend import period_close_repository as repository

source_close = _source_close


def test_source_details_keep_wallet_history_private_and_queue_fail_closed(
    source_close, monkeypatch
):
    f = source_close
    event = _event(f)
    f["conn"].commit()
    monkeypatch.setattr(
        repository,
        "open_connection",
        lambda: psycopg.connect(os.environ["GILBIC_TEST_DATABASE_URL"]),
    )
    actor = SimpleNamespace(user_id=f["actor"], registered_device_id=f["device"])
    repo = repository.PostgresPeriodCloseRepository()
    coverage = repo.source_coverage(f["period"], actor=actor)
    assert coverage["blocker_count"] == 1
    assert coverage["blockers"] == [
        {
            "source_type": "restricted_source",
            "source_id": None,
            "effective_date": None,
            "amount": None,
            "reason": "treasury_account_access_required",
        }
    ]
    item = repo.get_item(f["period"])
    assert item.close_status == "blocked_unreconciled_sources"
    assert item.source_blocker_count == 1
    assert f["period"] not in {
        x.fiscal_period_id for x in repo.list_items(status="ready_for_review")
    }
    assert repo.summary()["source_review_required_count"] >= 1
    f["conn"].execute(
        "INSERT INTO core.role_permissions(role_id,permission_code) SELECT id,'treasury.view' FROM core.roles WHERE code='management' ON CONFLICT DO NOTHING"
    )
    f["conn"].execute(
        "INSERT INTO treasury.account_access(account_id,user_id,permissions,granted_by) VALUES(%s,%s,ARRAY['treasury.view'],%s)",
        (f["account"], f["actor"], f["actor"]),
    )
    f["conn"].commit()
    assert (
        repo.source_coverage(f["period"], actor=actor)["blockers"][0]["amount"] is None
    )
    f["conn"].execute(
        "UPDATE treasury.account_access SET private_history=true WHERE account_id=%s AND user_id=%s",
        (f["account"], f["actor"]),
    )
    f["conn"].commit()
    detail = repo.source_coverage(f["period"], actor=actor)["blockers"][0]
    assert detail["source_id"] == str(event) and detail["amount"] == "100.00"
    assert "account_id" not in detail
    f["conn"].execute(
        "UPDATE treasury.account_access SET enabled=false WHERE account_id=%s AND user_id=%s",
        (f["account"], f["actor"]),
    )
    f["conn"].commit()
    assert (
        repo.source_coverage(f["period"], actor=actor)["blockers"][0]["source_id"]
        is None
    )


def test_late_sources_remain_in_closed_filter_with_live_warning(
    source_close, monkeypatch
):
    f = source_close
    _move_to_review(f["conn"], f["period"], f["actor"])
    _prepare(f)
    _post(f)
    f["conn"].commit()
    _event(f)
    f["conn"].commit()
    monkeypatch.setattr(
        repository,
        "open_connection",
        lambda: psycopg.connect(os.environ["GILBIC_TEST_DATABASE_URL"]),
    )
    repo = repository.PostgresPeriodCloseRepository()
    closed = {item.fiscal_period_id: item for item in repo.list_items(status="closed")}
    assert closed[f["period"]].close_status == "closed_source_review_required"
    assert f["period"] in {
        item.fiscal_period_id for item in repo.list_items(status="blocked")
    }

"""A close attempt must not deadlock already observed Collector cash acceptance."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import UUID, uuid4

import psycopg
import pytest
import test_collector_surplus_postgres as collector
import test_period_close_postgres as close
from test_collector_surplus_postgres import accept, count
from test_source_close_guard_postgres import MIGRATION, _connect, _instant

surplus = collector.surplus
treasury = collector.treasury


def test_close_yields_to_actual_acceptance_after_cash_event_insert(
    surplus, monkeypatch
):
    t = surplus
    with _connect() as reviewer:
        reviewer.execute(close._body(MIGRATION.read_text(encoding="utf-8")))
        actor = close._management_actor(reviewer, uuid4().hex)
        start = reviewer.execute(
            "SELECT greatest(coalesce(max(end_date)+1,DATE '2045-01-01'),DATE '2045-01-01') FROM accounting.fiscal_periods"
        ).fetchone()[0]
        period = reviewer.execute(
            "SELECT accounting.create_fiscal_period(%s,%s,%s,%s)",
            ("Acceptance race " + uuid4().hex, start, start + timedelta(days=9), actor),
        ).fetchone()[0]
        reviewer.commit()

        # Keep actual count and acceptance within this test's distinct period.
        monkeypatch.setattr(
            t["service"], "clock", lambda: _instant(start + timedelta(days=1))
        )
        recorded_count = count(t, amount="10000.00", counted_at=_instant(start))
        event_inserted = Event()
        continue_acceptance = Event()
        record_event = t["service"].record_verified_event
        inserted = {}

        def pause_after_event(conn, actor, account, event):
            result = record_event(conn, actor, account, event)
            inserted["event_id"] = result[0]["id"]
            event_inserted.set()
            assert continue_acceptance.wait(timeout=10), "Acceptance was not released"
            return result

        monkeypatch.setattr(t["service"], "record_verified_event", pause_after_event)
        with ThreadPoolExecutor(max_workers=1) as pool:
            accepting = pool.submit(accept, t, recorded_count)
            try:
                assert event_inserted.wait(timeout=10), "Acceptance never inserted cash"
                # Baseline blocks on events while holding SHARE on settlements.
                # A timeout bounds that failure without allowing the test to hang.
                reviewer.execute("SET LOCAL statement_timeout='2s'")
                with pytest.raises(
                    psycopg.Error,
                    match="Source activity is in progress; retry period close\\.",
                ) as rejected:
                    close._move_to_review(reviewer, period, actor)
                assert rejected.value.sqlstate == "23514"
            finally:
                reviewer.rollback()
                continue_acceptance.set()
                accepted = accepting.result(timeout=10)

        # The entire real acceptance, including custody and settlement, commits.
        assert (
            reviewer.execute(
                "SELECT status FROM lending.collection_remittances WHERE id=%s",
                (t["remittance_id"],),
            ).fetchone()[0]
            == "received"
        )
        assert (
            reviewer.execute(
                "SELECT event_id FROM treasury.collector_settlements WHERE id=%s",
                (UUID(accepted["result"]["settlement"]["id"]),),
            ).fetchone()[0]
            == inserted["event_id"]
        )
        assert (
            reviewer.execute(
                "SELECT sum(signed_amount) FROM treasury.movement_lines WHERE event_id=%s",
                (inserted["event_id"],),
            ).fetchone()[0]
            == 10000
        )
        assert (
            reviewer.execute(
                "SELECT status FROM accounting.fiscal_periods WHERE id=%s", (period,)
            ).fetchone()[0]
            == "open"
        )

        with (
            pytest.raises(psycopg.Error, match="unreconciled source"),
            reviewer.transaction(),
        ):
            close._move_to_review(reviewer, period, actor)
        assert reviewer.execute(
            "SELECT EXISTS(SELECT 1 FROM accounting.period_source_blockers(%s) WHERE source_id=%s)",
            (period, inserted["event_id"]),
        ).fetchone()[0]

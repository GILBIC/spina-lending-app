"""Commit-equivalent guard flushes for completed actions in a rollback proof."""

from time import perf_counter


def flush_completed_action(conn, phase, timings):
    # The proof uses one rollback transaction for several production requests.
    # Preserve the runner's statement limit and the credential flow's stricter
    # lock limit. No timeout or trigger setting is changed here.
    settings = conn.execute(
        """SELECT
          (SELECT setting::int FROM pg_catalog.pg_settings
           WHERE name='statement_timeout') AS statement_timeout_ms,
          (SELECT setting::int FROM pg_catalog.pg_settings
           WHERE name='lock_timeout') AS lock_timeout_ms,
          (SELECT setting FROM pg_catalog.pg_settings WHERE name='jit') AS jit,
          NOT EXISTS (SELECT 1 FROM pg_catalog.pg_constraint
                      WHERE condeferrable AND NOT condeferred)
            AS all_initially_deferred"""
    ).fetchone()
    assert settings == {
        "statement_timeout_ms": 60000,
        "lock_timeout_ms": 5000,
        "jit": "off",
        "all_initially_deferred": True,
    }, "The aged proof requires unchanged limits and initially deferred guards"
    started = perf_counter()
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
    elapsed = perf_counter() - started
    # A failed flush propagates before restoration. The fixture rolls it back.
    # All deferrable constraints in the pinned schema are initially deferred;
    # restore that mode so the next complete action can insert linked rows.
    conn.execute("SET CONSTRAINTS ALL DEFERRED")
    timings.append({"phase": phase, "elapsed_seconds": round(elapsed, 6)})

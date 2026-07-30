#!/usr/bin/env python3
"""Regression for missing Wave 81 Clients application-form formatters."""
from __future__ import annotations

from datetime import date, datetime


def _parse_day(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value or "")[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def main() -> None:
    from spina_app import client_application
    from spina_app.features.clients import install_clients_feature
    from spina_app.utilities import formatting

    class FakeApp:
        pass

    class FakeLoanDB:
        def renew_client(self, *args, **kwargs):
            return "legacy-renew"

    def no_op(*args, **kwargs):
        return None

    namespace = {
        "App": FakeApp,
        "LoanDB": FakeLoanDB,
        "SPINA_POSTGRESQL_TEST_MODE": False,
        "_log_exc": no_op,
        "_log_suppressed_once": no_op,
        "_log_ignored": no_op,
        "_spina_v22_reports_colors": lambda *_args, **_kwargs: {
            "bg": "#fff",
            "panel": "#fff",
            "card": "#fff",
            "card2": "#fff",
            "border": "#ddd",
            "fg": "#111",
            "muted": "#666",
            "blue": "#00f",
            "green": "#080",
            "red": "#f00",
            "soft": "#eee",
            "purple": "#808",
            "orange": "#f80",
        },
        "_spina_perf_dict_rows": lambda rows: list(rows or []),
        "_spina_perf_ensure_indexes": no_op,
        "_spina_perf_norm_lt": lambda value: "7x7" if "7" in str(value) else "Regular",
        "_spina__fmt_client_money": lambda value: str(value),
        "_spina_route_notice_key": lambda *args: "key",
        "_spina_route_notice_load": lambda: {},
        "_spina_route_notice_norm_lt": lambda value: str(value or "Regular"),
        "_spina_route_notice_norm_name": lambda value: str(value or "").lower(),
        "_spina__parse_day_ymd": _parse_day,
        "_spina__norm_weekday": lambda value: str(value or "")[:3].title(),
        "_spina__norm_dom": lambda value: int(value) if str(value or "").isdigit() else None,
    }

    assert "_spina_v23_money" not in namespace
    assert "_spina_v23_percent" not in namespace
    assert install_clients_feature(FakeApp, loan_db_cls=FakeLoanDB, namespace=namespace)

    assert namespace["_spina_v23_money"] is formatting._spina_v23_money
    assert namespace["_spina_v23_percent"] is formatting._spina_v23_percent
    assert client_application._spina_v23_money is formatting._spina_v23_money
    assert client_application._spina_v23_percent is formatting._spina_v23_percent
    assert client_application._spina_v23_money(1234.5) == "PHP 1,234.50"
    assert client_application._spina_v23_percent(42.4) == "42%"

    print("Clients application-form formatter binding regression passed")


if __name__ == "__main__":
    main()

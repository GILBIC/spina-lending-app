#!/usr/bin/env python3
"""Repository and pure-service regressions for Reports Wave 80."""
from __future__ import annotations

from spina_app.repositories.reports import (
    fetch_client_info,
    fetch_client_link_meta,
    fetch_client_type_presence,
    fetch_report_clients,
)
from spina_app.services.reports import (
    build_report_row,
    build_report_summary,
    display_loan_type,
    linked_label,
)


class FakeDb:
    def get_all_clients(self, **kwargs):
        assert kwargs["loan_type"] == "Regular"
        assert kwargs["include_archived"] is True
        return ["Ana"]

    def get_client_info(self, name, loan_type=None):
        if name != "Ana":
            return None
        if loan_type == "Regular":
            return {"name": name, "loan_type": "Regular", "principal": 5000}
        if loan_type == "7x7":
            return {"name": name, "loan_type": "Emergency", "principal": 3000}
        return {"name": name, "loan_type": "Regular"}

    def get_client_link_meta(self, name, loan_type=None):
        return {"client_uid": "c-1", "person_uid": "p-1"}


class FakeApp:
    db = FakeDb()


def main() -> None:
    app = FakeApp()
    assert fetch_report_clients(
        app,
        search="an",
        loan_type="Regular",
        include_archived=True,
    ) == ["Ana"]
    assert fetch_client_info(app, "Ana", "Regular")["principal"] == 5000
    assert fetch_client_link_meta(app, "Ana", "Regular")["person_uid"] == "p-1"
    assert fetch_client_type_presence(app, "Ana") == (True, True)

    assert display_loan_type("Emergency") == "7x7 (Emer)"
    assert display_loan_type("7x7emer") == "7x7 (Emer)"
    assert display_loan_type("reg") == "Regular"
    assert linked_label("Regular", True, True) == "7x7"
    assert linked_label("7x7", True, True) == "Regular"
    assert linked_label("All", True, True) == "Regular + 7x7 (Emer)"

    row = build_report_row(
        "Ana",
        {
            "loan_type": "Emergency",
            "payment_term": "Daily",
            "payment_amount": 42,
            "payment_mode": "Cash",
            "principal": 3000,
            "total_to_pay": 3000,
        },
        active_filter="7x7",
        has_regular=True,
        has_7x7=True,
        due_label="Daily",
        format_money=lambda value: f"{float(value):.2f}",
    )
    assert row[0] == "Ana"
    assert row[2] == "7x7 (Emer)"
    assert row[4] == "Daily"
    assert row[7] == "Regular"
    assert row[9] == "3000.00"

    assert build_report_summary(
        1,
        active_filter="Regular",
        start_date="2026-07-01",
        end_date="2026-07-31",
    ) == "1 client  •  View: Regular  •  Generate: 2026-07-01 to 2026-07-31"
    assert "2 clients" in build_report_summary(2, active_filter="All")
    print("Wave 80 Reports repository/service tests passed.")


if __name__ == "__main__":
    main()

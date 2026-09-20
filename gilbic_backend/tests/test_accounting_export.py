"""Review exports preserve exact books and reject incomplete or unsafe output."""

import csv
import hashlib
import io
import json
import zipfile
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from gilbic_backend import accounting_export as export

START = date(2026, 9, 1)
END = date(2026, 9, 30)
ACTOR = UUID("00000000-0000-4000-8000-000000000001")


def sample_snapshot():
    accounts = []
    journals = []
    for index, code in enumerate(("1010", "3000")):
        accounts.append(
            {
                "account_id": ACTOR,
                "account_code": code,
                "system_key": f"account_{code}",
                "account_name": "José <script>alert(1)</script>",
                "account_type": "asset" if index == 0 else "equity",
                "normal_balance": "debit" if index == 0 else "credit",
                "is_active": False,
                "is_posting": True,
                "opening_debit": Decimal("1.01") if index == 0 else Decimal(0),
                "opening_credit": Decimal("1.01") if index == 1 else Decimal(0),
                "movement_debit": Decimal("0.29") if index == 0 else Decimal(0),
                "movement_credit": Decimal("0.29") if index == 1 else Decimal(0),
            }
        )
        journals.append(
            {
                "entry_id": ACTOR,
                "entry_number": "JE-1",
                "period_id": ACTOR,
                "posting_date": START,
                "entry_description": ' =HYPERLINK("bad")',
                "source_type": "manual",
                "source_reference": None,
                "source_event_key": None,
                "reversal_of_entry_id": None,
                "created_by_user_id": ACTOR,
                "posted_by_user_id": ACTOR,
                "created_at": datetime(2026, 9, 1, tzinfo=timezone.utc),
                "posted_at": datetime(2026, 9, 1, tzinfo=timezone.utc),
                "line_number": index + 1,
                "account_code": code,
                "account_name": accounts[-1]["account_name"],
                "line_description": "@formula\nunsafe\x00",
                "debit": accounts[-1]["movement_debit"],
                "credit": accounts[-1]["movement_credit"],
                "client_id": None,
                "loan_id": None,
            }
        )
    return {
        "generated_at": datetime(2026, 9, 20, tzinfo=timezone.utc),
        "accounts": accounts,
        "journals": journals,
        "periods": [],
        "audit": [],
        "cancelled": [],
    }


def build(snapshot=None):
    return export.build_accounting_export(
        snapshot or sample_snapshot(),
        start_date=START,
        end_date=END,
        generated_by_user_id=ACTOR,
    )


def unpack(content):
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def test_exact_money_complete_inventory_hashes_and_determinism():
    content = build()
    assert content == build()
    files = unpack(content)
    assert set(files) == {
        "manifest.json",
        "README.md",
        "general-journal.csv",
        "general-ledger.csv",
        "trial-balance.csv",
        "chart-of-accounts.csv",
        "accounting-audit.csv",
        "cancelled-drafts.json",
        "print-view.html",
    }
    manifest = json.loads(files["manifest.json"])
    assert manifest["kind"] == "spina_accounting_export"
    assert manifest["review_only"] is True
    assert (
        manifest["official_books_registered"]
        is manifest["saf_compliance_verified"]
        is manifest["taxpayer_identity_verified"]
        is False
    )
    assert manifest["totals"] == {
        "opening_debit": "1.01",
        "opening_credit": "1.01",
        "movement_debit": "0.29",
        "movement_credit": "0.29",
        "closing_debit": "1.30",
        "closing_credit": "1.30",
    }
    assert set(manifest["files"]) == set(files) - {"manifest.json"}
    assert manifest["files"]["README.md"]["rows"] is None
    assert manifest["files"]["print-view.html"]["rows"] is None
    for name, metadata in manifest["files"].items():
        assert metadata["sha256"] == hashlib.sha256(files[name]).hexdigest()
        assert metadata["bytes"] == len(files[name])


def test_text_formula_controls_unicode_and_html_are_safe():
    files = unpack(build())
    rows = list(csv.DictReader(io.StringIO(files["general-journal.csv"].decode())))
    assert rows[0]["entry_description"].startswith("' =")
    assert rows[0]["line_description"] == "'@formula\\u000aunsafe\\u0000"
    assert rows[0]["debit"] == "0.29"
    assert "José" in files["print-view.html"].decode()
    assert b"<script>" not in files["print-view.html"]
    assert b"&lt;script&gt;" in files["print-view.html"]
    assert b"Content-Security-Policy" in files["print-view.html"]


@pytest.mark.parametrize("value", ["=2+2", "+1", "-1", "@bad", "  =2+2"])
def test_csv_text_prefixes_are_not_formulas(value):
    assert export.csv_cell(value).startswith("'")


def test_numeric_money_is_not_text_escaped():
    assert export.csv_cell(Decimal("-1.20")) == "-1.20"
    assert export.csv_cell("\t=1") == "\\u0009=1"


@pytest.mark.parametrize(
    "start,end", [(END, START), (date(2026, 1, 1), date(2027, 1, 2))]
)
def test_invalid_date_scope(start, end):
    with pytest.raises(export.AccountingExportError, match="366"):
        export.validate_range(start, end)


def test_366_day_and_single_day_ranges_are_valid():
    export.validate_range(START, START)
    export.validate_range(date(2024, 1, 1), date(2024, 12, 31))


@pytest.mark.parametrize(
    "change",
    [
        "journal",
        "movement",
        "opening",
        "unknown_account",
        "float",
        "fractional_cent",
        "duplicate_account",
    ],
)
def test_nonreconciling_or_inexact_ledger_is_rejected(change):
    snapshot = sample_snapshot()
    if change == "journal":
        snapshot["journals"][0]["debit"] += Decimal("0.01")
    elif change == "movement":
        snapshot["accounts"][0]["movement_debit"] += Decimal("0.01")
    elif change == "opening":
        snapshot["accounts"][0]["opening_debit"] += Decimal("0.01")
    elif change == "unknown_account":
        snapshot["journals"][0]["account_code"] = "missing"
    elif change == "float":
        snapshot["journals"][0]["debit"] = 0.29
    elif change == "fractional_cent":
        snapshot["journals"][0]["debit"] = Decimal("0.291")
    else:
        snapshot["accounts"].append(deepcopy(snapshot["accounts"][0]))
    with pytest.raises(export.AccountingExportError) as error:
        build(snapshot)
    assert error.value.code == "integrity"


def test_retired_accounts_and_audit_snapshots_remain_visible():
    snapshot = sample_snapshot()
    snapshot["cancelled"] = [
        {
            "original_journal_entry_id": str(ACTOR),
            "lines": [{"debit": "3.00"}],
            "prior_events": [{"event_type": "draft_created"}],
        }
    ]
    files = unpack(build(snapshot))
    rows = list(csv.DictReader(io.StringIO(files["chart-of-accounts.csv"].decode())))
    assert rows[0]["is_active"] == "false"
    assert (
        json.loads(files["cancelled-drafts.json"])[0]["prior_events"][0]["event_type"]
        == "draft_created"
    )


def test_rows_are_rejected_instead_of_truncated(monkeypatch):
    monkeypatch.setattr(export, "MAX_ROWS", 1)
    with pytest.raises(export.AccountingExportError) as error:
        build()
    assert error.value.code == "oversized"


def test_content_limit_is_on_uncompressed_full_package(monkeypatch):
    monkeypatch.setattr(export, "MAX_BYTES", 1000)
    with pytest.raises(export.AccountingExportError) as error:
        build()
    assert error.value.code == "oversized"

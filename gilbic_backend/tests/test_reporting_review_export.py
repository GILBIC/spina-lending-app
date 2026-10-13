"""An annual handoff preserves supplied reporting evidence without inventing it."""

import json
from copy import deepcopy

import pytest
from test_accounting_export import ACTOR, END, START, sample_snapshot, unpack

from gilbic_backend import accounting_export as export


def review_snapshot():
    snapshot = sample_snapshot()
    snapshot["reporting_review"] = {
        "schema_version": 1,
        "scope": "accountant_review",
        "start_date": START.isoformat(),
        "end_date": END.isoformat(),
        "book": {"status": "unconfigured"},
        "period_statements": [
            {
                "period": {
                    "period_id": str(ACTOR),
                    "label": "First reporting period",
                    "start_date": START.isoformat(),
                    "end_date": END.isoformat(),
                    "status": "open",
                },
                "profit_or_loss": {"net_income": "0.00"},
                "financial_position": {"total_assets": "1.30", "balanced": True},
                "reporting_supplement": {
                    "comparative": None,
                    "notes": {"status": "reporting_policy_required", "items": []},
                    "cash_flows": {
                        "status": "cash_definition_required",
                        "net_cash_flow": None,
                    },
                    "changes_in_equity": {"reconciled": True},
                    "journal_disclosures": {
                        "status": "disclosure_policy_required",
                        "coverage": {"blocked_count": 1},
                    },
                },
            }
        ],
        "annual_consolidation": "accountant_review_required",
        "statutory_acceptance": False,
    }
    return snapshot


def build(snapshot):
    return unpack(
        export.build_accounting_export(
            snapshot, start_date=START, end_date=END, generated_by_user_id=ACTOR
        )
    )


def test_first_book_reporting_handoff_keeps_unknown_cash_and_no_comparative():
    files = build(review_snapshot())
    assert "reporting/statement-packs.json" in files
    pack = json.loads(files["reporting/statement-packs.json"])
    assert pack["period_statements"][0]["reporting_supplement"]["comparative"] is None
    assert (
        pack["period_statements"][0]["reporting_supplement"]["cash_flows"][
            "net_cash_flow"
        ]
        is None
    )
    assert pack["statutory_acceptance"] is False
    manifest = json.loads(files["manifest.json"])
    assert manifest["reporting_package"]["scope"] == "accountant_review"
    assert (
        manifest["reporting_package"]["annual_consolidation"]
        == "accountant_review_required"
    )
    assert "reporting/statement-packs.json" in manifest["files"]
    assert (
        "No preceding configured period" in files["reporting/statements.html"].decode()
    )


def test_reporting_print_copy_escapes_supplied_notes():
    snapshot = review_snapshot()
    snapshot["reporting_review"]["period_statements"][0]["reporting_supplement"][
        "notes"
    ]["items"] = [
        {
            "title": "<script>private</script>",
            "text": "Actual supplied note & basis",
            "evidence_reference": "evidence-1",
            "evidence_digest": "a" * 64,
        }
    ]
    output = build(snapshot)["reporting/statements.html"].decode()
    assert "<script>" not in output
    assert "&lt;script&gt;" in output
    assert "Actual supplied note &amp; basis" in output


def test_each_printable_statement_section_identifies_the_book():
    snapshot = review_snapshot()
    report = snapshot["reporting_review"]
    report["book"] = {
        "status": "configured",
        "book_id": "00000000-0000-4000-8000-000000000002",
        "kind": "synthetic",
        "entity_label": "Synthetic <Lending> & Co",
    }
    period = report["period_statements"][0]
    report["range_statements"] = deepcopy(period)
    report["range_statements"]["period"]["label"] = "Selected reporting range"
    period["reporting_supplement"]["comparative"] = deepcopy(period)
    output = build(snapshot)["reporting/statements.html"].decode()
    sections = output.split("<section>")[1:]
    assert len(sections) == 3
    for section in sections:
        assert "Synthetic &lt;Lending&gt; &amp; Co" in section
        assert report["book"]["book_id"] in section
        assert "Book status</dt><dd>configured" in section
        assert "Book type</dt><dd>synthetic" in section


def test_printable_unconfigured_book_is_explicit():
    output = build(review_snapshot())["reporting/statements.html"].decode()
    assert "Book status</dt><dd>unconfigured" in output
    assert "Book</dt><dd>Unavailable" in output


@pytest.mark.parametrize("change", ["gap", "overlap", "wrong_range", "duplicate"])
def test_reporting_package_refuses_incomplete_or_ambiguous_period_scope(change):
    snapshot = review_snapshot()
    report = snapshot["reporting_review"]
    period = report["period_statements"][0]["period"]
    if change == "gap":
        period["start_date"] = "2026-09-02"
    elif change == "overlap":
        report["period_statements"].append(deepcopy(report["period_statements"][0]))
        report["period_statements"][1]["period"]["period_id"] = (
            "00000000-0000-4000-8000-000000000002"
        )
    elif change == "duplicate":
        report["period_statements"].append(deepcopy(report["period_statements"][0]))
    else:
        report["end_date"] = "2026-09-29"
    with pytest.raises(export.AccountingExportError, match="period|range"):
        build(snapshot)

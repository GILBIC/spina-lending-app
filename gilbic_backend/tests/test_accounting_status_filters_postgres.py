"""Exercise every queue filter with psycopg and hand-checked status examples."""

import importlib
import os

import psycopg
import pytest

DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="Disposable PostgreSQL required"
)

# The selected values are business statuses, independently specified here so a
# broken SQL predicate cannot manufacture its own expected result.
FILTERS = {
    "v1_tax_liability": (
        "accounting_status",
        {
            "ready": ("evidence_ready",),
            "prepared": ("prepared_not_posted",),
            "posted": ("posted",),
            "adjustment_review": ("posted_adjustment_review_required",),
            "adjusted": ("posted_adjusted_reversed", "posted_adjusted_recoverable"),
            "covered": ("covered_by_settled_adjustment",),
            "blocked": (
                "blocked_evidence",
                "posted_adjustment_review_required",
                "unknown_status",
            ),
        },
        ("no_liability_required",),
    ),
    "v1_tax_settlement": (
        "settlement_status",
        {
            "awaiting_payment": ("return_recorded_awaiting_payment",),
            "ready": ("payment_evidence_ready",),
            "prepared": ("settlement_prepared",),
            "settled": ("settled",),
            "adjustment_review": ("settled_adjustment_review_required",),
            "adjustment_in_progress": ("settled_adjustment_in_progress",),
            "adjusted": ("settled_adjustment_recorded",),
            "blocked": ("blocked_evidence", "prepared_blocked_evidence"),
        },
        ("unknown_status",),
    ),
    "v1_tax_adjustment": (
        "adjustment_status",
        {
            "ready": ("evidence_ready",),
            "prepared": ("prepared_not_posted",),
            "posted": (
                "posted_unsettled_liability_reversal",
                "posted_settled_tax_recoverable",
            ),
            "review": ("posted_further_adjustment_review_required",),
            "blocked": ("blocked_evidence",),
        },
        ("unknown_status",),
    ),
    "v1_tax_additional_amendment": (
        "amendment_status",
        {
            "ready": ("amendment_evidence_ready",),
            "liability_prepared": ("additional_liability_prepared",),
            "awaiting_payment": ("additional_liability_posted_awaiting_payment",),
            "payment_ready": ("additional_payment_evidence_ready",),
            "settlement_prepared": ("additional_settlement_prepared",),
            "settled": ("additional_tax_settled",),
            "review": ("further_review_required", "blocked_review_required"),
            "blocked": ("blocked_evidence", "blocked_review_required"),
        },
        ("unknown_status",),
    ),
    "v1_tax_recoverable_refund": (
        "refund_status",
        {
            "ready": ("refund_evidence_ready",),
            "prepared": ("refund_prepared",),
            "realized": ("refund_realized",),
            "blocked": ("blocked_evidence",),
        },
        ("unknown_status",),
    ),
    "v1_tax_recoverable_credit": (
        "credit_status",
        {
            "ready": ("credit_evidence_ready",),
            "prepared": ("credit_prepared",),
            "applied": ("credit_applied",),
            "blocked": ("blocked_evidence",),
        },
        ("unknown_status",),
    ),
    "period_close": (
        "close_status",
        {
            "ready_for_review": ("ready_for_review",),
            "ready_to_prepare": ("ready_to_prepare",),
            "prepared": ("prepared_confirmation_required",),
            "closed": ("closed_protected", "blocked_closed_source_review_required"),
            "blocked": (
                "blocked_evidence",
                "blocked_closed_source_review_required",
                "closed_legacy_without_protected_close_audit",
            ),
        },
        ("unknown_status",),
    ),
}


def _repository(name):
    module = importlib.import_module(f"gilbic_backend.{name}_repository")
    repository_type = next(
        getattr(module, attribute)
        for attribute in dir(module)
        if attribute.startswith("Postgres") and attribute.endswith("Repository")
    )
    return repository_type()


@pytest.mark.parametrize(
    "name,status",
    [
        (name, status)
        for name, (_, filters, _) in FILTERS.items()
        for status in ("all", *filters)
    ],
)
def test_queue_filter_executes_and_selects_only_matching_statuses(name, status):
    repository = _repository(name)
    # Exercise the actual list query: the original failure occurs when LIKE's
    # literal percent is parsed beside the LIMIT/OFFSET bind placeholders.
    assert isinstance(repository.list_items(status=status, limit=1, offset=0), tuple)

    column, expected_by_filter, other_values = FILTERS[name]
    values = sorted(set(other_values).union(*expected_by_filter.values()))
    expected = values if status == "all" else sorted(expected_by_filter[status])
    clause, parameters = repository._status_where(status)
    with psycopg.connect(DATABASE_URL) as connection:
        actual = connection.execute(
            f"SELECT {column} FROM unnest(%s::text[]) AS cases({column}) WHERE {clause} ORDER BY {column}",
            (values, *parameters),
        ).fetchall()
    assert [row[0] for row in actual] == expected


@pytest.mark.parametrize("name", FILTERS)
def test_queue_rejects_unsupported_status_filters(name):
    with pytest.raises(ValueError, match="Unsupported"):
        _repository(name).list_items(status="unknown_filter")

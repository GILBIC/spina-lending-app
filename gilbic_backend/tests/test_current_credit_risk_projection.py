"""The public current-risk context never returns private evidence snapshots."""

from gilbic_backend.current_credit_risk_review_repository import public_context


def test_current_risk_projection_keeps_only_reviewable_identity_and_labels():
    source = {
        "book_id": "book",
        "period_id": "period",
        "loan_id": "loan",
        "ready": True,
        "blockers": [],
        "as_of_date": "2026-10-10",
        "source_digest": "a" * 64,
        "schedule_id": "schedule",
        "schedule_version": 2,
        "days_past_due": 0,
        "due_unpaid_amount": "900.05",
        "thirty_day_sicr_backstop_reached": False,
        "ninety_day_default_backstop_reached": False,
        "snapshot": {
            "loan": {"private_phone": "sensitive"},
            "collections": [{"receipt": "private"}],
        },
        "private_document": "private/source/key",
        "prior_review": {
            "id": 31,
            "review_version": 2,
            "stage_label": "stage_2_lifetime",
            "default_label": False,
            "write_off_label": "none",
            "recovery_label": "none",
            "reviewed_at": "2026-10-10T01:00:00Z",
            "evidence_reference": "private-evidence",
            "review_note": "private note",
            "reviewer_user_id": "private-actor",
        },
        "inherited_review": {
            "id": 29,
            "review_version": 1,
            "loan_id": "old-loan",
            "stage_label": "stage_3_credit_impaired",
            "default_label": False,
            "write_off_label": "none",
            "recovery_label": "none",
            "reviewed_at": "2026-10-09T01:00:00Z",
            "evidence_reference": "private-inherited-evidence",
            "lineage": {"private_document": "private/source/key"},
        },
    }
    public = public_context(source)
    assert set(public) == {
        "book_id",
        "period_id",
        "loan_id",
        "ready",
        "blockers",
        "as_of_date",
        "source_digest",
        "schedule_id",
        "schedule_version",
        "days_past_due",
        "due_unpaid_amount",
        "thirty_day_sicr_backstop_reached",
        "ninety_day_default_backstop_reached",
        "prior_review",
        "inherited_review",
    }
    assert public["due_unpaid_amount"] == "900.05"
    assert set(public["prior_review"]) == {
        "id",
        "review_version",
        "stage_label",
        "default_label",
        "write_off_label",
        "recovery_label",
        "reviewed_at",
    }
    assert public["inherited_review"] == {
        "id": 29,
        "review_version": 1,
        "loan_id": "old-loan",
        "stage_label": "stage_3_credit_impaired",
        "default_label": False,
        "write_off_label": "none",
        "recovery_label": "none",
        "reviewed_at": "2026-10-09T01:00:00Z",
    }
    assert "private" not in str(public)


def test_current_risk_without_inherited_history_keeps_it_absent():
    public = public_context({"due_unpaid_amount": "0.00"})
    assert public["prior_review"] is None
    assert public["inherited_review"] is None

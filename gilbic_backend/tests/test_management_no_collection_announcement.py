from __future__ import annotations

from datetime import date, datetime, timezone
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from gilbic_backend.management_no_collection_announcement import (
    NoCollectionAnnouncementDateError,
    philippines_business_date,
    validate_no_collection_announcement_date,
)
from gilbic_backend.management_no_collection_api import (
    NoCollectionDeclarationBody,
    NoCollectionPreviewBody,
)
from gilbic_backend.management_no_collection_preview import preview_no_collection_shift
from gilbic_backend.management_no_collection_query_repository import NoCollectionLoanState
from gilbic_backend.management_no_collection_repository import ManagementNoCollectionInvalid


LOAN_ID = UUID("10000000-0000-4000-8000-000000000001")


def test_no_collection_announcement_rejects_today_and_past_but_accepts_future() -> None:
    business_date = date(2026, 8, 27)

    for blocked_date in (date(2026, 8, 26), business_date):
        with pytest.raises(
            NoCollectionAnnouncementDateError,
            match="only be announced for a future date",
        ):
            validate_no_collection_announcement_date(
                no_collection_date=blocked_date,
                business_date=business_date,
            )

    validate_no_collection_announcement_date(
        no_collection_date=date(2026, 8, 28),
        business_date=business_date,
    )


def test_philippines_business_date_uses_utc_plus_eight_boundary() -> None:
    assert philippines_business_date(
        now=datetime(2026, 8, 26, 16, 30, tzinfo=timezone.utc)
    ) == date(2026, 8, 27)


def test_preview_planner_rejects_non_future_announcement_before_schedule_work() -> None:
    unusable_state = cast(NoCollectionLoanState, object())

    with pytest.raises(
        ManagementNoCollectionInvalid,
        match="only be announced for a future date",
    ):
        preview_no_collection_shift(
            state=unusable_state,
            no_collection_date=date(2026, 8, 27),
            business_date=date(2026, 8, 27),
        )


def test_management_api_bodies_reject_past_no_collection_dates() -> None:
    with pytest.raises(ValidationError, match="only be announced for a future date"):
        NoCollectionPreviewBody(
            loan_id=LOAN_ID,
            expected_operational_version=0,
            no_collection_date=date(2000, 1, 1),
        )

    with pytest.raises(ValidationError, match="only be announced for a future date"):
        NoCollectionDeclarationBody(
            no_collection_date=date(2000, 1, 1),
            reason="Management announcement",
            loans=[
                {
                    "loan_id": LOAN_ID,
                    "expected_operational_version": 0,
                }
            ],
        )


def test_management_api_bodies_accept_future_no_collection_dates() -> None:
    future_date = date(2099, 1, 1)

    preview = NoCollectionPreviewBody(
        loan_id=LOAN_ID,
        expected_operational_version=0,
        no_collection_date=future_date,
    )
    declaration = NoCollectionDeclarationBody(
        no_collection_date=future_date,
        reason="Management announcement",
        loans=[
            {
                "loan_id": LOAN_ID,
                "expected_operational_version": 0,
            }
        ],
    )

    assert preview.no_collection_date == future_date
    assert declaration.no_collection_date == future_date

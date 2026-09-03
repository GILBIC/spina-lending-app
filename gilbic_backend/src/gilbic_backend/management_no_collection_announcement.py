from __future__ import annotations

from datetime import date, datetime, timedelta, timezone


PHILIPPINES_TIMEZONE = timezone(timedelta(hours=8))


class NoCollectionAnnouncementDateError(ValueError):
    """Raised when a normal No Collection announcement does not target the future."""


def philippines_business_date(*, now: datetime | None = None) -> date:
    """Return the current Philippines business date without relying on server local time."""

    current = now or datetime.now(PHILIPPINES_TIMEZONE)
    if current.tzinfo is None:
        current = current.replace(tzinfo=PHILIPPINES_TIMEZONE)
    else:
        current = current.astimezone(PHILIPPINES_TIMEZONE)
    return current.date()


def validate_no_collection_announcement_date(
    *,
    no_collection_date: date,
    business_date: date | None = None,
) -> None:
    """Require a normal Management No Collection announcement to target a future date."""

    current_business_date = business_date or philippines_business_date()
    if no_collection_date <= current_business_date:
        raise NoCollectionAnnouncementDateError(
            "No Collection can only be announced for a future date."
        )

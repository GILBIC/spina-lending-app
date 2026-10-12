"""Require the result of an accounting query that promises exactly one row."""

from typing import TypeVar

Row = TypeVar("Row")


def require_row(row: Row | None) -> Row:
    if row is None:
        raise RuntimeError("The required accounting query result is unavailable.")
    return row

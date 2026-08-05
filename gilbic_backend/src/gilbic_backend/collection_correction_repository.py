from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .database import open_connection


MONEY = Decimal("0.01")


class CollectionCorrectionError(RuntimeError):
    code = "collection_correction_error"


class CollectionCorrectionNotFound(CollectionCorrectionError):
    code = "collection_correction_not_found"


class CollectionCorrectionForbidden(CollectionCorrectionError):
    code = "collection_correction_forbidden"


class CollectionCorrectionLocked(CollectionCorrectionError):
    code = "collection_correction_locked"


class CollectionCorrectionConflict(CollectionCorrectionError):
    code = "collection_correction_conflict"


class CollectionCorrectionInvalid(CollectionCorrectionError):
    code = "collection_correction_invalid"


@dataclass(frozen=True, slots=True)
class CollectionCorrectionRecord:
    transaction_id: UUID
    client_id: UUID
    loan_id: UUID
    collection_date: date
    entry_type: str
    amount: Decimal
    covered_dates: tuple[date, ...]
    note: str
    official_balance: Decimal
    pass_count_after: int
    receipt_number: str
    edit_version: int
    route_revision: str
    edited_at: datetime


class PostgresCollectionCorrectionRepository:
    def correct_own_unremitted(
        self,
        *,
        actor_user_id: UUID,
        transaction_id: UUID,
        entry_type: str,
        amount: Decimal | None,
        covered_dates: tuple[date, ...],
        note: str,
        reason: str,
    ) -> CollectionCorrectionRecord:
        normalized_type = entry_type.strip().lower()
        if normalized_type not in {"payment", "advance", "pass"}:
            raise CollectionCorrectionInvalid("Choose a valid collection entry type.")
        if not reason.strip():
            raise CollectionCorrectionInvalid("Enter a reason for the correction.")

        with open_connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                        (f"gilbic-collection-correction:{transaction_id}",),
                    )
                    cursor.execute(
                        """
                        select
                            t.*,
                            l.status as loan_status,
                            lt.settings as loan_type_settings,
                            s.remaining_balance as state_remaining_balance,
                            s.pass_count as state_pass_count,
                            s.last_payment_date as state_last_payment_date,
                            s.advance_until as state_advance_until,
                            s.note as state_note,
                            s.state_version
                        from lending.collection_transactions t
                        join lending.loans l on l.id = t.loan_id
                        join lending.loan_types lt on lt.id = l.loan_type_id
                        join lending.loan_collection_state s on s.loan_id = t.loan_id
                        where t.id = %s
                        for update of t, l, s
                        """,
                        (transaction_id,),
                    )
                    transaction = cursor.fetchone()
                    if not transaction:
                        raise CollectionCorrectionNotFound(
                            "The collection entry was not found."
                        )
                    if transaction["collector_user_id"] != actor_user_id:
                        raise CollectionCorrectionForbidden(
                            "Only the collector who recorded this entry may correct it."
                        )
                    if transaction["is_locked"] or transaction["remittance_id"] is not None:
                        raise CollectionCorrectionLocked(
                            "This entry is already included in a remittance and cannot be edited."
                        )

                    details = (
                        dict(transaction["details"])
                        if isinstance(transaction["details"], dict)
                        else {}
                    )
                    expected_state_version = details.get("state_version_after")
                    if expected_state_version is None or int(expected_state_version) != int(
                        transaction["state_version"]
                    ):
                        raise CollectionCorrectionConflict(
                            "The loan changed after this entry. Refresh before correcting it."
                        )

                    selected_dates = tuple(sorted(set(covered_dates)))
                    self._validate_replacement(
                        entry_type=normalized_type,
                        amount=amount,
                        collection_date=transaction["collection_date"],
                        covered_dates=selected_dates,
                    )
                    self._verify_dates_available(
                        cursor,
                        transaction_id=transaction_id,
                        loan_id=transaction["loan_id"],
                        covered_dates=selected_dates,
                    )

                    cursor.execute(
                        """
                        select
                            coalesce((
                                select previous.pass_count_after
                                from lending.collection_transactions previous
                                where previous.loan_id = %s
                                  and (previous.accepted_at, previous.id) < (%s, %s)
                                order by previous.accepted_at desc, previous.id desc
                                limit 1
                            ), 0) as pass_count_before,
                            (
                                select previous.advance_until_after
                                from lending.collection_transactions previous
                                where previous.loan_id = %s
                                  and (previous.accepted_at, previous.id) < (%s, %s)
                                order by previous.accepted_at desc, previous.id desc
                                limit 1
                            ) as advance_until_before,
                            (
                                select max(previous.collection_date)
                                from lending.collection_transactions previous
                                where previous.loan_id = %s
                                  and (previous.accepted_at, previous.id) < (%s, %s)
                                  and previous.entry_type <> 'pass'
                            ) as last_payment_date_before
                        """,
                        (
                            transaction["loan_id"],
                            transaction["accepted_at"],
                            transaction_id,
                            transaction["loan_id"],
                            transaction["accepted_at"],
                            transaction_id,
                            transaction["loan_id"],
                            transaction["accepted_at"],
                            transaction_id,
                        ),
                    )
                    before_state = cursor.fetchone()
                    cursor.execute(
                        """
                        select covered_date
                        from lending.collection_covered_dates
                        where transaction_id = %s
                        order by covered_date
                        """,
                        (transaction_id,),
                    )
                    previous_covered_dates = tuple(
                        row["covered_date"] for row in cursor.fetchall()
                    )

                    previous_balance = self._money(transaction["previous_balance"])
                    corrected_amount = self._money(amount or Decimal("0"))
                    if normalized_type == "pass":
                        corrected_amount = Decimal("0.00")
                        official_balance = previous_balance
                        pass_count_after = int(before_state["pass_count_before"]) + 1
                        last_payment_date_after = before_state[
                            "last_payment_date_before"
                        ]
                        advance_from = None
                        advance_until = None
                    else:
                        if corrected_amount > previous_balance:
                            raise CollectionCorrectionInvalid(
                                "The corrected amount is higher than the balance before this entry."
                            )
                        official_balance = self._money(previous_balance - corrected_amount)
                        pass_count_after = 0
                        last_payment_date_after = transaction["collection_date"]
                        advance_from = (
                            selected_dates[0] if normalized_type == "advance" else None
                        )
                        advance_until = (
                            selected_dates[-1] if normalized_type == "advance" else None
                        )

                    previous_snapshot = self._snapshot(
                        transaction,
                        covered_dates=previous_covered_dates,
                    )
                    cursor.execute(
                        "delete from lending.collection_covered_dates where transaction_id = %s",
                        (transaction_id,),
                    )
                    for covered_date in selected_dates:
                        cursor.execute(
                            """
                            insert into lending.collection_covered_dates (
                                transaction_id, loan_id, covered_date
                            ) values (%s, %s, %s)
                            """,
                            (transaction_id, transaction["loan_id"], covered_date),
                        )
                    cursor.execute(
                        """
                        select max(covered_date) as latest_covered_date
                        from lending.collection_covered_dates
                        where loan_id = %s
                        """,
                        (transaction["loan_id"],),
                    )
                    advance_until_after = cursor.fetchone()["latest_covered_date"]

                    edited_at = datetime.now(timezone.utc)
                    edit_version = int(transaction["edit_version"]) + 1
                    next_state_version = int(transaction["state_version"]) + 1
                    route_revision = (
                        f"loan:{transaction['loan_id']}:v{next_state_version}"
                    )
                    replacement_details = dict(details)
                    replacement_details.update(
                        {
                            "state_version_after": next_state_version,
                            "last_correction_version": edit_version,
                            "last_corrected_at": edited_at.isoformat(),
                            "covered_dates": [
                                value.isoformat() for value in selected_dates
                            ],
                        }
                    )
                    replacement_snapshot = {
                        "transaction_id": str(transaction_id),
                        "entry_type": normalized_type,
                        "amount": str(corrected_amount),
                        "advance_from": (
                            advance_from.isoformat() if advance_from else None
                        ),
                        "advance_until": (
                            advance_until.isoformat() if advance_until else None
                        ),
                        "note": note.strip(),
                        "previous_balance": str(previous_balance),
                        "official_balance": str(official_balance),
                        "pass_count_after": pass_count_after,
                        "advance_until_after": (
                            advance_until_after.isoformat()
                            if advance_until_after
                            else None
                        ),
                        "covered_dates": [
                            value.isoformat() for value in selected_dates
                        ],
                        "receipt_number": str(transaction["receipt_number"]),
                    }

                    cursor.execute(
                        """
                        insert into lending.collection_transaction_edits (
                            id,
                            transaction_id,
                            edited_by_user_id,
                            edit_version,
                            reason,
                            previous_snapshot,
                            replacement_snapshot,
                            previous_covered_dates,
                            replacement_covered_dates,
                            edited_at
                        ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            uuid4(),
                            transaction_id,
                            actor_user_id,
                            edit_version,
                            reason.strip(),
                            Jsonb(previous_snapshot),
                            Jsonb(replacement_snapshot),
                            list(previous_covered_dates),
                            list(selected_dates),
                            edited_at,
                        ),
                    )
                    cursor.execute(
                        """
                        update lending.collection_transactions
                        set entry_type = %s,
                            amount = %s,
                            advance_from = %s,
                            advance_until = %s,
                            note = %s,
                            official_balance = %s,
                            pass_count_after = %s,
                            advance_until_after = %s,
                            details = %s,
                            edit_version = %s,
                            updated_at = %s,
                            updated_by_user_id = %s
                        where id = %s
                        """,
                        (
                            normalized_type,
                            corrected_amount,
                            advance_from,
                            advance_until,
                            note.strip(),
                            official_balance,
                            pass_count_after,
                            advance_until_after,
                            Jsonb(replacement_details),
                            edit_version,
                            edited_at,
                            actor_user_id,
                            transaction_id,
                        ),
                    )
                    cursor.execute(
                        """
                        update lending.loan_collection_state
                        set remaining_balance = %s,
                            pass_count = %s,
                            last_payment_date = %s,
                            advance_until = %s,
                            note = %s,
                            state_version = %s,
                            updated_at = %s
                        where loan_id = %s
                        """,
                        (
                            official_balance,
                            pass_count_after,
                            last_payment_date_after,
                            advance_until_after,
                            note.strip(),
                            next_state_version,
                            edited_at,
                            transaction["loan_id"],
                        ),
                    )
                    cursor.execute(
                        """
                        update lending.loans
                        set status = %s, updated_at = %s
                        where id = %s
                        """,
                        (
                            "paid" if official_balance == Decimal("0.00") else "active",
                            edited_at,
                            transaction["loan_id"],
                        ),
                    )
                    cursor.execute(
                        """
                        insert into core.audit_logs (
                            actor_user_id,
                            action,
                            target_type,
                            target_id,
                            details,
                            created_at
                        ) values (%s, 'collection.corrected.own_unremitted', 'collection_transaction', %s, %s, %s)
                        """,
                        (
                            actor_user_id,
                            transaction_id,
                            Jsonb(
                                {
                                    "reason": reason.strip(),
                                    "edit_version": edit_version,
                                    "previous": previous_snapshot,
                                    "replacement": replacement_snapshot,
                                }
                            ),
                            edited_at,
                        ),
                    )

        return CollectionCorrectionRecord(
            transaction_id=transaction_id,
            client_id=transaction["client_id"],
            loan_id=transaction["loan_id"],
            collection_date=transaction["collection_date"],
            entry_type=normalized_type,
            amount=corrected_amount,
            covered_dates=selected_dates,
            note=note.strip(),
            official_balance=official_balance,
            pass_count_after=pass_count_after,
            receipt_number=str(transaction["receipt_number"]),
            edit_version=edit_version,
            route_revision=route_revision,
            edited_at=edited_at,
        )

    @staticmethod
    def _money(value: Decimal | int | str) -> Decimal:
        return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)

    @staticmethod
    def _validate_replacement(
        *,
        entry_type: str,
        amount: Decimal | None,
        collection_date: date,
        covered_dates: tuple[date, ...],
    ) -> None:
        if entry_type == "pass":
            if amount not in {None, Decimal("0"), Decimal("0.00")}:
                raise CollectionCorrectionInvalid(
                    "An unable-to-pay entry cannot contain an amount."
                )
            if covered_dates:
                raise CollectionCorrectionInvalid(
                    "An unable-to-pay entry cannot contain covered dates."
                )
            return
        if amount is None or amount <= Decimal("0"):
            raise CollectionCorrectionInvalid(
                "Enter a corrected amount greater than zero."
            )
        if entry_type == "payment":
            if covered_dates != (collection_date,):
                raise CollectionCorrectionInvalid(
                    "A normal payment must cover only the collection date."
                )
            return
        if not covered_dates:
            raise CollectionCorrectionInvalid(
                "Choose at least one exact covered date."
            )

    @staticmethod
    def _verify_dates_available(
        cursor,
        *,
        transaction_id: UUID,
        loan_id: UUID,
        covered_dates: tuple[date, ...],
    ) -> None:
        if not covered_dates:
            return
        cursor.execute(
            """
            select covered_date
            from lending.collection_covered_dates
            where loan_id = %s
              and transaction_id <> %s
              and covered_date = any(%s)
            order by covered_date
            limit 1
            """,
            (loan_id, transaction_id, list(covered_dates)),
        )
        row = cursor.fetchone()
        if row:
            raise CollectionCorrectionConflict(
                f"{row['covered_date'].isoformat()} is already covered by another payment."
            )

    @staticmethod
    def _snapshot(
        transaction: dict[str, Any],
        *,
        covered_dates: tuple[date, ...],
    ) -> dict[str, object]:
        return {
            "transaction_id": str(transaction["id"]),
            "entry_type": str(transaction["entry_type"]),
            "amount": str(transaction["amount"]),
            "advance_from": (
                transaction["advance_from"].isoformat()
                if transaction["advance_from"]
                else None
            ),
            "advance_until": (
                transaction["advance_until"].isoformat()
                if transaction["advance_until"]
                else None
            ),
            "note": str(transaction["note"] or ""),
            "previous_balance": str(transaction["previous_balance"]),
            "official_balance": str(transaction["official_balance"]),
            "pass_count_after": int(transaction["pass_count_after"]),
            "advance_until_after": (
                transaction["advance_until_after"].isoformat()
                if transaction["advance_until_after"]
                else None
            ),
            "covered_dates": [value.isoformat() for value in covered_dates],
            "receipt_number": str(transaction["receipt_number"]),
            "edit_version": int(transaction["edit_version"]),
        }

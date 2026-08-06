from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row

from .database import open_connection


RenewalStatus = Literal["pending", "approved", "rejected", "cancelled"]
RenewalDecision = Literal["approved", "rejected"]


class RenewalError(RuntimeError):
    code = "renewal_error"


class RenewalBorrowerNotLinked(RenewalError):
    code = "renewal_borrower_not_linked"


class RenewalRequestNotFound(RenewalError):
    code = "renewal_request_not_found"


class RenewalConflict(RenewalError):
    code = "renewal_conflict"


class RenewalLoanNotEligible(RenewalError):
    code = "renewal_loan_not_eligible"


@dataclass(frozen=True, slots=True)
class RenewalLoanOption:
    loan_id: UUID
    loan_number: str
    loan_type_name: str
    calculation_mode: str
    principal: Decimal
    remaining_balance: Decimal
    daily_amount: Decimal
    date_released: date
    due_date: date
    status: str
    eligible: bool
    eligibility_message: str
    pending_request_id: UUID | None

    @property
    def paid_amount(self) -> Decimal:
        return max(Decimal("0"), self.principal - self.remaining_balance)

    @property
    def paid_percent(self) -> Decimal:
        if self.principal <= 0:
            return Decimal("0")
        return (self.paid_amount / self.principal * Decimal("100")).quantize(
            Decimal("0.1")
        )


@dataclass(frozen=True, slots=True)
class RenewalRequestRecord:
    request_id: UUID
    client_id: UUID
    client_code: str
    client_name: str
    loan_id: UUID
    loan_number: str
    loan_type_name: str
    current_principal: Decimal
    remaining_balance: Decimal
    requested_amount: Decimal
    client_message: str
    status: RenewalStatus
    submitted_at: datetime
    reviewed_at: datetime | None
    reviewed_by_name: str | None
    review_note: str
    cancelled_at: datetime | None


@dataclass(frozen=True, slots=True)
class ClientRenewalPortal:
    client_id: UUID
    client_code: str
    client_name: str
    loans: tuple[RenewalLoanOption, ...]
    requests: tuple[RenewalRequestRecord, ...]


class PostgresRenewalRepository:
    def portal_for_user(self, *, user_id: UUID) -> ClientRenewalPortal:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                client = self._linked_client(cursor, user_id=user_id)
                cursor.execute(
                    """
                    select
                        loan.id as loan_id,
                        loan.loan_number,
                        coalesce(nullif(btrim(loan_type.name), ''), 'Loan')
                            as loan_type_name,
                        loan_type.calculation_mode,
                        loan.principal,
                        coalesce(state.remaining_balance, loan.principal)
                            as remaining_balance,
                        loan.daily_amount,
                        loan.date_released,
                        loan.due_date,
                        loan.status,
                        pending.id as pending_request_id
                    from lending.loans loan
                    join lending.loan_types loan_type
                      on loan_type.id = loan.loan_type_id
                    left join lending.loan_collection_state state
                      on state.loan_id = loan.id
                    left join lateral (
                        select request.id
                        from lending.client_renewal_requests request
                        where request.client_id = loan.client_id
                          and request.loan_id = loan.id
                          and request.status = 'pending'
                        order by request.submitted_at desc
                        limit 1
                    ) pending on true
                    where loan.client_id = %s
                      and loan.status in ('active', 'paid')
                    order by
                        case when loan.status = 'active' then 0 else 1 end,
                        loan.date_released desc,
                        loan.id desc
                    """,
                    (client["id"],),
                )
                loans = tuple(self._loan_from_row(row) for row in cursor.fetchall())
                requests = self._list_requests(cursor, client_id=client["id"])

        return ClientRenewalPortal(
            client_id=client["id"],
            client_code=str(client["client_code"]),
            client_name=str(client["full_name"]),
            loans=loans,
            requests=requests,
        )

    def submit_for_user(
        self,
        *,
        user_id: UUID,
        loan_id: UUID,
        requested_amount: Decimal,
        client_message: str,
    ) -> RenewalRequestRecord:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                client = self._linked_client(cursor, user_id=user_id)
                cursor.execute(
                    """
                    select
                        loan.id,
                        loan.status,
                        loan_type.calculation_mode
                    from lending.loans loan
                    join lending.loan_types loan_type
                      on loan_type.id = loan.loan_type_id
                    where loan.id = %s
                      and loan.client_id = %s
                    for update
                    """,
                    (loan_id, client["id"]),
                )
                loan = cursor.fetchone()
                if not loan:
                    raise RenewalLoanNotEligible(
                        "This loan does not belong to the linked borrower."
                    )
                if str(loan["status"]).lower() not in {"active", "paid"}:
                    raise RenewalLoanNotEligible(
                        "Only an active or fully paid loan can be renewed."
                    )
                if str(loan["calculation_mode"]).lower() == "seven_by_seven":
                    raise RenewalLoanNotEligible(
                        "7x7 renewal requests are handled by the SPINA office."
                    )

                try:
                    cursor.execute(
                        """
                        insert into lending.client_renewal_requests (
                            client_id,
                            loan_id,
                            requested_by_user_id,
                            requested_amount,
                            client_message
                        )
                        values (%s, %s, %s, %s, %s)
                        returning id
                        """,
                        (
                            client["id"],
                            loan_id,
                            user_id,
                            requested_amount,
                            client_message,
                        ),
                    )
                except UniqueViolation as exc:
                    raise RenewalConflict(
                        "A renewal request for this loan is already pending."
                    ) from exc
                request_id = cursor.fetchone()["id"]
                cursor.execute(
                    """
                    insert into core.audit_logs (
                        actor_user_id,
                        action,
                        target_type,
                        target_id,
                        details
                    )
                    values (
                        %s,
                        'renewal.requested',
                        'client_renewal_request',
                        %s,
                        jsonb_build_object(
                            'client_id', %s::text,
                            'loan_id', %s::text,
                            'requested_amount', %s::text
                        )
                    )
                    """,
                    (
                        user_id,
                        request_id,
                        client["id"],
                        loan_id,
                        requested_amount,
                    ),
                )
                return self._fetch_request(cursor, request_id=request_id)

    def cancel_for_user(
        self,
        *,
        user_id: UUID,
        request_id: UUID,
    ) -> RenewalRequestRecord:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                client = self._linked_client(cursor, user_id=user_id)
                cursor.execute(
                    """
                    update lending.client_renewal_requests
                    set
                        status = 'cancelled',
                        cancelled_at = now(),
                        updated_at = now()
                    where id = %s
                      and client_id = %s
                      and status = 'pending'
                    returning id
                    """,
                    (request_id, client["id"]),
                )
                if not cursor.fetchone():
                    raise RenewalConflict(
                        "Only your own pending renewal request can be cancelled."
                    )
                cursor.execute(
                    """
                    insert into core.audit_logs (
                        actor_user_id,
                        action,
                        target_type,
                        target_id
                    )
                    values (
                        %s,
                        'renewal.cancelled',
                        'client_renewal_request',
                        %s
                    )
                    """,
                    (user_id, request_id),
                )
                return self._fetch_request(cursor, request_id=request_id)

    def list_for_management(
        self,
        *,
        status: RenewalStatus,
        limit: int,
        offset: int,
    ) -> tuple[RenewalRequestRecord, ...]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                return self._list_requests(
                    cursor,
                    status=status,
                    limit=limit,
                    offset=offset,
                )

    def review(
        self,
        *,
        actor_user_id: UUID,
        request_id: UUID,
        decision: RenewalDecision,
        review_note: str,
    ) -> RenewalRequestRecord:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    update lending.client_renewal_requests
                    set
                        status = %s,
                        reviewed_by_user_id = %s,
                        review_note = %s,
                        reviewed_at = now(),
                        updated_at = now()
                    where id = %s
                      and status = 'pending'
                    returning id
                    """,
                    (decision, actor_user_id, review_note, request_id),
                )
                if not cursor.fetchone():
                    raise RenewalConflict(
                        "This renewal request is no longer pending."
                    )
                cursor.execute(
                    """
                    insert into core.audit_logs (
                        actor_user_id,
                        action,
                        target_type,
                        target_id,
                        details
                    )
                    values (
                        %s,
                        %s,
                        'client_renewal_request',
                        %s,
                        jsonb_build_object('review_note', %s)
                    )
                    """,
                    (
                        actor_user_id,
                        f"renewal.{decision}",
                        request_id,
                        review_note,
                    ),
                )
                return self._fetch_request(cursor, request_id=request_id)

    @staticmethod
    def _linked_client(cursor, *, user_id: UUID):
        cursor.execute(
            """
            select id, client_code, full_name
            from lending.clients
            where user_id = %s
            limit 1
            """,
            (user_id,),
        )
        client = cursor.fetchone()
        if not client:
            raise RenewalBorrowerNotLinked(
                "This client account is not linked to a borrower record."
            )
        return client

    @staticmethod
    def _loan_from_row(row) -> RenewalLoanOption:
        calculation_mode = str(row["calculation_mode"])
        status = str(row["status"])
        eligible = (
            calculation_mode.lower() != "seven_by_seven"
            and status.lower() in {"active", "paid"}
        )
        if calculation_mode.lower() == "seven_by_seven":
            message = "7x7 renewals are handled by the SPINA office."
        elif not eligible:
            message = "This loan is not currently eligible for renewal."
        elif row["pending_request_id"]:
            message = "A renewal request is already pending."
        else:
            message = "Management will review this request before office processing."
        return RenewalLoanOption(
            loan_id=row["loan_id"],
            loan_number=str(row["loan_number"]),
            loan_type_name=str(row["loan_type_name"]),
            calculation_mode=calculation_mode,
            principal=Decimal(row["principal"]),
            remaining_balance=Decimal(row["remaining_balance"]),
            daily_amount=Decimal(row["daily_amount"]),
            date_released=row["date_released"],
            due_date=row["due_date"],
            status=status,
            eligible=eligible,
            eligibility_message=message,
            pending_request_id=row["pending_request_id"],
        )

    def _list_requests(
        self,
        cursor,
        *,
        client_id: UUID | None = None,
        status: RenewalStatus | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[RenewalRequestRecord, ...]:
        filters: list[str] = []
        params: list[object] = []
        if client_id is not None:
            filters.append("request.client_id = %s")
            params.append(client_id)
        if status is not None:
            filters.append("request.status = %s")
            params.append(status)
        where = f"where {' and '.join(filters)}" if filters else ""
        params.extend([limit, offset])
        cursor.execute(
            f"""
            select
                request.id as request_id,
                request.client_id,
                client.client_code,
                client.full_name as client_name,
                request.loan_id,
                loan.loan_number,
                coalesce(nullif(btrim(loan_type.name), ''), 'Loan')
                    as loan_type_name,
                loan.principal as current_principal,
                coalesce(state.remaining_balance, loan.principal)
                    as remaining_balance,
                request.requested_amount,
                request.client_message,
                request.status,
                request.submitted_at,
                request.reviewed_at,
                coalesce(
                    nullif(btrim(reviewer.full_name), ''),
                    nullif(btrim(reviewer.username), '')
                ) as reviewed_by_name,
                request.review_note,
                request.cancelled_at
            from lending.client_renewal_requests request
            join lending.clients client on client.id = request.client_id
            join lending.loans loan on loan.id = request.loan_id
            join lending.loan_types loan_type on loan_type.id = loan.loan_type_id
            left join lending.loan_collection_state state on state.loan_id = loan.id
            left join core.users reviewer
              on reviewer.id = request.reviewed_by_user_id
            {where}
            order by request.submitted_at desc, request.id desc
            limit %s offset %s
            """,
            tuple(params),
        )
        return tuple(self._request_from_row(row) for row in cursor.fetchall())

    def _fetch_request(self, cursor, *, request_id: UUID) -> RenewalRequestRecord:
        cursor.execute(
            """
            select
                request.id as request_id,
                request.client_id,
                client.client_code,
                client.full_name as client_name,
                request.loan_id,
                loan.loan_number,
                coalesce(nullif(btrim(loan_type.name), ''), 'Loan')
                    as loan_type_name,
                loan.principal as current_principal,
                coalesce(state.remaining_balance, loan.principal)
                    as remaining_balance,
                request.requested_amount,
                request.client_message,
                request.status,
                request.submitted_at,
                request.reviewed_at,
                coalesce(
                    nullif(btrim(reviewer.full_name), ''),
                    nullif(btrim(reviewer.username), '')
                ) as reviewed_by_name,
                request.review_note,
                request.cancelled_at
            from lending.client_renewal_requests request
            join lending.clients client on client.id = request.client_id
            join lending.loans loan on loan.id = request.loan_id
            join lending.loan_types loan_type on loan_type.id = loan.loan_type_id
            left join lending.loan_collection_state state on state.loan_id = loan.id
            left join core.users reviewer
              on reviewer.id = request.reviewed_by_user_id
            where request.id = %s
            """,
            (request_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise RenewalRequestNotFound("Renewal request was not found.")
        return self._request_from_row(row)

    @staticmethod
    def _request_from_row(row) -> RenewalRequestRecord:
        return RenewalRequestRecord(
            request_id=row["request_id"],
            client_id=row["client_id"],
            client_code=str(row["client_code"]),
            client_name=str(row["client_name"]),
            loan_id=row["loan_id"],
            loan_number=str(row["loan_number"]),
            loan_type_name=str(row["loan_type_name"]),
            current_principal=Decimal(row["current_principal"]),
            remaining_balance=Decimal(row["remaining_balance"]),
            requested_amount=Decimal(row["requested_amount"]),
            client_message=str(row["client_message"] or ""),
            status=str(row["status"]),
            submitted_at=row["submitted_at"],
            reviewed_at=row["reviewed_at"],
            reviewed_by_name=(
                str(row["reviewed_by_name"])
                if row["reviewed_by_name"]
                else None
            ),
            review_note=str(row["review_note"] or ""),
            cancelled_at=row["cancelled_at"],
        )

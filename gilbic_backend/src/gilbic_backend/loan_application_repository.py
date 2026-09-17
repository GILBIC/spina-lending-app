from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .database import open_connection
from .loan_application_information import LoanApplicationInformation


APPLICATION_REVIEW_PERMISSION = "client_onboarding.requirement.review"


@dataclass(frozen=True, slots=True)
class LoanApplicationVersionRecord:
    id: UUID
    application_id: UUID
    application_reference: str
    client_id: UUID
    cif_version_id: UUID
    version_number: int
    information: LoanApplicationInformation
    recorded_by_user_id: UUID
    recorded_at: datetime


class LoanApplicationError(RuntimeError):
    code = "loan_application_error"


class LoanApplicationConflict(LoanApplicationError):
    code = "loan_application_conflict"


class LoanApplicationAccessDenied(LoanApplicationError):
    code = "loan_application_access_denied"


_VERSION_SELECT = """
    select
        version.id,
        version.application_id,
        application.application_reference,
        version.client_id,
        version.cif_version_id,
        version.version_number,
        version.information,
        version.recorded_by_user_id,
        version.recorded_at,
        application.created_by_user_id
    from lending.loan_application_versions version
    join lending.loan_applications application
      on application.id = version.application_id
     and application.client_id = version.client_id
"""


def _record_from_row(row: Mapping[str, object]) -> LoanApplicationVersionRecord:
    return LoanApplicationVersionRecord(
        id=cast(UUID, row["id"]),
        application_id=cast(UUID, row["application_id"]),
        application_reference=str(row["application_reference"]),
        client_id=cast(UUID, row["client_id"]),
        cif_version_id=cast(UUID, row["cif_version_id"]),
        version_number=int(cast(int, row["version_number"])),
        information=LoanApplicationInformation.model_validate(row["information"]),
        recorded_by_user_id=cast(UUID, row["recorded_by_user_id"]),
        recorded_at=cast(datetime, row["recorded_at"]),
    )


def _information_json(
    information: LoanApplicationInformation,
) -> dict[str, object]:
    return cast(dict[str, object], information.model_dump(mode="json"))


def _row_matches_save(
    row: Mapping[str, object],
    *,
    actor_user_id: UUID,
    cif_version_id: UUID,
    information: LoanApplicationInformation,
) -> bool:
    return (
        row["recorded_by_user_id"] == actor_user_id
        and row["cif_version_id"] == cif_version_id
        and row["information"] == _information_json(information)
    )


class PostgresLoanApplicationRepository:
    def create_draft(
        self,
        *,
        actor_user_id: UUID,
        client_id: UUID,
        cif_version_id: UUID,
        application_reference: str,
        information: LoanApplicationInformation,
    ) -> LoanApplicationVersionRecord:
        reference = application_reference.strip()
        if not reference:
            raise LoanApplicationConflict("Application reference is required.")

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                self._require_actor(cursor, actor_user_id)

                existing = self._version_by_reference(
                    cursor,
                    application_reference=reference,
                    version_number=1,
                )
                if existing is not None:
                    return self._resolve_create_retry(
                        existing,
                        actor_user_id=actor_user_id,
                        client_id=client_id,
                        cif_version_id=cif_version_id,
                        information=information,
                    )

                self._require_eligible_source(
                    cursor,
                    client_id=client_id,
                    cif_version_id=cif_version_id,
                )

                header = cursor.execute(
                    """
                    insert into lending.loan_applications (
                        application_reference,
                        client_id,
                        created_by_user_id
                    )
                    values (%s, %s, %s)
                    on conflict (application_reference) do nothing
                    returning id, created_at
                    """,
                    (reference, client_id, actor_user_id),
                ).fetchone()

                if header is None:
                    existing = self._version_by_reference(
                        cursor,
                        application_reference=reference,
                        version_number=1,
                    )
                    if existing is None:
                        raise LoanApplicationConflict(
                            "Application reference already exists without a readable draft."
                        )
                    return self._resolve_create_retry(
                        existing,
                        actor_user_id=actor_user_id,
                        client_id=client_id,
                        cif_version_id=cif_version_id,
                        information=information,
                    )

                cursor.execute(
                    """
                    insert into lending.loan_application_versions (
                        application_id,
                        client_id,
                        cif_version_id,
                        version_number,
                        information,
                        recorded_by_user_id,
                        recorded_at
                    )
                    values (%s, %s, %s, 1, %s, %s, %s)
                    """,
                    (
                        header["id"],
                        client_id,
                        cif_version_id,
                        Jsonb(_information_json(information)),
                        actor_user_id,
                        header["created_at"],
                    ),
                )
                created = self._version_by_id(
                    cursor,
                    application_id=cast(UUID, header["id"]),
                    client_id=client_id,
                    version_number=1,
                )
                if created is None:
                    raise LoanApplicationConflict(
                        "Application draft was not readable after creation."
                    )
                return _record_from_row(created)

    def append_draft(
        self,
        *,
        actor_user_id: UUID,
        client_id: UUID,
        application_id: UUID,
        cif_version_id: UUID,
        expected_version_number: int,
        information: LoanApplicationInformation,
    ) -> LoanApplicationVersionRecord:
        if expected_version_number < 1:
            raise LoanApplicationConflict("Expected application version is invalid.")

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                self._require_actor(cursor, actor_user_id)

                header = cursor.execute(
                    """
                    select id
                    from lending.loan_applications
                    where id = %s and client_id = %s
                    for update
                    """,
                    (application_id, client_id),
                ).fetchone()
                if header is None:
                    raise LoanApplicationConflict("Application was not found.")

                expected = self._version_by_id(
                    cursor,
                    application_id=application_id,
                    client_id=client_id,
                    version_number=expected_version_number,
                )
                if expected is None:
                    raise LoanApplicationConflict("Expected application version was not found.")

                next_version_number = expected_version_number + 1
                next_version = self._version_by_id(
                    cursor,
                    application_id=application_id,
                    client_id=client_id,
                    version_number=next_version_number,
                )
                if next_version is not None:
                    if _row_matches_save(
                        next_version,
                        actor_user_id=actor_user_id,
                        cif_version_id=cif_version_id,
                        information=information,
                    ):
                        return _record_from_row(next_version)
                    raise LoanApplicationConflict(
                        "Application version has already advanced with different data."
                    )

                latest = cursor.execute(
                    """
                    select max(version_number) as version_number
                    from lending.loan_application_versions
                    where application_id = %s and client_id = %s
                    """,
                    (application_id, client_id),
                ).fetchone()
                if (
                    latest is None
                    or latest["version_number"] is None
                    or int(latest["version_number"]) != expected_version_number
                ):
                    raise LoanApplicationConflict(
                        "Application version changed; refresh before saving."
                    )

                if _row_matches_save(
                    expected,
                    actor_user_id=actor_user_id,
                    cif_version_id=cif_version_id,
                    information=information,
                ):
                    return _record_from_row(expected)

                self._require_eligible_source(
                    cursor,
                    client_id=client_id,
                    cif_version_id=cif_version_id,
                )

                cursor.execute(
                    """
                    insert into lending.loan_application_versions (
                        application_id,
                        client_id,
                        cif_version_id,
                        version_number,
                        information,
                        recorded_by_user_id
                    )
                    values (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        application_id,
                        client_id,
                        cif_version_id,
                        next_version_number,
                        Jsonb(_information_json(information)),
                        actor_user_id,
                    ),
                )
                created = self._version_by_id(
                    cursor,
                    application_id=application_id,
                    client_id=client_id,
                    version_number=next_version_number,
                )
                if created is None:
                    raise LoanApplicationConflict(
                        "Application version was not readable after creation."
                    )
                return _record_from_row(created)

    def get_version(
        self,
        *,
        actor_user_id: UUID,
        client_id: UUID,
        application_id: UUID,
        version_number: int,
    ) -> LoanApplicationVersionRecord:
        if version_number < 1:
            raise LoanApplicationConflict("Application version is invalid.")

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                self._require_actor(cursor, actor_user_id)
                row = self._version_by_id(
                    cursor,
                    application_id=application_id,
                    client_id=client_id,
                    version_number=version_number,
                )
                if row is None:
                    raise LoanApplicationConflict("Application version was not found.")
                return _record_from_row(row)

    @staticmethod
    def _require_actor(cursor, actor_user_id: UUID) -> None:
        allowed = cursor.execute(
            """
            select 1
            from core.users user_account
            where user_account.id = %s
              and user_account.status = 'active'
              and exists (
                  select 1
                  from core.user_roles user_role
                  join core.roles role on role.id = user_role.role_id
                  join core.role_permissions permission
                    on permission.role_id = role.id
                  where user_role.user_id = user_account.id
                    and role.code in ('employee', 'management')
                    and permission.permission_code = %s
              )
            """,
            (actor_user_id, APPLICATION_REVIEW_PERMISSION),
        ).fetchone()
        if allowed is None:
            raise LoanApplicationAccessDenied(
                "An active authorized office account is required."
            )

    @staticmethod
    def _require_eligible_source(
        cursor,
        *,
        client_id: UUID,
        cif_version_id: UUID,
    ) -> None:
        eligible = cursor.execute(
            """
            select 1
            from lending.client_cif_versions cif
            join lending.clients client on client.id = cif.client_id
            where cif.id = %s
              and cif.client_id = %s
              and cif.is_current = true
              and cif.status in ('draft', 'active')
              and client.status in ('inactive', 'active')
              and exists (
                  select 1
                  from lending.client_onboarding_applicants applicant
                  where applicant.promoted_client_id = cif.client_id
                    and applicant.status = 'eligible_for_cif'
              )
            """,
            (cif_version_id, client_id),
        ).fetchone()
        if eligible is None:
            raise LoanApplicationConflict(
                "No eligible current CIF is available for this application draft."
            )

    @staticmethod
    def _version_by_reference(
        cursor,
        *,
        application_reference: str,
        version_number: int,
    ):
        return cursor.execute(
            _VERSION_SELECT
            + """
            where application.application_reference = %s
              and version.version_number = %s
            """,
            (application_reference, version_number),
        ).fetchone()

    @staticmethod
    def _version_by_id(
        cursor,
        *,
        application_id: UUID,
        client_id: UUID,
        version_number: int,
    ):
        return cursor.execute(
            _VERSION_SELECT
            + """
            where version.application_id = %s
              and version.client_id = %s
              and version.version_number = %s
            """,
            (application_id, client_id, version_number),
        ).fetchone()

    @staticmethod
    def _resolve_create_retry(
        row: Mapping[str, object],
        *,
        actor_user_id: UUID,
        client_id: UUID,
        cif_version_id: UUID,
        information: LoanApplicationInformation,
    ) -> LoanApplicationVersionRecord:
        if (
            row["client_id"] != client_id
            or row["created_by_user_id"] != actor_user_id
            or not _row_matches_save(
                row,
                actor_user_id=actor_user_id,
                cif_version_id=cif_version_id,
                information=information,
            )
        ):
            raise LoanApplicationConflict(
                "Application reference is already bound to different draft data."
            )
        return _record_from_row(row)

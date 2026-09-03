from __future__ import annotations

import base64
import hmac
from hashlib import sha256
from hmac import compare_digest
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response

from .account_repository import PostgresAccountRepository
from .auth_client import SupabaseAuthClient, SupabaseAuthError
from .database import open_connection
from .management_repository import PostgresManagementRepository


_TOKEN_DIGEST = "e6852f560da75de8a8ac1a25340c5a0a8605998176e7ae1fcc9d66981a004439"
_TEST_CLIENT_CODE = "TEST-7X7-001"
_TEST_APP_VERSION = "0.1.0"


def _temporary_password(token: str, role_code: str) -> str:
    digest = hmac.new(
        token.encode("utf-8"),
        f"spina-test-account:{role_code}:2026-09-03".encode("utf-8"),
        sha256,
    ).digest()
    secret = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")[:20]
    return f"Spina-{role_code.title()}-{secret}!"


def _actor_user_id() -> UUID:
    with open_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select u.id
                from core.users u
                join core.user_roles ur on ur.user_id = u.id
                join core.roles r on r.id = ur.role_id
                where r.code = 'management'
                  and u.status = 'active'
                  and lower(u.username) <> 'spina_test_management'
                order by u.created_at
                limit 1
                """
            )
            row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=409, detail="An active Management owner is required.")
    return row[0]


def _core_user(username: str) -> tuple[UUID, UUID | None] | None:
    with open_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select id, external_auth_id
                from core.users
                where lower(username) = lower(%s)
                """,
                (username,),
            )
            row = cursor.fetchone()
    if not row:
        return None
    return row[0], row[1]


def _ensure_role_and_status(*, user_id: UUID, role_code: str) -> None:
    with open_connection() as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("delete from core.user_roles where user_id = %s", (user_id,))
                cursor.execute(
                    """
                    insert into core.user_roles (user_id, role_id)
                    select %s, id from core.roles where code = %s
                    """,
                    (user_id, role_code),
                )
                cursor.execute(
                    "update core.users set status = 'active', updated_at = now() where id = %s",
                    (user_id,),
                )


def _ensure_client_link(
    *,
    actor_user_id: UUID,
    user_id: UUID,
) -> None:
    with open_connection() as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select id, user_id
                    from lending.clients
                    where client_code = %s and status = 'active'
                    for update
                    """,
                    (_TEST_CLIENT_CODE,),
                )
                borrower = cursor.fetchone()
                if not borrower:
                    raise HTTPException(status_code=409, detail="The isolated test borrower is unavailable.")
                if borrower[1] not in {None, user_id}:
                    raise HTTPException(status_code=409, detail="The isolated test borrower is already linked.")
                cursor.execute(
                    "update lending.clients set user_id = %s, updated_at = now() where id = %s",
                    (user_id, borrower[0]),
                )
                cursor.execute(
                    """
                    insert into core.client_registration_requests (
                        user_id,
                        claimed_client_code,
                        claimed_phone_number,
                        status,
                        linked_client_id,
                        reviewed_by_user_id,
                        review_note,
                        submitted_at,
                        reviewed_at,
                        updated_at
                    ) values (
                        %s, %s, null, 'approved', %s, %s,
                        'Isolated temporary Client account for company acceptance testing.',
                        now(), now(), now()
                    )
                    on conflict (user_id) do update
                    set claimed_client_code = excluded.claimed_client_code,
                        status = 'approved',
                        linked_client_id = excluded.linked_client_id,
                        reviewed_by_user_id = excluded.reviewed_by_user_id,
                        review_note = excluded.review_note,
                        reviewed_at = now(),
                        updated_at = now()
                    """,
                    (user_id, _TEST_CLIENT_CODE, borrower[0], actor_user_id),
                )


def _get_or_create_auth_session(
    *,
    auth: SupabaseAuthClient,
    email: str,
    password: str,
):
    try:
        return auth.sign_in(email=email, password=password)
    except SupabaseAuthError:
        return auth.sign_up(email=email, password=password)


def create_temporary_test_account_bootstrap_router() -> APIRouter:
    router = APIRouter(include_in_schema=False)

    @router.get("/api/v1/internal/one-time-test-account-bootstrap")
    def bootstrap_test_accounts(
        response: Response,
        token: str = Query(min_length=32, max_length=200),
    ) -> dict[str, object]:
        supplied = sha256(token.encode("utf-8")).hexdigest()
        if not compare_digest(supplied, _TOKEN_DIGEST):
            raise HTTPException(status_code=404, detail="Not found.")

        specifications = (
            (
                "client",
                "Client",
                "spina_test_client",
                "gilbicsanjose+spina-test-client-20260903@gmail.com",
                "SPINA TEST CLIENT",
            ),
            (
                "employee",
                "Employee",
                "spina_test_employee",
                "gilbicsanjose+spina-test-employee-20260903@gmail.com",
                "SPINA TEST EMPLOYEE",
            ),
            (
                "collector",
                "Collector",
                "spina_test_collector",
                "gilbicsanjose+spina-test-collector-20260903@gmail.com",
                "SPINA TEST COLLECTOR",
            ),
            (
                "management",
                "Management",
                "spina_test_management",
                "gilbicsanjose+spina-test-management-20260903@gmail.com",
                "SPINA TEST MANAGEMENT",
            ),
        )
        actor_user_id = _actor_user_id()
        accounts = PostgresAccountRepository()
        management = PostgresManagementRepository()
        auth = SupabaseAuthClient()
        credentials: list[dict[str, object]] = []
        try:
            for role_code, role_name, username, email, full_name in specifications:
                password = _temporary_password(token, role_code)
                auth_session = _get_or_create_auth_session(
                    auth=auth,
                    email=email,
                    password=password,
                )
                existing = _core_user(username)
                if existing:
                    user_id, linked_auth_id = existing
                    if linked_auth_id != auth_session.auth_user_id:
                        raise HTTPException(
                            status_code=409,
                            detail=f"Test account {username} is linked to another authentication identity.",
                        )
                    _ensure_role_and_status(user_id=user_id, role_code=role_code)
                    if role_code == "client":
                        _ensure_client_link(actor_user_id=actor_user_id, user_id=user_id)
                elif role_code == "client":
                    context = accounts.create_client_profile(
                        auth_user_id=auth_session.auth_user_id,
                        username=username,
                        email=email,
                        full_name=full_name,
                        claimed_client_code=_TEST_CLIENT_CODE,
                        claimed_phone_number=None,
                    )
                    _ensure_role_and_status(user_id=context.user_id, role_code="client")
                    _ensure_client_link(actor_user_id=actor_user_id, user_id=context.user_id)
                else:
                    record = management.create_staff_profile(
                        actor_user_id=actor_user_id,
                        auth_user_id=auth_session.auth_user_id,
                        username=username,
                        email=email,
                        full_name=full_name,
                        role_code=role_code,
                    )
                    _ensure_role_and_status(user_id=record.id, role_code=role_code)

                verified_session = auth.sign_in(email=email, password=password)
                context = accounts.activate_and_register_device(
                    auth_user_id=verified_session.auth_user_id,
                    device_identifier=f"spina-web-test-{role_code}-20260903",
                    platform="web",
                    app_version=_TEST_APP_VERSION,
                )
                credentials.append(
                    {
                        "role": context.primary_role_name,
                        "username": username,
                        "password": password,
                        "login_verified": True,
                        "permission_count": len(context.permissions),
                    }
                )
        finally:
            auth.close()

        response.headers["Cache-Control"] = "no-store"
        return {"success": True, "data": {"accounts": credentials}}

    return router

from __future__ import annotations

import os
import secrets
from hashlib import sha256
from hmac import compare_digest
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response

from .auth_admin_client import SupabaseAuthAdminClient
from .database import open_connection
from .management_repository import PostgresManagementRepository


_TOKEN_DIGEST = "e6852f560da75de8a8ac1a25340c5a0a8605998176e7ae1fcc9d66981a004439"


def _temporary_password(role: str) -> str:
    return f"Spina-{role}-{secrets.token_urlsafe(12)}!"


def _account(username: str) -> tuple[UUID, UUID, str]:
    with open_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select id, external_auth_id, email
                from core.users
                where lower(username) = lower(%s)
                """,
                (username,),
            )
            row = cursor.fetchone()
    if not row or not row[1] or not row[2]:
        raise HTTPException(status_code=409, detail=f"Test account {username} is unavailable.")
    return row[0], row[1], str(row[2])


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


def _create_or_rotate_staff(
    *,
    admin: SupabaseAuthAdminClient,
    management: PostgresManagementRepository,
    actor_user_id: UUID,
    username: str,
    email: str,
    full_name: str,
    role_code: str,
    password: str,
) -> None:
    try:
        user_id, auth_user_id, _ = _account(username)
    except HTTPException:
        auth_user_id = admin.create_confirmed_user(email=email, password=password)
        try:
            record = management.create_staff_profile(
                actor_user_id=actor_user_id,
                auth_user_id=auth_user_id,
                username=username,
                email=email,
                full_name=full_name,
                role_code=role_code,
            )
            user_id = record.id
        except Exception:
            admin.delete_user(auth_user_id=auth_user_id)
            raise
    else:
        admin.update_password(auth_user_id=auth_user_id, password=password)
    _ensure_role_and_status(user_id=user_id, role_code=role_code)


def create_temporary_test_account_bootstrap_router() -> APIRouter:
    router = APIRouter(include_in_schema=False)

    @router.get("/api/v1/internal/one-time-test-account-bootstrap")
    def bootstrap_test_accounts(
        response: Response,
        token: str = Query(min_length=32, max_length=200),
    ) -> dict[str, object]:
        if os.getenv("VERCEL_ENV", "").strip().lower() != "preview":
            raise HTTPException(status_code=404, detail="Not found.")
        supplied = sha256(token.encode("utf-8")).hexdigest()
        if not compare_digest(supplied, _TOKEN_DIGEST):
            raise HTTPException(status_code=404, detail="Not found.")

        actor_user_id = _actor_user_id()
        passwords = {
            "client": _temporary_password("Client"),
            "employee": _temporary_password("Employee"),
            "collector": _temporary_password("Collector"),
            "management": _temporary_password("Management"),
        }
        admin = SupabaseAuthAdminClient()
        management = PostgresManagementRepository()
        try:
            client_id, client_auth_id, client_email = _account("testclientledger")
            admin.update_password(auth_user_id=client_auth_id, password=passwords["client"])
            _ensure_role_and_status(user_id=client_id, role_code="client")

            collector_id, collector_auth_id, collector_email = _account("collector")
            admin.update_password(auth_user_id=collector_auth_id, password=passwords["collector"])
            _ensure_role_and_status(user_id=collector_id, role_code="collector")

            _create_or_rotate_staff(
                admin=admin,
                management=management,
                actor_user_id=actor_user_id,
                username="spina_test_employee",
                email="spina.test.employee@example.com",
                full_name="SPINA TEST EMPLOYEE",
                role_code="employee",
                password=passwords["employee"],
            )
            _create_or_rotate_staff(
                admin=admin,
                management=management,
                actor_user_id=actor_user_id,
                username="spina_test_management",
                email="spina.test.management@example.com",
                full_name="SPINA TEST MANAGEMENT",
                role_code="management",
                password=passwords["management"],
            )
        finally:
            admin.close()

        response.headers["Cache-Control"] = "no-store"
        return {
            "success": True,
            "data": {
                "accounts": [
                    {"role": "Client", "username": "testclientledger", "email": client_email, "password": passwords["client"]},
                    {"role": "Employee", "username": "spina_test_employee", "email": "spina.test.employee@example.com", "password": passwords["employee"]},
                    {"role": "Collector", "username": "collector", "email": collector_email, "password": passwords["collector"]},
                    {"role": "Management", "username": "spina_test_management", "email": "spina.test.management@example.com", "password": passwords["management"]},
                ]
            },
        }

    return router

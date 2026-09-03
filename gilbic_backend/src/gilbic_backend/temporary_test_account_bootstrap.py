from __future__ import annotations

import os
import secrets
from hashlib import sha256
from hmac import compare_digest
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response

from .account_repository import PostgresAccountRepository
from .auth_client import SupabaseAuthClient
from .database import open_connection
from .management_repository import PostgresManagementRepository


_TOKEN_DIGEST = "e6852f560da75de8a8ac1a25340c5a0a8605998176e7ae1fcc9d66981a004439"


def _temporary_password(role: str) -> str:
    return f"Spina-{role}-{secrets.token_urlsafe(12)}!"


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


def _borrower_id(client_code: str) -> UUID:
    with open_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select id
                from lending.clients
                where client_code = %s and status = 'active' and user_id is null
                """,
                (client_code,),
            )
            row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=409, detail="The isolated test borrower is unavailable.")
    return row[0]


def _ensure_unused(accounts: PostgresAccountRepository, usernames: tuple[str, ...]) -> None:
    existing = [username for username in usernames if accounts.username_exists(username)]
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Test accounts already exist. The one-time bootstrap will not rotate them.",
        )


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

        specifications = (
            ("client", "Client", "spina_test_client", "spina.test.client.20260903@example.com", "SPINA TEST CLIENT"),
            ("employee", "Employee", "spina_test_employee", "spina.test.employee.20260903@example.com", "SPINA TEST EMPLOYEE"),
            ("collector", "Collector", "spina_test_collector", "spina.test.collector.20260903@example.com", "SPINA TEST COLLECTOR"),
            ("management", "Management", "spina_test_management", "spina.test.management.20260903@example.com", "SPINA TEST MANAGEMENT"),
        )
        actor_user_id = _actor_user_id()
        borrower_id = _borrower_id("TEST-7X7-001")
        accounts = PostgresAccountRepository()
        management = PostgresManagementRepository()
        _ensure_unused(accounts, tuple(item[2] for item in specifications))

        auth = SupabaseAuthClient()
        credentials: list[dict[str, object]] = []
        try:
            for role_code, role_name, username, email, full_name in specifications:
                password = _temporary_password(role_name)
                session = auth.sign_up(email=email, password=password)
                if role_code == "client":
                    context = accounts.create_client_profile(
                        auth_user_id=session.auth_user_id,
                        username=username,
                        email=email,
                        full_name=full_name,
                        claimed_client_code="TEST-7X7-001",
                        claimed_phone_number=None,
                    )
                    management.approve_client_registration(
                        actor_user_id=actor_user_id,
                        target_user_id=context.user_id,
                        client_id=borrower_id,
                        review_note="Isolated temporary Client account for company acceptance testing.",
                    )
                else:
                    management.create_staff_profile(
                        actor_user_id=actor_user_id,
                        auth_user_id=session.auth_user_id,
                        username=username,
                        email=email,
                        full_name=full_name,
                        role_code=role_code,
                    )
                credentials.append(
                    {
                        "role": role_name,
                        "username": username,
                        "email": email,
                        "password": password,
                        "email_confirmed": session.email_confirmed,
                    }
                )
        finally:
            auth.close()

        response.headers["Cache-Control"] = "no-store"
        return {"success": True, "data": {"accounts": credentials}}

    return router

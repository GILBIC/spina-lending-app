"""Explicit disposable synthetic database only; never application DB configuration."""

import os
import re
from uuid import uuid4

import psycopg
import pytest
from gilbic_backend.account_repository import AccountContext
from gilbic_backend.office_review_evidence_storage import PrivateEvidenceStore
from gilbic_backend.treasury_models import AccountConfigure
from gilbic_backend.treasury_repository import TreasuryService
from psycopg.rows import dict_row

PDF = b"%PDF-1.4\nSynthetic private evidence\n%%EOF"


def connect():
    value = os.getenv("GILBIC_TEST_DATABASE_URL")
    if not value:
        pytest.skip("Explicit disposable GILBIC_TEST_DATABASE_URL required.")
    params = psycopg.conninfo.conninfo_to_dict(value)
    if (
        params.get("host") not in {"127.0.0.1", "localhost", "::1"}
        or params.get("hostaddr", params.get("host"))
        not in {"127.0.0.1", "localhost", "::1"}
        or not re.fullmatch(
            r"spina_treasury_(?:validation_[a-f0-9]{24}|test_20261002)",
            params.get("dbname", ""),
        )
        or any(
            key in params for key in ["service", "servicefile", "passfile", "options"]
        )
    ):
        raise RuntimeError(
            "Only explicitly disposable loopback treasury test DB is allowed."
        )
    return psycopg.connect(value, row_factory=dict_row)


def actor(conn, role="management"):
    user_id, device_id = uuid4(), uuid4()
    conn.execute(
        "insert into core.users(id,username,full_name,status) values(%s,%s,'Synthetic treasury actor','active')",
        (user_id, "treasury-" + user_id.hex),
    )
    conn.execute(
        "insert into core.devices(id,user_id,device_identifier_hash,platform,status) values(%s,%s,%s,'web','active')",
        (device_id, user_id, device_id.hex),
    )
    conn.execute(
        "insert into core.user_roles(user_id,role_id) select %s,id from core.roles where code=%s",
        (user_id, role),
    )
    return AccountContext(
        user_id,
        user_id,
        "synthetic",
        None,
        "Synthetic treasury actor",
        "active",
        (role,),
        (),
        True,
        device_id,
    )


def grant_live(conn, user_id, *permissions):
    role_id = uuid4()
    conn.execute(
        "insert into core.roles(id,code,name) values(%s,%s,'Synthetic scoped grant')",
        (role_id, "treasury-" + role_id.hex),
    )
    conn.execute(
        "insert into core.user_roles(user_id,role_id) values(%s,%s)", (user_id, role_id)
    )
    for permission in permissions:
        conn.execute(
            "insert into core.role_permissions(role_id,permission_code) values(%s,%s)",
            (role_id, permission),
        )
    return role_id


@pytest.fixture
def treasury(monkeypatch, tmp_path):
    with connect() as conn:
        owner = actor(conn)
        client_actor = actor(conn, "client")
        client_id = uuid4()
        conn.execute(
            "insert into lending.clients(id,user_id,client_code,full_name,area) values(%s,%s,%s,'Synthetic borrower',%s)",
            (
                client_id,
                client_actor.user_id,
                client_id.hex,
                "SYNTHETIC-" + client_id.hex,
            ),
        )
        loan_type = conn.execute(
            "select id from lending.loan_types order by code limit 1"
        ).fetchone()
        if loan_type is None:
            type_id = uuid4()
            conn.execute(
                "insert into lending.loan_types(id,code,name,term_days,calculation_mode) values(%s,%s,'Synthetic Regular',10,'fixed_daily')",
                (type_id, type_id.hex),
            )
        else:
            type_id = loan_type["id"]
        loan_id = uuid4()
        conn.execute(
            """insert into lending.loans(id,loan_number,client_id,loan_type_id,principal,daily_amount,date_released,due_date,status)
          values(%s,%s,%s,%s,10000,1000,'2026-10-01','2026-10-11','active')""",
            (loan_id, loan_id.hex, client_id, type_id),
        )
    monkeypatch.setenv("SPINA_EMPLOYEE_OWNER_USER_ID", str(owner.user_id))
    monkeypatch.setenv("SPINA_TREASURY_ENABLED", "true")
    service = TreasuryService(
        connection_factory=connect, store=PrivateEvidenceStore(tmp_path / "private")
    )
    account_id, context_id = uuid4(), uuid4()
    service.execute(
        owner,
        AccountConfigure(
            action="account_configure",
            request_id=uuid4(),
            account_id=account_id,
            expected_version=0,
            ledger_context_id=context_id,
            context="synthetic",
            kind="gcash",
            alias="Synthetic receiving wallet",
            ownership="synthetic",
            custodian_user_id=owner.user_id,
            designated_receiving=True,
            payment_instructions="Synthetic recipient only",
        ),
    )
    return {
        "service": service,
        "owner": owner,
        "client_actor": client_actor,
        "account_id": account_id,
        "context_id": context_id,
        "client_id": client_id,
        "loan_id": loan_id,
    }


def version(fixture):
    with connect() as conn:
        return conn.execute(
            "select version from treasury.accounts where id=%s",
            (fixture["account_id"],),
        ).fetchone()["version"]


def evidence(fixture, purpose="recipient"):
    from gilbic_backend.treasury_claims import upload_evidence

    result = upload_evidence(
        fixture["service"],
        fixture["owner"],
        uuid4(),
        fixture["account_id"],
        purpose,
        PDF,
        "application/pdf",
    )
    return result["target_id"]

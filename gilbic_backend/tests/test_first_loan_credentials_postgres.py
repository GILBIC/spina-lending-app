from contextlib import contextmanager
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from psycopg.rows import tuple_row

from test_client_cif_review_confirmation_postgres import (  # noqa: F401
    DATABASE_URL,
    connection as connection,
    runtime_url as runtime_url,
)
from test_first_loan_postgres import setup, ready, private_fixture_configuration  # noqa: F401
from gilbic_backend.account_repository import AccountConflict
from gilbic_backend import client_account_repository as accounts_module
from gilbic_backend import first_loan_credential_service as service_module

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured"
)


def acquire_on(connection, monkeypatch):
    @contextmanager
    def acquire():
        with connection.transaction():
            yield connection

    @contextmanager
    def acquire_accounts():
        # Production open_connection uses tuple rows; this shared fixture uses
        # dict rows for assertions. Preserve the real account repository contract.
        original_factory = connection.row_factory
        connection.row_factory = tuple_row
        try:
            with connection.transaction():
                yield connection
        finally:
            connection.row_factory = original_factory

    monkeypatch.setattr(accounts_module, "open_connection", acquire_accounts)
    monkeypatch.setattr(service_module, "open_connection", acquire)


def test_active_onboarding_client_cannot_receive_manual_credentials_before_release(
    connection, monkeypatch
):
    _, repository, case = setup(connection, monkeypatch)
    acquire_on(connection, monkeypatch)
    accounts = accounts_module.PostgresClientAccountRepository()
    with pytest.raises(AccountConflict, match="committed first-loan release"):
        accounts.next_client_username(client_id=case["client"])
    with pytest.raises(AccountConflict, match="committed first-loan release"):
        accounts.create_client_account_profile(
            actor_user_id=case["actor"],
            auth_user_id=uuid4(),
            username="synthetic.not-issued",
            email="synthetic@example.test",
            client_id=case["client"],
        )
    assert (
        connection.execute(
            "select user_id from lending.clients where id=%s", (case["client"],)
        ).fetchone()["user_id"]
        is None
    )


def test_committed_release_provisions_one_reserved_auth_and_permanent_client_link(
    connection, monkeypatch
):
    _, repository, case = setup(connection, monkeypatch)
    record, args = ready(repository, case)
    repository.release(**args)
    acquire_on(connection, monkeypatch)
    created = []

    class Auth:
        def get_provisioned_user(self, **kwargs):
            return (
                connection.execute(
                    "select 1 from auth.users where id=%s", (kwargs["auth_user_id"],)
                ).fetchone()
                is not None
            )

        def create_user(self, **kwargs):
            created.append(kwargs["auth_user_id"])
            connection.execute(
                "insert into auth.users(id) values(%s)",
                (kwargs["auth_user_id"],),
            )
            return kwargs["auth_user_id"]

        def update_user_password(self, **kwargs):
            pytest.fail("Completed retry must not reset or recreate credentials")

    service = service_module.FirstLoanCredentialService(
        intents=service_module.PostgresFirstLoanCredentialRepository(),
        accounts=accounts_module.PostgresClientAccountRepository(),
        auth_admin=Auth(),
        mailer=SimpleNamespace(
            send_client_credentials=lambda **kwargs: SimpleNamespace(sent=False)
        ),
    )
    arguments = dict(
        loan_id=UUID(record["loan_id"]),
        actor_user_id=case["actor"],
        registered_device_id=case["device"],
    )
    first = service.provision(**arguments)
    assert first["status"] == "completed"
    assert first["credentials"]["password"]
    second = service.provision(**arguments)
    assert second["user_id"] == first["user_id"] and "credentials" not in second
    assert len(created) == 1
    saved = connection.execute(
        "select * from lending.first_loan_credential_intents where client_id=%s",
        (case["client"],),
    ).fetchone()
    assert saved["auth_user_id"] == created[0] and saved["status"] == "completed"
    assert str(saved["linked_user_id"]) == first["user_id"]
    assert (
        connection.execute(
            "select user_id from lending.clients where id=%s", (case["client"],)
        ).fetchone()["user_id"]
        == saved["linked_user_id"]
    )
    roles = connection.execute(
        "select r.code from core.roles r join core.user_roles ur on ur.role_id=r.id where ur.user_id=%s",
        (saved["linked_user_id"],),
    ).fetchall()
    assert roles == [{"code": "client"}]
    assert not any("password" in key for key in saved)


def test_credential_intent_cannot_be_borrowed_by_another_client_or_auth_identity(
    connection, monkeypatch
):
    _, repository, case = setup(connection, monkeypatch)
    record, args = ready(repository, case)
    repository.release(**args)
    acquire_on(connection, monkeypatch)
    intents = service_module.PostgresFirstLoanCredentialRepository()
    intents.prepare(
        loan_id=UUID(record["loan_id"]),
        actor_user_id=case["actor"],
        registered_device_id=case["device"],
    )
    intent = connection.execute(
        "select * from lending.first_loan_credential_intents where client_id=%s",
        (case["client"],),
    ).fetchone()
    with pytest.raises(AccountConflict, match="committed first-loan release"):
        accounts_module.PostgresClientAccountRepository().create_client_account_profile(
            actor_user_id=case["actor"],
            auth_user_id=uuid4(),
            username="synthetic.mismatch",
            email=intent["email"],
            client_id=case["client"],
            provisioning_intent_id=intent["id"],
        )


def test_revoked_device_blocks_credential_processing_without_reserving_auth(
    connection, monkeypatch
):
    _, repository, case = setup(connection, monkeypatch)
    record, args = ready(repository, case)
    repository.release(**args)
    acquire_on(connection, monkeypatch)
    connection.execute(
        "update core.devices set status='revoked' where id=%s", (case["device"],)
    )
    with pytest.raises(service_module.FirstLoanCredentialAccessDenied):
        service_module.PostgresFirstLoanCredentialRepository().prepare(
            loan_id=UUID(record["loan_id"]),
            actor_user_id=case["actor"],
            registered_device_id=case["device"],
        )
    assert (
        connection.execute(
            "select auth_user_id from lending.first_loan_credential_intents where client_id=%s",
            (case["client"],),
        ).fetchone()["auth_user_id"]
        is None
    )

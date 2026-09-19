from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from gilbic_backend.auth_admin_client import SupabaseAuthAdminClient
from gilbic_backend.auth_client import SupabaseAuthError
from gilbic_backend.config import Settings
from gilbic_backend.first_loan_credential_service import FirstLoanCredentialService


class Intents:
    def __init__(self):
        self.row = dict(
            id=uuid4(),
            client_id=uuid4(),
            auth_user_id=uuid4(),
            email="borrower@example.test",
            status="processing",
            linked_user_id=None,
            username=None,
        )
        self.linked = None
        self.events = []

    def prepare(self, **kwargs):
        self.events.append("prepare")

    @contextmanager
    def locked(self, **kwargs):
        yield self.row, None

    def linked_account(self, cursor, row):
        return self.linked

    def complete(self, cursor, row, *, user_id, username):
        row.update(status="completed", linked_user_id=user_id, username=username)

    def attempt(self, cursor, row, *, username):
        self.events.append("attempt")

    def uncertain(self, cursor, row, *, code):
        row.update(status="reconciliation_required")
        self.events.append(code)


class Auth:
    def __init__(self):
        self.users = {}
        self.creates = 0
        self.resets = 0
        self.fail_after_create = False
        self.fail_lookup = False

    def get_provisioned_user(self, *, auth_user_id, **kwargs):
        if self.fail_lookup:
            raise TimeoutError("provider unavailable")
        return auth_user_id in self.users

    def create_user(self, **kwargs):
        self.creates += 1
        self.users[kwargs["auth_user_id"]] = kwargs
        if self.fail_after_create:
            self.fail_after_create = False
            raise TimeoutError("provider committed, response lost")
        return kwargs["auth_user_id"]

    def update_user_password(self, **kwargs):
        self.resets += 1


class Accounts:
    def __init__(self, intents):
        self.intents = intents
        self.creates = 0
        self.fail = None

    def next_client_username(self, **kwargs):
        return "spina.c.synthetic"

    def create_client_account_profile(self, **kwargs):
        self.creates += 1
        if self.fail == "before":
            raise RuntimeError("no local commit")
        record = SimpleNamespace(id=uuid4(), full_name="Synthetic Borrower")
        self.intents.linked = {"id": record.id, "username": kwargs["username"]}
        if self.fail == "after":
            raise RuntimeError("local commit acknowledged late")
        return record


class Mailer:
    def __init__(self):
        self.calls = 0
        self.fail = False

    def send_client_credentials(self, **kwargs):
        self.calls += 1
        if self.fail:
            raise TimeoutError("mail unavailable")
        return SimpleNamespace(sent=True)


@pytest.fixture
def scenario():
    intents, auth, mailer = Intents(), Auth(), Mailer()
    accounts = Accounts(intents)
    service = FirstLoanCredentialService(
        intents=intents, accounts=accounts, auth_admin=auth, mailer=mailer
    )
    arguments = dict(
        loan_id=uuid4(), actor_user_id=uuid4(), registered_device_id=uuid4()
    )
    return service, arguments, intents, auth, accounts, mailer


def test_success_exposes_password_once_and_retry_creates_no_account_or_email(scenario):
    service, args, intents, auth, accounts, mailer = scenario
    first = service.provision(**args)
    assert first["status"] == "completed"
    assert first["credentials"]["password"]
    assert not any("password" in key for key in intents.row)
    second = service.provision(**args)
    assert second["user_id"] == first["user_id"]
    assert "credentials" not in second
    assert (auth.creates, auth.resets, accounts.creates, mailer.calls) == (1, 0, 1, 1)


def test_lost_provider_response_reconciles_reserved_identity_without_duplicate(
    scenario,
):
    service, args, intents, auth, accounts, mailer = scenario
    auth.fail_after_create = True
    reserved = intents.row["auth_user_id"]
    assert service.provision(**args)["status"] == "reconciliation_required"
    assert accounts.creates == 0
    assert service.provision(**args)["status"] == "completed"
    assert set(auth.users) == {reserved}
    assert (auth.creates, auth.resets, accounts.creates) == (1, 1, 1)


def test_lost_local_commit_response_recovers_link_without_reset_or_duplicate(scenario):
    service, args, intents, auth, accounts, mailer = scenario
    accounts.fail = "after"
    assert service.provision(**args)["status"] == "reconciliation_required"
    result = service.provision(**args)
    assert result["status"] == "completed"
    assert "credentials" not in result
    assert (auth.creates, auth.resets, accounts.creates, mailer.calls) == (1, 0, 1, 0)


def test_local_failure_retains_exact_auth_identity_for_resume(scenario):
    service, args, intents, auth, accounts, mailer = scenario
    accounts.fail = "before"
    assert service.provision(**args)["status"] == "reconciliation_required"
    accounts.fail = None
    assert service.provision(**args)["status"] == "completed"
    assert auth.creates == 1


def test_unavailable_reconciliation_does_not_attempt_create(scenario):
    service, args, intents, auth, accounts, mailer = scenario
    auth.fail_lookup = True
    assert service.provision(**args)["status"] == "reconciliation_required"
    assert (auth.creates, accounts.creates, mailer.calls) == (0, 0, 0)


def test_email_failure_returns_manual_credentials_without_repeating_release(scenario):
    service, args, intents, auth, accounts, mailer = scenario
    mailer.fail = True
    result = service.provision(**args)
    assert result["status"] == "completed"
    assert result["delivery"]["sent"] is False
    assert result["credentials"]["password"]


def admin(handler):
    return SupabaseAuthAdminClient(
        Settings(
            supabase_url="https://auth.example.test",
            supabase_secret_key="sb_secret_test",
        ),
        client=httpx.Client(
            base_url="https://auth.example.test", transport=httpx.MockTransport(handler)
        ),
    )


def test_auth_create_sends_reserved_id_and_server_owned_intent_marker():
    import json

    target, intent = uuid4(), uuid4()

    def handler(request):
        payload = json.loads(request.content)
        assert payload["id"] == str(target)
        assert payload["app_metadata"] == {"spina_provisioning_intent_id": str(intent)}
        assert "user_metadata" not in payload
        return httpx.Response(200, json={"id": str(target)})

    assert (
        admin(handler).create_user(
            email="BORROWER@example.test",
            password="fake",
            auth_user_id=target,
            provisioning_intent_id=intent,
        )
        == target
    )


@pytest.mark.parametrize(
    "mismatch", ["id", "email", "app_metadata", "deleted_at", "malformed"]
)
def test_reconciliation_rejects_wrong_identity_email_or_untrusted_marker(mismatch):
    target, intent = uuid4(), uuid4()
    payload = dict(
        id=str(target),
        email="borrower@example.test",
        app_metadata={"spina_provisioning_intent_id": str(intent)},
    )
    if mismatch == "malformed":
        payload = []
    else:
        payload[mismatch] = "wrong"
    with pytest.raises(SupabaseAuthError):
        admin(lambda request: httpx.Response(200, json=payload)).get_provisioned_user(
            auth_user_id=target,
            email="borrower@example.test",
            provisioning_intent_id=intent,
        )


def test_reconciliation_404_is_absent_but_server_error_is_not_absence():
    args = dict(
        auth_user_id=uuid4(),
        email="borrower@example.test",
        provisioning_intent_id=uuid4(),
    )
    assert (
        admin(lambda request: httpx.Response(404)).get_provisioned_user(**args) is False
    )
    with pytest.raises(SupabaseAuthError):
        admin(lambda request: httpx.Response(503)).get_provisioned_user(**args)

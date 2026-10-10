from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from gilbic_backend.auth_api import account_repository_dependency
from test_renewal_api import (
    CLIENT_USER_ID,
    MANAGEMENT_USER_ID,
    REQUEST_ID,
    FakeAccounts,
)
from test_renewal_workflow_cif_conflict_api import (
    HEADERS,
    WorkflowDatabase,
    make_client,
)


class SignerDatabase(WorkflowDatabase):
    def __init__(self):
        super().__init__(None)
        self.prepare_proof_review()
        self.state["row"].update(status="pending", borrower_user_id=CLIENT_USER_ID)
        self.state["signers"] = []

    def execute(self, sql, params=None):
        statement = " ".join(sql.split()).lower()
        if statement.startswith("select id, party_role"):
            self.result = deepcopy(self.state["signers"])
        elif statement.startswith("delete from lending.renewal_required_signers"):
            self.state["signers"] = []
        elif statement.startswith("insert into lending.renewal_required_signers"):
            self.state["signers"].append(
                saved_signer(
                    role=params[1],
                    name=params[2],
                    user_id=params[3],
                    government_id_verified_at=now() if params[4] else None,
                    selfie_verified_at=now() if params[5] else None,
                )
            )
        elif "set status='approved', approved_principal" in statement:
            self.state["row"].update(
                status="approved",
                approved_principal=params[0],
                management_override_reason=params[1],
                review_note=params[3],
                signer_readiness_status=params[4],
                office_processing_required=params[5],
                reviewed_at=now(),
            )
        elif statement.startswith("select office_processing_required"):
            self.result = dict(self.state["row"])
        elif statement.startswith("select count(*) filter"):
            signers = self.state["signers"]
            self.result = {
                "required_count": len(signers),
                "missing_app_count": sum(s["user_id"] is None for s in signers),
                "ready_count": sum(
                    all(
                        s[k] is not None
                        for k in (
                            "user_id",
                            "government_id_verified_at",
                            "selfie_verified_at",
                            "signed_at",
                        )
                    )
                    for s in signers
                ),
            }
        elif "set signer_readiness_status = %s" in statement:
            self.state["row"]["signer_readiness_status"] = params[0]
        elif statement.startswith("select id, user_id, government_id_verified_at"):
            self.result = next(
                (s for s in self.state["signers"] if s["id"] == params[0]), None
            )
        elif "set signed_at=coalesce(signed_at, now())" in statement:
            self.state["signers"][0]["signed_at"] = now()
        else:
            return super().execute(sql, params)
        return self


def now():
    return datetime.now(UTC)


def saved_signer(
    role="borrower", name="Synthetic Borrower", user_id=CLIENT_USER_ID, **changes
):
    return {
        "id": uuid4(),
        "party_role": role,
        "full_name": name,
        "user_id": user_id,
        "is_required": True,
        "government_id_verified_at": None,
        "selfie_verified_at": None,
        "signed_at": None,
        **changes,
    }


def signer(role="borrower", user_id=CLIENT_USER_ID):
    return {
        "party_role": role,
        "full_name": "Synthetic Borrower",
        "user_id": str(user_id) if user_id else None,
    }


def terms(*, office=False, signers=None):
    return {
        "decision": "approved",
        "approved_principal": "100.00",
        "office_processing_required": office,
        "signers": [signer()] if signers is None else signers,
    }


@pytest.mark.parametrize("prefix", ["/api/v1", "/api/mobile/v1"])
@pytest.mark.parametrize("office", [False, True])
@pytest.mark.parametrize("role", ["guarantor", "solidary_co_maker", "surety"])
def test_new_supporting_party_is_rejected_without_writes(
    monkeypatch, prefix, office, role
):
    db = SignerDatabase()
    before = deepcopy(db.state)
    response = make_client(monkeypatch, db).post(
        f"{prefix}/management/renewals/{REQUEST_ID}/terms",
        headers=HEADERS,
        json=terms(office=office, signers=[signer(), signer(role, MANAGEMENT_USER_ID)]),
    )
    assert response.status_code == 422
    assert db.state == before


@pytest.mark.parametrize("office", [False, True])
@pytest.mark.parametrize(
    "submitted", [[signer(), signer()], [signer(user_id=MANAGEMENT_USER_ID)]]
)
def test_borrower_role_cannot_add_another_person_or_duplicate(
    monkeypatch, office, submitted
):
    db = SignerDatabase()
    before = deepcopy(db.state)
    response = make_client(monkeypatch, db).post(
        f"/api/v1/management/renewals/{REQUEST_ID}/terms",
        headers=HEADERS,
        json=terms(office=office, signers=submitted),
    )
    assert response.status_code == 422
    assert db.state == before


@pytest.mark.parametrize(
    "office,submitted",
    [
        (False, [signer()]),
        (True, [signer()]),
        (True, [signer(user_id=None)]),
        (True, []),
    ],
)
def test_borrower_only_remote_and_office_paths_keep_their_existing_gates(
    monkeypatch, office, submitted
):
    db = SignerDatabase()
    response = make_client(monkeypatch, db).post(
        f"/api/v1/management/renewals/{REQUEST_ID}/terms",
        headers=HEADERS,
        json=terms(office=office, signers=submitted),
    )
    assert response.status_code == 200
    assert db.state["row"]["status"] == "approved"
    assert db.state["row"]["signer_readiness_status"] == (
        "office_required" if office else "pending"
    )
    assert all(
        s["party_role"] == "borrower" and s["signed_at"] is None
        for s in db.state["signers"]
    )
    assert db.state["audits"] == ["renewal.management.approved"]


@pytest.mark.parametrize(
    "role,signed",
    [
        ("guarantor", False),
        ("surety", True),
        ("solidary_co_maker", False),
        ("borrower", True),
    ],
)
def test_terms_do_not_replace_existing_supporting_or_signed_records(
    monkeypatch, role, signed
):
    db = SignerDatabase()
    db.state["signers"] = [saved_signer(role=role, signed_at=now() if signed else None)]
    before = deepcopy(db.state)
    response = make_client(monkeypatch, db).post(
        f"/api/v1/management/renewals/{REQUEST_ID}/terms",
        headers=HEADERS,
        json=terms(office=True),
    )
    assert response.status_code == 409
    assert (
        response.json()["detail"]["code"] == "renewal_existing_signers_review_required"
    )
    assert db.state == before


@pytest.mark.parametrize("submitted", [[], [signer(user_id=None)]])
def test_remote_renewal_still_requires_the_borrowers_linked_account(
    monkeypatch, submitted
):
    db = SignerDatabase()
    before = deepcopy(db.state)
    response = make_client(monkeypatch, db).post(
        f"/api/v1/management/renewals/{REQUEST_ID}/terms",
        headers=HEADERS,
        json=terms(signers=submitted),
    )
    assert response.status_code == 422
    assert db.state == before


@pytest.mark.parametrize("role", ["guarantor", "solidary_co_maker", "surety"])
@pytest.mark.parametrize("own_account", [False, True])
def test_existing_supporting_signer_keeps_own_account_signature_path(
    monkeypatch, role, own_account
):
    db = SignerDatabase()
    db.state["row"].update(status="approved", office_processing_required=False)
    old = saved_signer(
        role=role, government_id_verified_at=now(), selfie_verified_at=now()
    )
    db.state["signers"] = [old]
    before = deepcopy(db.state)
    client = make_client(monkeypatch, db)
    if own_account:
        client.app.dependency_overrides[account_repository_dependency] = lambda: (
            FakeAccounts(role="client")
        )
    response = client.post(
        f"/api/v1/renewals/{REQUEST_ID}/signers/{old['id']}/sign", headers=HEADERS
    )
    if own_account:
        assert response.status_code == 200
        assert db.state["signers"][0]["id"] == old["id"]
        assert db.state["signers"][0]["party_role"] == role
        assert db.state["signers"][0]["signed_at"] is not None
    else:
        assert response.status_code == 403
        assert db.state == before

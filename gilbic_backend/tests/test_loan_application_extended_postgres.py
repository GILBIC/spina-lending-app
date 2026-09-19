"""Real immutable-history proofs for additive declared application information."""
from copy import deepcopy
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

from gilbic_backend.loan_application_information import (
    ExtendedLoanApplicationInformation, LoanApplicationInformation,
    parse_loan_application_information,
)
from test_client_cif_review_confirmation_postgres import (
    DATABASE_URL, connection as connection, runtime_url as runtime_url,
)
from test_loan_application_extended_information import _details
from test_loan_application_history_postgres import _header, _read, _version
from test_loan_application_repository_postgres import (
    _append, _create, _read_version, _repository, _seed, _state,
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured"
)


def _information():
    return parse_loan_application_information({
        "request": {"requested_amount": "9007199254740993.01"},
        "details": _details(),
    })


def test_create_and_read_preserve_exact_optional_snapshot_and_money(connection, monkeypatch):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    information = _information()
    first = _create(repository, case, f"SYN-EXTENDED-{uuid4().hex}", information=information)
    row = _read(connection, "loan_application_versions", first.id)
    assert row["information"] == information.model_dump(mode="json")
    saved = _read_version(repository, case, first)
    assert isinstance(saved.information, ExtendedLoanApplicationInformation)
    assert saved.information.model_dump(mode="json") == row["information"]
    assert saved.information.model_dump(mode="json")["request"]["requested_amount"] == "9007199254740993.01"
    latest = repository.get_latest_by_reference(actor_user_id=case["actor"],
        client_id=case["client"], application_reference=first.application_reference)
    assert latest.id == first.id
    assert latest.information.model_dump(mode="json") == row["information"]


def test_append_details_preserves_legacy_version_and_exact_legacy_shape(connection, monkeypatch):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    first = _create(repository, case, f"SYN-LEGACY-{uuid4().hex}")
    legacy = _read(connection, "loan_application_versions", first.id)
    next_version = _append(repository, case, first, information=_information())
    assert next_version.version_number == 2
    assert _read(connection, "loan_application_versions", first.id) == legacy
    assert set(legacy["information"]) == {"request", "repayment"}
    assert type(_read_version(repository, case, first).information) is LoanApplicationInformation
    assert _read_version(repository, case, first, version_number=2).information == _information()


def test_identical_create_and_append_retry_do_not_duplicate_details_or_versions(connection, monkeypatch):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    reference = f"SYN-RETRY-{uuid4().hex}"
    first = _create(repository, case, reference, information=_information())
    before = _state(connection, case)
    assert _create(repository, case, reference, information=_information()).id == first.id
    assert _state(connection, case) == before
    changed = _information().model_dump(mode="json")
    changed["details"]["references"][0]["relationship"] = "Sibling, updated declaration"
    changed = parse_loan_application_information(changed)
    next_version = _append(repository, case, first, information=changed)
    before = _state(connection, case)
    assert _append(repository, case, first, information=changed).id == next_version.id
    assert _state(connection, case) == before


def test_changed_optional_detail_is_not_an_idempotent_retry(connection, monkeypatch):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    reference = f"SYN-CONFLICT-{uuid4().hex}"
    _create(repository, case, reference, information=_information())
    changed = _information().model_dump(mode="json")
    changed["details"]["employment"]["contact_number"] = "00000000099"
    before = _state(connection, case)
    from gilbic_backend.loan_application_repository import LoanApplicationConflict
    with pytest.raises(LoanApplicationConflict):
        _create(repository, case, reference, information=parse_loan_application_information(changed))
    assert _state(connection, case) == before


@pytest.mark.parametrize("details", [None, [], {}, {"schema_version": "1", "employment": {}, "references": []},
    {"schema_version": 2, "employment": {}, "references": []},
    {"schema_version": 1, "employment": [], "references": []},
    {"schema_version": 1, "employment": {}, "references": {}},
    {"schema_version": 1, "employment": {}, "references": [], "verified": True}])
def test_database_rejects_invalid_additional_section_shapes(connection, details):
    case = _seed(connection)
    header = _header(connection, case)
    information = LoanApplicationInformation().model_dump(mode="json")
    information["details"] = deepcopy(details)
    with pytest.raises(psycopg.errors.CheckViolation):
        with connection.transaction():
            _version(connection, case, header, information=Jsonb(information))


def test_extended_snapshot_remains_immutable(connection, monkeypatch):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    first = _create(repository, case, f"SYN-IMMUTABLE-{uuid4().hex}", information=_information())
    before = _read(connection, "loan_application_versions", first.id)
    with pytest.raises(psycopg.Error):
        with connection.transaction():
            connection.execute("update lending.loan_application_versions set information = %s where id = %s",
                               (Jsonb(LoanApplicationInformation().model_dump(mode="json")), first.id))
    assert _read(connection, "loan_application_versions", first.id) == before

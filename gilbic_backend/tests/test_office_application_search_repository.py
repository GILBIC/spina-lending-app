import base64
import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from test_client_cif_review_confirmation_postgres import DATABASE_URL, _summary_state
from test_client_cif_review_confirmation_postgres import (
    connection as connection,  # noqa: PLC0414 -- pytest fixture
)
from test_client_cif_review_confirmation_postgres import (
    runtime_url as runtime_url,  # noqa: PLC0414 -- pytest fixture
)
from test_client_onboarding_case_postgres import _case, _repository

db = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured"
)
KEYS = {
    "applicant_id",
    "intake_reference",
    "client_id",
    "full_name",
    "phone_number",
    "intake_status",
    "created_at",
    "updated_at",
}
APP_KEYS = {
    "application_id",
    "application_reference",
    "client_id",
    "created_at",
    "application_version_id",
    "version_number",
    "recorded_at",
}

MALFORMED_CURSOR_FIELDS = [
    ("id", 17),
    ("id", 17.5),
    ("id", None),
    ("id", True),
    ("id", []),
    ("id", {}),
    ("created_at", 17),
    ("created_at", None),
    ("created_at", {}),
    ("scope", 17),
    ("scope", None),
    ("scope", []),
    ("v", True),
    ("v", 1.0),
    ("v", None),
]


def _malformed_cursor(field, value):
    # Construct the documented token independently from production helpers.
    scope = hashlib.sha256(
        json.dumps(["intakes", "", None], separators=(",", ":")).encode()
    ).hexdigest()
    payload = {
        "v": 1,
        "scope": scope,
        "created_at": "2026-01-01T00:00:00+00:00",
        "id": "00000000-0000-0000-0000-000000000001",
    }
    payload[field] = value
    return (
        base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )


@pytest.mark.parametrize("applications", [False, True])
@pytest.mark.parametrize("field,value", MALFORMED_CURSOR_FIELDS)
def test_malformed_cursor_field_types_are_rejected_before_database_access(
    monkeypatch, applications, field, value
):
    from gilbic_backend import client_onboarding_repository as module

    def forbidden():
        pytest.fail("Malformed cursor fields must not acquire a database connection")

    monkeypatch.setattr(module, "open_connection", forbidden)
    repository = module.PostgresClientOnboardingRepository()
    cursor = _malformed_cursor(field, value)
    with pytest.raises(ValueError):
        if applications:
            repository.list_office_applications(
                actor_user_id=uuid4(),
                application_reference="Synthetic / Intake",
                cursor=cursor,
            )
        else:
            repository.search_office_cases(actor_user_id=uuid4(), cursor=cursor)


def _search(repository, case, **options):
    return repository.search_office_cases(actor_user_id=case["actor"], **options)


def _applications(repository, case, **options):
    return repository.list_office_applications(
        actor_user_id=case["actor"], application_reference=case["reference"], **options
    )


def _intake(
    connection,
    number,
    *,
    name="Duplicate Synthetic",
    phone="(+63) 912-345-6789",
    status="requirements_incomplete",
    client=None,
):
    identity = UUID(int=number + 1)
    connection.execute(
        """insert into lending.client_onboarding_applicants
        (id, application_reference, full_name, phone_number, present_address,
         national_id_egov_evidence_reference, tin_id_egov_evidence_reference,
         meralco_bill_evidence_reference, privacy_consent, accuracy_declaration,
         status, promoted_client_id, created_at, updated_at)
        values (%s,%s,%s,%s,'PRIVATE-ADDRESS','PRIVATE-ID','PRIVATE-TIN','PRIVATE-BILL',true,true,%s,%s,%s,%s)""",
        (
            identity,
            f"INTAKE/{number:05d}",
            name,
            phone,
            status,
            client,
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC),
        ),
    )
    return identity


def _headers(connection, case, count=3, versions=2):
    identities = []
    for number in range(count):
        identity = uuid4()
        identities.append(identity)
        connection.execute(
            """insert into lending.loan_applications (id, application_reference, client_id, created_by_user_id, created_at)
            values (%s,%s,%s,%s,%s)""",
            (
                identity,
                f"Loan / {identity.hex}",
                case["client"],
                case["actor"],
                datetime(2026, 1, 1, tzinfo=UTC),
            ),
        )
        for version in range(1, versions + 1):
            connection.execute(
                """insert into lending.loan_application_versions
                (application_id, client_id, cif_version_id, version_number, information, recorded_by_user_id)
                values (%s,%s,%s,%s,'{"request": {}, "repayment": {}}',%s)""",
                (identity, case["client"], case["cif"], version, case["actor"]),
            )
    return identities


@db
@pytest.mark.parametrize("count", [0, 1, 25, 26, 60])
def test_filtered_cardinality_pages_use_immutable_tuple_and_exact_minimal_projection(
    connection, monkeypatch, count
):
    case = _case(connection)
    ids = [
        _intake(connection, number, name="Task Six Finder Cardinality")
        for number in range(count)
    ]
    repository = _repository(connection, monkeypatch)
    found = []
    cursor = None
    while True:
        result = _search(
            repository, case, q="task six finder cardinality", cursor=cursor
        )
        assert len(result["items"]) <= 25
        assert isinstance(result["as_of"], datetime)
        for item in result["items"]:
            assert set(item) == KEYS
            assert item["intake_status"] == "requirements_incomplete"
            assert item["phone_number"] == "(+63) 912-345-6789"
            expected_day = 3 if cursor and item["applicant_id"] == ids[0] else 2
            assert item["updated_at"] == datetime(2026, 1, expected_day, tzinfo=UTC)
        found.extend(item["applicant_id"] for item in result["items"])
        if not result["has_more"]:
            assert result["next_cursor"] is None
            break
        cursor = result["next_cursor"]
        connection.execute(
            "update lending.client_onboarding_applicants set updated_at=%s where id=%s",
            (datetime(2026, 1, 3, tzinfo=UTC), ids[0]),
        )
    assert found == list(reversed(ids))
    assert len(found) == len(set(found))


@db
def test_empty_query_lists_recent_intakes_and_edits_do_not_reorder_pages(
    connection, monkeypatch
):
    case = _case(connection)
    identities = [_intake(connection, number) for number in range(4)]
    for number, day in [(0, 1), (1, 2), (2, 2), (3, 3)]:
        connection.execute(
            "update lending.client_onboarding_applicants set created_at=%s where id=%s",
            (datetime(2099, 1, day, tzinfo=UTC), identities[number]),
        )
    repository = _repository(connection, monkeypatch)
    first = _search(repository, case, limit=1)
    assert first["items"][0]["applicant_id"] == identities[3]
    assert first["items"][0]["intake_reference"] == "INTAKE/00003"
    assert set(first["items"][0]) == KEYS
    connection.execute(
        "update lending.client_onboarding_applicants set updated_at=%s, status=%s where id=%s",
        (datetime(2100, 1, 1, tzinfo=UTC), "requirements_rejected", identities[0]),
    )
    second = _search(repository, case, limit=1, cursor=first["next_cursor"])
    third = _search(repository, case, limit=1, cursor=second["next_cursor"])
    fourth = _search(repository, case, limit=1, cursor=third["next_cursor"])
    assert [
        second["items"][0]["applicant_id"],
        third["items"][0]["applicant_id"],
        fourth["items"][0]["applicant_id"],
    ] == [identities[2], identities[1], identities[0]]
    assert fourth["items"][0]["intake_status"] == "requirements_rejected"
    assert fourth["items"][0]["updated_at"] == datetime(2100, 1, 1, tzinfo=UTC)
    newest = _intake(connection, 4)
    connection.execute(
        "update lending.client_onboarding_applicants set created_at=%s where id=%s",
        (datetime(2099, 1, 4, tzinfo=UTC), newest),
    )
    assert _search(repository, case, limit=1)["items"][0]["applicant_id"] == newest
    assert (
        _search(repository, case, limit=1, cursor=first["next_cursor"])["items"][0][
            "applicant_id"
        ]
        == identities[2]
    )


@db
@pytest.mark.parametrize(
    "q,matched",
    [
        ("duplicate synthetic", True),
        ("(+63) 912-345", True),
        ("INTAKE/00000", True),
        ("_% literal", True),
        ("O'Quote", True),
        ("' OR 1=1 --", False),
        ("_% missing", False),
    ],
)
def test_name_phone_reference_and_literal_metacharacters_are_parameterized(
    connection, monkeypatch, q, matched
):
    case = _case(connection)
    identity = _intake(connection, 0, name="Duplicate Synthetic _% literal O'Quote")
    result = _search(_repository(connection, monkeypatch), case, q=q)
    assert [item["applicant_id"] for item in result["items"]] == (
        [identity] if matched else []
    )


@db
def test_linked_application_reference_search_uses_exists_without_fanout(
    connection, monkeypatch
):
    case = _case(connection, status="eligible_for_cif")
    _headers(connection, case, count=30)
    repository = _repository(connection, monkeypatch)
    before = _summary_state(connection, case)
    result = _search(repository, case, q="loan /")
    assert [item["applicant_id"] for item in result["items"]] == [case["applicant"]]
    assert _summary_state(connection, case) == before
    detail = repository.get_case_by_reference(
        actor_user_id=case["actor"],
        application_reference=result["items"][0]["intake_reference"],
        scope="office",
    )
    assert detail["applicant_id"] == result["items"][0]["applicant_id"]


@db
def test_application_headers_remain_independent_and_latest_versions_are_bounded(
    connection, monkeypatch
):
    case = _case(connection, status="eligible_for_cif")
    identities = _headers(connection, case, count=26, versions=3)
    repository = _repository(connection, monkeypatch)
    before = _summary_state(connection, case)
    first = _applications(repository, case)
    second = _applications(repository, case, cursor=first["next_cursor"])
    items = first["items"] + second["items"]
    assert [item["application_id"] for item in items] == sorted(
        identities, reverse=True
    )
    assert all(set(item) == APP_KEYS and item["version_number"] == 3 for item in items)
    assert first["intake"] == {
        "applicant_id": case["applicant"],
        "intake_reference": case["reference"],
        "client_id": case["client"],
        "intake_status": "eligible_for_cif",
    }
    assert not second["has_more"]
    assert _summary_state(connection, case) == before


@db
def test_unpromoted_and_versionless_applications_are_truthful(connection, monkeypatch):
    case = _case(connection)
    repository = _repository(connection, monkeypatch)
    result = _applications(repository, case)
    assert result["items"] == [] and result["intake"]["client_id"] is None
    connection.execute(
        "update lending.client_onboarding_applicants set promoted_client_id=%s where id=%s",
        (case["client"], case["applicant"]),
    )
    _headers(connection, case, count=1, versions=0)
    item = _applications(repository, case)["items"][0]
    assert (
        item["application_version_id"] is None
        and item["version_number"] is None
        and item["recorded_at"] is None
    )
    assert (
        repository.list_office_applications(
            actor_user_id=case["actor"], application_reference="missing"
        )
        is None
    )


@db
@pytest.mark.parametrize("role", ["employee", "management"])
@pytest.mark.parametrize("revocation", ["status", "role", "permission"])
def test_every_page_rechecks_same_persisted_authority_as_case_reads(
    connection, monkeypatch, role, revocation
):
    from gilbic_backend.client_onboarding_repository import ClientOnboardingAccessDenied

    case = _case(connection, role=role, status="eligible_for_cif")
    _intake(connection, 0)
    _headers(connection, case, count=2)
    repository = _repository(connection, monkeypatch)
    search_cursor = _search(repository, case, limit=1)["next_cursor"]
    app_cursor = _applications(repository, case, limit=1)["next_cursor"]
    if revocation == "status":
        connection.execute(
            "update core.users set status='inactive' where id=%s", (case["actor"],)
        )
    elif revocation == "role":
        connection.execute(
            "delete from core.user_roles where user_id=%s", (case["actor"],)
        )
    else:
        connection.execute(
            "delete from core.role_permissions where permission_code='client_onboarding.requirement.review' and role_id in (select id from core.roles where code=%s)",
            (role,),
        )
    for action in [
        lambda: _search(repository, case, cursor=search_cursor),
        lambda: _applications(repository, case, cursor=app_cursor),
        lambda: repository.get_case_by_reference(
            actor_user_id=case["actor"],
            application_reference=case["reference"],
            scope="office",
        ),
    ]:
        with pytest.raises(ClientOnboardingAccessDenied):
            action()


@db
@pytest.mark.parametrize("role", ["client", "collector"])
def test_wrong_persisted_roles_cannot_list_intakes_or_applications(
    connection, monkeypatch, role
):
    from gilbic_backend.client_onboarding_repository import ClientOnboardingAccessDenied

    case = _case(connection, role=role)
    repository = _repository(connection, monkeypatch)
    with pytest.raises(ClientOnboardingAccessDenied):
        _search(repository, case)
    with pytest.raises(ClientOnboardingAccessDenied):
        _applications(repository, case)


@db
def test_cursor_cannot_cross_query_status_reference_or_changed_client(
    connection, monkeypatch
):
    case = _case(connection, status="eligible_for_cif")
    _intake(connection, 0, name="Synthetic second")
    _headers(connection, case, count=2)
    repository = _repository(connection, monkeypatch)
    token = _search(repository, case, limit=1)["next_cursor"]
    for options in [{"q": "synthetic"}, {"status": "eligible_for_cif"}]:
        with pytest.raises(ValueError):
            _search(repository, case, cursor=token, **options)
    app_token = _applications(repository, case, limit=1)["next_cursor"]
    with pytest.raises(ValueError):
        _search(repository, case, cursor=app_token)
    connection.execute(
        "update lending.client_onboarding_applicants set promoted_client_id=%s where id=%s",
        (case["other"], case["applicant"]),
    )
    with pytest.raises(ValueError):
        _applications(repository, case, cursor=app_token)


@db
def test_status_filter_and_query_normalization_keep_cursor_scope(
    connection, monkeypatch
):
    case = _case(connection)
    _intake(connection, 0, name="Synthetic other")
    repository = _repository(connection, monkeypatch)
    first = _search(
        repository, case, q=" SYNTHETIC ", status="requirements_incomplete", limit=1
    )
    second = _search(
        repository,
        case,
        q="synthetic",
        status="requirements_incomplete",
        cursor=first["next_cursor"],
        limit=100,
    )
    assert len(second["items"]) == 1 and not second["has_more"]
    assert not _search(repository, case, status="requirements_rejected")["items"]


@pytest.mark.parametrize(
    "options",
    [
        {"q": None},
        {"q": 2},
        {"q": "ab"},
        {"q": "x" * 201},
        {"status": "approved"},
        {"limit": 0},
        {"limit": 101},
        {"limit": True},
        {"limit": 1.5},
        {"cursor": ""},
        {"cursor": "x" * 2049},
        {"cursor": "%%%invalid"},
        {"cursor": base64.urlsafe_b64encode(b"[]").decode()},
        {"cursor": base64.urlsafe_b64encode(json.dumps({"v": 1}).encode()).decode()},
    ],
)
def test_invalid_input_fails_before_database_access(monkeypatch, options):
    from gilbic_backend import client_onboarding_repository as module

    def forbidden():
        pytest.fail("Malformed finder input must not query the database")

    monkeypatch.setattr(module, "open_connection", forbidden)
    with pytest.raises(ValueError):
        module.PostgresClientOnboardingRepository().search_office_cases(
            actor_user_id=uuid4(), **options
        )


@db
def test_synthetic_query_plans_cover_name_phone_application_and_bounded_versions(
    connection, capsys
):
    from gilbic_backend.client_onboarding_repository import (
        _LIST_OFFICE_APPLICATIONS_SQL,
        _SEARCH_OFFICE_CASES_SQL,
    )

    case = _case(connection, status="eligible_for_cif")
    connection.execute(
        """insert into lending.client_onboarding_applicants
        (application_reference,full_name,phone_number,present_address,
         national_id_egov_evidence_reference,tin_id_egov_evidence_reference,
         meralco_bill_evidence_reference,privacy_consent,accuracy_declaration)
        select 'PLAN-INTAKE-'||n, 'Synthetic Plan Name '||n, '+63 (912) 345-'||lpad(n::text,4,'0'),
        'PRIVATE-ADDRESS','PRIVATE-ID','PRIVATE-TIN','PRIVATE-BILL',true,true
        from generate_series(1,10000) n""",
    )
    connection.execute(
        """insert into lending.loan_applications (application_reference,client_id,created_by_user_id)
        select 'PLAN-APP-'||n,%s,%s from generate_series(1,1000) n""",
        (case["client"], case["actor"]),
    )
    connection.execute(
        """insert into lending.loan_application_versions
        (application_id,client_id,cif_version_id,version_number,information,recorded_by_user_id)
        select app.id,app.client_id,%s,n,'{"request": {}, "repayment": {}}',%s
        from lending.loan_applications app cross join generate_series(1,10) n
        where app.client_id=%s""",
        (case["cif"], case["actor"], case["client"]),
    )
    for table in [
        "client_onboarding_applicants",
        "loan_applications",
        "loan_application_versions",
    ]:
        connection.execute("analyze lending." + table)
    plans = {}
    for label, q, pattern, phone in [
        ("recent", "", "%%", None),
        ("name", "synthetic plan name", "%synthetic plan name%", None),
        ("phone", "+63 (912) 345", "%+63 (912) 345%", "%63912345%"),
        ("application_reference", "plan-app-999", "%plan-app-999%", None),
    ]:
        rows = connection.execute(
            "explain (analyze, buffers, format json) " + _SEARCH_OFFICE_CASES_SQL,
            {
                "q": q,
                "pattern": pattern,
                "phone": phone,
                "status": None,
                "created_at": None,
                "id": None,
                "take": 26,
            },
        ).fetchone()
        plan = rows["QUERY PLAN"][0]
        assert plan["Plan"]["Actual Rows"] <= 26
        plans[label] = plan
    rows = connection.execute(
        "explain (analyze, buffers, format json) " + _LIST_OFFICE_APPLICATIONS_SQL,
        {"client_id": case["client"], "created_at": None, "id": None, "take": 26},
    ).fetchone()
    plan = rows["QUERY PLAN"][0]
    assert plan["Plan"]["Actual Rows"] == 26

    def nodes(node):
        yield node
        for child in node.get("Plans", []):
            yield from nodes(child)

    latest_limits = [
        node
        for node in nodes(plan["Plan"])
        if node["Node Type"] == "Limit" and node["Actual Loops"] == 26
    ]
    assert len(latest_limits) == 1 and latest_limits[0]["Actual Rows"] == 1
    plans["applications_with_10_versions"] = plan
    with capsys.disabled():
        print("\nSYNTHETIC_OFFICE_QUERY_PLANS " + json.dumps(plans, default=str))

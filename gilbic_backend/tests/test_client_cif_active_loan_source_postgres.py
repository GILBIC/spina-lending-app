"""Persisted CIF selection for a NEW loan approval, not historical issuance.

Reuse the existing disposable database, seed and state-preservation fixtures.
An active CIF is only one prerequisite: these tests do not confirm a complete
application, approve terms, authenticate an API actor, or issue any document.
"""
from __future__ import annotations

from dataclasses import fields
from uuid import uuid4

import pytest

from test_client_cif_review_confirmation_postgres import (
    DATABASE_URL,
    _insert,
    _read,
    _seed_summary_case,
    _summary_repository,
    _summary_state,
    connection as connection,
    runtime_url as runtime_url,
)


pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured"
)


def _seed_active_source(connection):
    case = _seed_summary_case(connection)
    connection.execute(
        """
        update lending.clients
        set status = 'active', full_name = 'Synthetic mutable Client display'
        where id = %s
        """,
        (case["client"],),
    )
    connection.execute(
        """
        update lending.client_cif_versions
        set status = 'active', baseline_liveness_status = 'passed',
            baseline_face_scan_evidence_reference = 'SYNTHETIC-BASELINE-FACE',
            activated_at = now() - interval '1 year',
            expires_at = now() + interval '4 years',
            review_due_at = now() + interval '4 years' - interval '90 days'
        where id = %s
        """,
        (case["cif"],),
    )
    return case


def _active_reader(repository):
    method = getattr(repository, "get_active_source_for_new_loan", None)
    assert callable(method), "Active CIF source selection for a new loan is not implemented"
    return method


@pytest.mark.parametrize("expiring", [False, True], ids=["valid", "expiring"])
def test_active_source_reads_exact_persisted_version_without_writes(
    connection, monkeypatch, expiring
):
    case = _seed_active_source(connection)
    if expiring:
        connection.execute(
            """
            update lending.client_cif_versions
            set activated_at = now() - interval '5 years' + interval '30 days',
                expires_at = now() + interval '30 days',
                review_due_at = now() - interval '60 days'
            where id = %s
            """,
            (case["cif"],),
        )
    repository = _summary_repository(connection, monkeypatch)
    read = _active_reader(repository)
    before = _summary_state(connection, case)
    stored = next(row for row in before["versions"] if row["id"] == case["cif"])

    first = read(client_id=case["client"], cif_version_id=case["cif"])
    repeated = read(client_id=case["client"], cif_version_id=case["cif"])

    assert first == repeated
    for field in fields(first):
        assert getattr(first, field.name) == stored[field.name]
    assert first.id == case["cif"] and first.client_id == case["client"]
    assert first.status == "active" and first.is_current
    # Stored CIF facts, not the older intake or mutable Client display name.
    assert first.full_name == "Synthetic CIF Borrower"
    assert first.phone_number == "00000000000"
    assert first.present_address == "Synthetic office test address"
    assert first.email is None
    assert next(row for row in before["clients"] if row["id"] == case["client"])["user_id"] is None
    assert _summary_state(connection, case) == before


@pytest.mark.parametrize(
    "scenario",
    [
        "draft", "not_current", "superseded", "inactive_client", "blocked_client",
        "closed_client", "expired", "expires_now", "reverification",
        "wrong_client", "wrong_cif", "unknown_client", "unknown_cif",
        "ineligible_applicant", "wrong_eligibility_link", "missing_applicant",
        "blank_baseline", "future_activation",
    ],
)
def test_active_source_rejects_unavailable_or_mismatched_records_without_writes(
    connection, monkeypatch, scenario
):
    from gilbic_backend.client_cif_repository import ClientCifConflict

    case = _seed_active_source(connection)
    other = _seed_active_source(connection)  # Identical name, different identities.
    client_id, cif_id = case["client"], case["cif"]
    if scenario in {"draft", "superseded"}:
        connection.execute(
            "update lending.client_cif_versions set status = %s where id = %s",
            (scenario, cif_id),
        )
    elif scenario == "not_current":
        connection.execute(
            "update lending.client_cif_versions set is_current = false where id = %s",
            (cif_id,),
        )
    elif scenario in {"inactive_client", "blocked_client", "closed_client"}:
        connection.execute(
            "update lending.clients set status = %s where id = %s",
            (scenario.removesuffix("_client"), client_id),
        )
    elif scenario in {"expired", "expires_now"}:
        connection.execute(
            """
            update lending.client_cif_versions
            set activated_at = now() - interval '5 years' - interval '1 day',
                expires_at = now() - (%s * interval '1 day'),
                review_due_at = now() - interval '91 days'
            where id = %s
            """,
            (1 if scenario == "expired" else 0, cif_id),
        )
    elif scenario == "reverification":
        connection.execute(
            """
            update lending.client_cif_versions
            set reverification_required_at = now(),
                reverification_reason = 'Synthetic required re-verification'
            where id = %s
            """,
            (cif_id,),
        )
    elif scenario == "wrong_client":
        client_id = other["client"]
    elif scenario == "wrong_cif":
        cif_id = other["cif"]
    elif scenario == "unknown_client":
        client_id = uuid4()
    elif scenario == "unknown_cif":
        cif_id = uuid4()
    elif scenario == "ineligible_applicant":
        connection.execute(
            "update lending.client_onboarding_applicants "
            "set status = 'requirements_rejected' where id = %s",
            (case["applicant"],),
        )
    elif scenario == "wrong_eligibility_link":
        connection.execute(
            "update lending.client_onboarding_applicants "
            "set promoted_client_id = %s where id = %s",
            (case["other"], case["applicant"]),
        )
    elif scenario == "missing_applicant":
        connection.execute(
            "delete from lending.client_onboarding_applicants where id = %s",
            (case["applicant"],),
        )
    elif scenario == "blank_baseline":
        connection.execute(
            "update lending.client_cif_versions "
            "set baseline_face_scan_evidence_reference = '   ' where id = %s",
            (cif_id,),
        )
    elif scenario == "future_activation":
        connection.execute(
            "update lending.client_cif_versions "
            "set activated_at = now() + interval '1 day' where id = %s",
            (cif_id,),
        )
    else:
        raise AssertionError(f"Unhandled synthetic scenario: {scenario}")
    repository = _summary_repository(connection, monkeypatch)
    read = _active_reader(repository)
    before, other_before = _summary_state(connection, case), _summary_state(connection, other)

    with pytest.raises(ClientCifConflict):
        read(client_id=client_id, cif_version_id=cif_id)

    assert _summary_state(connection, case) == before
    assert _summary_state(connection, other) == other_before


def test_active_source_never_substitutes_a_newer_version_or_rewrites_old_evidence(
    connection, monkeypatch
):
    from gilbic_backend.client_cif_repository import ClientCifConflict

    case = _seed_active_source(connection)
    old_evidence = _insert(connection, case)  # Existing schema fixture, not approval.
    connection.execute(
        "update lending.client_cif_versions set is_current = false, status = 'superseded' "
        "where id = %s",
        (case["cif"],),
    )
    connection.execute(
        """
        update lending.client_cif_versions
        set is_current = true, status = 'active', baseline_liveness_status = 'passed',
            baseline_face_scan_evidence_reference = 'SYNTHETIC-NEW-BASELINE',
            activated_at = now(), expires_at = now() + interval '5 years',
            review_due_at = now() + interval '5 years' - interval '90 days',
            present_address = 'Synthetic newer CIF address'
        where id = %s
        """,
        (case["next_cif"],),
    )
    read = _active_reader(_summary_repository(connection, monkeypatch))
    before = _summary_state(connection, case)

    with pytest.raises(ClientCifConflict):
        read(client_id=case["client"], cif_version_id=case["cif"])
    selected = read(client_id=case["client"], cif_version_id=case["next_cif"])

    assert selected.id == case["next_cif"] and selected.version_number == 2
    assert selected.present_address == "Synthetic newer CIF address"
    assert _read(connection, old_evidence["id"]) == old_evidence
    assert _summary_state(connection, case) == before

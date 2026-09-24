"""Pure source identity and retry checks, not PostgreSQL or release acceptance."""

from copy import deepcopy
from importlib import import_module
from uuid import UUID

import pytest

MODULE = "gilbic_backend.first_loan_disclosure_binding"
CALCULATION = UUID("00000000-0000-4000-8000-000000000021")
DIGEST = "a" * 64


def binding_module():
    try:
        return import_module(MODULE)
    except ModuleNotFoundError as error:
        if error.name != MODULE:
            raise
        pytest.fail("The disclosure binding value guards are missing", pytrace=False)


@pytest.mark.parametrize("identity", [CALCULATION, str(CALCULATION)])
def test_source_pair_preserves_valid_identity_and_digest(identity):
    assert binding_module().source_pair(identity, DIGEST) == (str(CALCULATION), DIGEST)


@pytest.mark.parametrize(
    "identity,digest",
    [
        (None, None),
        (None, DIGEST),
        (CALCULATION, None),
        (True, DIGEST),
        (1.0, DIGEST),
        (1, DIGEST),
        ("not-an-id", DIGEST),
        (CALCULATION, ""),
        (CALCULATION, "A" * 64),
        (CALCULATION, "z" * 64),
        (CALCULATION, "a" * 63),
        (CALCULATION, "a" * 65),
        (CALCULATION, True),
        (CALCULATION, 0),
    ],
)
def test_new_source_pair_rejects_missing_or_malformed_values(identity, digest):
    module = binding_module()
    with pytest.raises(module.DisclosureBindingError):
        module.source_pair(identity, digest)


def test_exact_schema_two_retry_preserves_the_saved_packet():
    packet = {
        "schema_version": 2,
        "tax_disclosure": {
            "calculation_id": str(CALCULATION),
            "review_digest": DIGEST,
            "financial_snapshot": {"synthetic": "unchanged"},
        },
    }
    original = deepcopy(packet)
    module = binding_module()
    assert module.retry_matches(packet, CALCULATION, DIGEST) is True
    assert module.retry_matches(packet, str(CALCULATION), DIGEST) is True
    assert packet == original


@pytest.mark.parametrize(
    "identity,digest",
    [
        (None, None),
        (None, DIGEST),
        (CALCULATION, None),
        (UUID("00000000-0000-4000-8000-000000000022"), DIGEST),
        (CALCULATION, "b" * 64),
    ],
)
def test_schema_two_retry_cannot_drop_or_substitute_source(identity, digest):
    packet = {
        "schema_version": 2,
        "tax_disclosure": {
            "calculation_id": str(CALCULATION),
            "review_digest": DIGEST,
            "financial_snapshot": {},
        },
    }
    original = deepcopy(packet)
    assert binding_module().retry_matches(packet, identity, digest) is False
    assert packet == original


def test_schema_one_historical_retry_cannot_add_a_new_review():
    packet = {"schema_version": 1, "terms": {"synthetic": "original"}}
    original = deepcopy(packet)
    module = binding_module()
    assert module.retry_matches(packet, None, None) is True
    assert module.retry_matches(packet, CALCULATION, DIGEST) is False
    assert module.retry_matches(packet, None, DIGEST) is False
    assert packet == original


@pytest.mark.parametrize(
    "packet",
    [
        {},
        {"schema_version": True},
        {"schema_version": "1"},
        {"schema_version": 3},
        {"schema_version": 1, "tax_disclosure": {}},
        {"schema_version": 2},
        {"schema_version": 2, "tax_disclosure": None},
        {"schema_version": 2, "tax_disclosure": []},
    ],
)
def test_malformed_or_unknown_packets_cannot_use_legacy_retry(packet):
    original = deepcopy(packet)
    assert binding_module().retry_matches(packet, None, None) is False
    assert packet == original


@pytest.mark.parametrize(
    "change",
    [
        {"financial_snapshot": None},
        {"financial_snapshot": []},
        {"support_storage_key": "private"},
        {"calculation_id": CALCULATION.hex},
    ],
)
def test_schema_two_retry_rejects_malformed_or_extra_private_binding(change):
    packet = {
        "schema_version": 2,
        "tax_disclosure": {
            "calculation_id": str(CALCULATION),
            "review_digest": DIGEST,
            "financial_snapshot": {},
            **change,
        },
    }
    assert binding_module().retry_matches(packet, CALCULATION, DIGEST) is False

from importlib import import_module

import pytest


def test_optional_identity_facts_have_typed_dates_and_preserve_absence():
    model = import_module(
        "gilbic_backend.client_cif_identity_information"
    ).CifIdentityInformation
    assert model().model_dump(mode="json") == {
        "birth_date": None,
        "birth_place": None,
        "civil_status": None,
        "citizenship": None,
    }
    record = model(
        birth_date="1990-02-03",
        birth_place="  Quezon   City ",
        citizenship=" Filipino ",
    )
    assert record.model_dump(mode="json")["birth_place"] == "Quezon City"
    assert record.model_dump(mode="json")["birth_date"] == "1990-02-03"
    with pytest.raises(ValueError):
        model(birth_date="not-a-date")
    with pytest.raises(ValueError):
        model(verified=True)

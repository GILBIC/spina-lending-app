"""Review amounts retain all cents permitted by PostgreSQL NUMERIC(18,2)."""

from decimal import Decimal

from gilbic_backend import retained_cutoff_assessment_repository as repository


def test_source_json_decoder_preserves_large_cents_and_original_eir():
    decode = getattr(repository, "_source_json_loads", None)
    assert decode is not None, "Cutoff source JSON requires exact Decimal decoding"
    source = decode(
        b'{"ecl_amount":9999999999999999.99,"original_daily_eir":0.001234567891,"version":1}'
    )
    assert source["ecl_amount"] == Decimal("9999999999999999.99")
    assert repository._money(source["ecl_amount"]) == "9999999999999999.99"
    assert source["original_daily_eir"] == Decimal("0.001234567891")
    assert source["version"] == 1

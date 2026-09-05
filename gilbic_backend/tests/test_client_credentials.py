from __future__ import annotations


AMBIGUOUS = set("O0Il1")
SAFE_SYMBOLS = set("@#$%")


def test_client_username_base_uses_normalized_client_code() -> None:
    from gilbic_backend.client_credentials import client_username_base

    assert client_username_base("C-001") == "spina.c.001"
    assert client_username_base("  ABC---  99  ") == "spina.abc.99"


def test_client_username_base_has_safe_fallback_when_code_has_no_ascii_alnum() -> None:
    from gilbic_backend.client_credentials import client_username_base

    assert client_username_base("###") == "spina.client"


def test_generated_password_is_16_chars_and_has_every_required_character_class() -> None:
    from gilbic_backend.client_credentials import generate_password

    for _ in range(40):
        password = generate_password()
        assert len(password) == 16
        assert any(char.isupper() for char in password)
        assert any(char.islower() for char in password)
        assert any(char.isdigit() for char in password)
        assert any(char in SAFE_SYMBOLS for char in password)
        assert not (set(password) & AMBIGUOUS)


def test_generated_password_rejects_lengths_too_short_for_required_classes() -> None:
    from gilbic_backend.client_credentials import generate_password

    try:
        generate_password(3)
    except ValueError as exc:
        assert "at least 4" in str(exc)
    else:
        raise AssertionError("generate_password must reject lengths below four characters")

from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected one match in {path}; found {count}.")
    target.write_text(text.replace(old, new), encoding="utf-8")


def patch_domain() -> None:
    path = Path("gilbic_backend/src/gilbic_backend/cif_domain.py")
    text = path.read_text(encoding="utf-8")
    old = """    if isinstance(value, (set, frozenset)):
        return list(value)
"""
    new = """    if isinstance(value, (set, frozenset)):
        return sorted(value, key=lambda item: str(item))
"""
    if text.count(old) != 1:
        raise SystemExit("Expected one unordered CIF set serializer.")
    text = text.replace(old, new)
    if "def normalize_external_reference(" in text:
        raise SystemExit("External-reference normalizer already exists.")
    text += """


def normalize_external_reference(
    value: str,
    *,
    name: str = "External reference",
    maximum: int = 500,
) -> str:
    \"\"\"Accept an opaque restricted-object reference, never inline file bytes.\"\"\"

    if not isinstance(value, str):
        raise ValueError(f"{name} must be text.")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"{name} must not contain control characters.")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} is required.")
    if len(normalized) > maximum:
        raise ValueError(f"{name} is too long.")
    lowered = normalized.lower()
    if (
        lowered.startswith("data:")
        or lowered.startswith("base64:")
        or ";base64," in lowered
    ):
        raise ValueError(
            f"{name} must reference an approved restricted object, not inline data."
        )
    return normalized
"""
    path.write_text(text, encoding="utf-8")


def patch_cif_repository() -> None:
    path = "gilbic_backend/src/gilbic_backend/cif_repository.py"
    replace_once(
        path,
        """from .cif_domain import (
    ALLOWED_REVERIFICATION_REASONS,
    canonical_cif_digest,
)
""",
        """from .cif_domain import (
    ALLOWED_REVERIFICATION_REASONS,
    canonical_cif_digest,
    normalize_external_reference,
)
""",
    )
    replace_once(
        path,
        """        permanent = cls._normalize_object(
            draft.permanent_address,
            name="Permanent address",
            allowed_keys=_ADDRESS_KEYS,
        )
        livelihood = cls._normalize_object(
""",
        """        permanent = cls._normalize_object(
            draft.permanent_address,
            name="Permanent address",
            allowed_keys=_ADDRESS_KEYS,
        )
        if draft.same_as_present_address:
            permanent = dict(present)
        livelihood = cls._normalize_object(
""",
    )
    replace_once(
        path,
        """        signature_reference = cls._normalize_text(
            draft.client_signature_reference,
            name="Client signature reference",
            maximum=500,
            required=False,
        )
""",
        """        signature_reference = cls._normalize_text(
            draft.client_signature_reference,
            name="Client signature reference",
            maximum=500,
            required=False,
        )
        if signature_reference:
            try:
                signature_reference = normalize_external_reference(
                    signature_reference,
                    name="Client signature reference",
                    maximum=500,
                )
            except ValueError as error:
                raise CifInvalid(str(error)) from error
""",
    )
    replace_once(
        path,
        """    @classmethod
    def _assert_complete(cls, row: Mapping[str, Any]) -> None:
""",
        """    @staticmethod
    def _has_meaningful_mapping(value: object) -> bool:
        if not isinstance(value, Mapping):
            return False
        return any(
            item is not None
            and (not isinstance(item, str) or bool(item.strip()))
            for item in value.values()
        )

    @classmethod
    def _assert_complete(cls, row: Mapping[str, Any]) -> None:
""",
    )
    replace_once(
        path,
        """        for key, label in (
            ("present_address", "present address"),
            ("permanent_address", "permanent address"),
            ("livelihood_profile", "livelihood profile"),
        ):
            value = row.get(key)
            if not isinstance(value, Mapping) or not value:
                missing.append(label)
""",
        """        for key, label in (
            ("present_address", "present address"),
            ("permanent_address", "permanent address"),
            ("livelihood_profile", "livelihood profile"),
        ):
            if not cls._has_meaningful_mapping(row.get(key)):
                missing.append(label)
""",
    )


def patch_restricted_repository() -> None:
    path = "gilbic_backend/src/gilbic_backend/restricted_identity_repository.py"
    replace_once(
        path,
        """from .cif_domain import (
    ALLOWED_ACCESS_PURPOSES,
    ALLOWED_EVIDENCE_TYPES,
    normalize_masked_reference,
)
""",
        """from .cif_domain import (
    ALLOWED_ACCESS_PURPOSES,
    ALLOWED_EVIDENCE_TYPES,
    normalize_external_reference,
    normalize_masked_reference,
)
""",
    )
    replace_once(
        path,
        """        external_reference = cls._normalize_text(
            data.external_evidence_reference,
            name="External evidence reference",
            maximum=500,
            required=True,
        )
""",
        """        try:
            external_reference = normalize_external_reference(
                data.external_evidence_reference,
                name="External evidence reference",
                maximum=500,
            )
        except ValueError as error:
            raise RestrictedIdentityInvalid(str(error)) from error
""",
    )


def main() -> int:
    patch_domain()
    patch_cif_repository()
    patch_restricted_repository()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CifIdentityInformation(BaseModel):
    """Optional declared identity facts; presence does not imply verification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    birth_date: date | None = None
    birth_place: str | None = Field(default=None, max_length=300)
    civil_status: str | None = Field(default=None, max_length=100)
    citizenship: str | None = Field(default=None, max_length=100)

    @field_validator("birth_place", "civil_status", "citizenship", mode="before")
    @classmethod
    def normalize_text(cls, value):
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Identity information must be text.")
        return " ".join(value.split()) or None


def cif_information_from_row(row) -> dict:
    information = {
        name: row[name]
        for name in ("full_name", "phone_number", "email", "present_address")
    }
    if row.get("identity_information") is not None:
        information["identity_information"] = row["identity_information"]
    return information

from pathlib import Path


def test_renewal_review_audit_note_is_explicitly_typed() -> None:
    repository_source = (
        Path(__file__).parents[1]
        / "src"
        / "gilbic_backend"
        / "renewal_repository.py"
    ).read_text(encoding="utf-8")

    assert "jsonb_build_object('review_note', %s::text)" in repository_source
    assert "jsonb_build_object('review_note', %s)" not in repository_source

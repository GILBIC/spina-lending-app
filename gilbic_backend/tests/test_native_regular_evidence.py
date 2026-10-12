from uuid import uuid4

import pytest
from gilbic_backend.native_regular_evidence import verify_native_regular_files
from gilbic_backend.office_review_evidence_storage import (
    EvidenceFileError,
    PrivateEvidenceStore,
)

PDF = b"%PDF-1.4\nsynthetic signed contract\n%%EOF"


def test_missing_signed_packet_blocks_retained_native_evidence_even_with_unchanged_metadata(
    tmp_path,
):
    store = PrivateEvidenceStore(tmp_path / "private-native")
    key = uuid4()
    digest = store.put(key, PDF, "application/pdf")
    source = {
        "origin_kind": "native_payout",
        "snapshot": {
            "packet_document": {
                "storage_key": str(key),
                "content_sha256": digest,
                "byte_count": len(PDF),
            },
            "debit_preparation": {"snapshot": {}},
            "completion_preparation": {"snapshot": {}},
        },
    }
    verify_native_regular_files(source, store=store)
    (store.root / f"{key.hex}.bin").unlink()
    with pytest.raises(EvidenceFileError, match="unavailable"):
        verify_native_regular_files(source, store=store)


def test_changed_payout_bytes_cannot_substitute_for_exact_signed_source(tmp_path):
    store = PrivateEvidenceStore(tmp_path / "private-native")
    packet, receipt = uuid4(), uuid4()
    digest = store.put(packet, PDF, "application/pdf")
    store.put(receipt, PDF, "application/pdf")
    source = {
        "origin_kind": "native_payout",
        "snapshot": {
            "packet_document": {
                "storage_key": str(packet),
                "content_sha256": digest,
                "byte_count": len(PDF),
            },
            "debit_preparation": {
                "snapshot": {
                    "evidence": {
                        "id": str(receipt),
                        "sha256": digest,
                        "byte_count": len(PDF),
                    }
                }
            },
            "completion_preparation": {"snapshot": {}},
        },
    }
    (store.root / f"{receipt.hex}.bin").write_bytes(PDF.replace(b"signed", b"falsed"))
    with pytest.raises(EvidenceFileError, match="integrity"):
        verify_native_regular_files(source, store=store)


@pytest.mark.parametrize("changed", ["original", "bundle", "borrower", "debit"])
def test_renewal_lineage_requires_original_and_current_private_bytes(tmp_path, changed):
    store = PrivateEvidenceStore(tmp_path / "private-lineage")
    keys = {name: uuid4() for name in ("original", "bundle", "borrower", "debit")}
    proofs = {
        name: {
            "id": str(key),
            "sha256": store.put(key, PDF, "application/pdf"),
            "byte_count": len(PDF),
        }
        for name, key in keys.items()
    }
    original = {
        "origin_kind": "native_payout",
        "snapshot": {
            "packet_document": {
                "storage_key": str(keys["original"]),
                "content_sha256": proofs["original"]["sha256"],
                "byte_count": len(PDF),
            },
            "debit_preparation": {"snapshot": {}},
            "completion_preparation": {"snapshot": {}},
        },
    }
    renewal = {
        "origin_kind": "native_renewal",
        "snapshot": {
            "review": {
                "source_snapshot": {
                    "boundary": {"rollforward": {"native_origin": original}},
                    "borrower_evidence": proofs["borrower"],
                    "payout_debit_origin": {"evidence": proofs["debit"]},
                },
                "reviewed_measurement": {"evidence": proofs["bundle"]},
            }
        },
    }
    verify_native_regular_files(renewal, store=store)
    (store.root / f"{keys[changed].hex}.bin").write_bytes(b"replaced proof bytes")
    with pytest.raises(EvidenceFileError, match="integrity"):
        verify_native_regular_files(renewal, store=store)

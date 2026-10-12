"""Verify private bytes supporting an exact native accounting asset lineage."""

from uuid import UUID

from .office_review_evidence_storage import PrivateEvidenceStore


def verify_native_regular_files(origin, *, store=None):
    if not origin or origin.get("origin_kind") not in {
        "native_payout",
        "native_renewal",
    }:
        return
    snapshot = origin["snapshot"]
    store = store or PrivateEvidenceStore()
    if origin["origin_kind"] == "native_renewal":
        review = snapshot["review"]
        source = review["source_snapshot"]
        verify_native_regular_files(
            source["boundary"]["rollforward"]["native_origin"], store=store
        )
        # The explicitly reviewed signed-contract/measurement bundle is bound
        # to the exact renewal schedule, not inferred from signer timestamps.
        for evidence in (
            review["reviewed_measurement"]["evidence"],
            source["borrower_evidence"],
            source["payout_debit_origin"]["evidence"],
        ):
            store.read(
                UUID(str(evidence["id"])), evidence["sha256"], evidence["byte_count"]
            )
        return
    document = snapshot["packet_document"]
    store.read(
        UUID(str(document["storage_key"])),
        document["content_sha256"],
        document["byte_count"],
    )
    seen = set()
    for stage in ("debit_preparation", "completion_preparation"):
        source = snapshot[stage]["snapshot"]
        for name in ("evidence", "borrower_evidence"):
            evidence = source.get(name)
            if evidence and evidence["id"] not in seen:
                store.read(
                    UUID(str(evidence["id"])),
                    evidence["sha256"],
                    evidence["byte_count"],
                )
                seen.add(evidence["id"])
        office = source.get("office_evidence")
        if office:
            store.read(
                UUID(str(office["request_id"])),
                office["content_sha256"],
                office["byte_count"],
            )

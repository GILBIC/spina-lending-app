from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

from .regular_cross_period_posting_ready_evidence import (
    REGULAR_CROSS_PERIOD_POSTING_READY_EVIDENCE_POLICY_VERSION,
    RegularCrossPeriodPostingReadyEvidenceBundle,
    RegularCrossPeriodPostingReadyEntryEvidence,
)

REGULAR_JOURNAL_DRAFT_POLICY_VERSION = "regular_journal_draft_v1"


class RegularJournalDraftEvidenceError(ValueError):
    pass


def _money(value: Decimal) -> str:
    return format(value, ".2f")


def _line_evidence(line) -> dict[str, Any]:
    return {
        "line_order": line.line_order,
        "account_system_key": line.account_system_key,
        "side": line.side,
        "amount": _money(line.amount),
        "label": line.label,
    }


def _entry_evidence(
    entry: RegularCrossPeriodPostingReadyEntryEvidence,
) -> dict[str, Any]:
    return {
        "sequence_order": entry.sequence_order,
        "entry_type": entry.entry_type,
        "bundle_entry_key": entry.bundle_entry_key,
        "sequence_preview_entry_key": entry.sequence_preview_entry_key,
        "coordinate_preview_key": entry.coordinate_preview_key,
        "identity_preview_key": entry.identity_preview_key,
        "upstream_related_source_event_key": entry.upstream_related_source_event_key,
        "source_type": entry.source_type,
        "source_reference": entry.source_reference,
        "source_event_key": entry.source_event_key,
        "related_collection_source_event_key": (
            entry.related_collection_source_event_key
        ),
        "recognition_date": entry.recognition_date.isoformat(),
        "proposed_posting_date": entry.proposed_posting_date.isoformat(),
        "amount": _money(entry.amount),
        "fiscal_period_id": str(entry.fiscal_period_id),
        "fiscal_period_label": entry.fiscal_period_label,
        "fiscal_period_start_date": entry.fiscal_period_start_date.isoformat(),
        "fiscal_period_end_date": entry.fiscal_period_end_date.isoformat(),
        "fiscal_period_status": entry.fiscal_period_status,
        "journal_lines": [_line_evidence(line) for line in entry.journal_lines],
        "total_debit": _money(entry.total_debit),
        "total_credit": _money(entry.total_credit),
        "balanced": entry.balanced,
        "posting_eligible": entry.posting_eligible,
    }


def _validated_entries(
    bundle: RegularCrossPeriodPostingReadyEvidenceBundle,
) -> tuple[RegularCrossPeriodPostingReadyEntryEvidence, ...]:
    if (
        bundle.bundle_policy_version
        != REGULAR_CROSS_PERIOD_POSTING_READY_EVIDENCE_POLICY_VERSION
        or bundle.disposition
        != "regular_cross_period_posting_ready_evidence_complete"
        or bundle.blocker_code is not None
        or bundle.posting_eligible
        or bundle.automatic_source_posting_enabled
        or not bundle.posting_coordinate_ready
        or not bundle.posting_identity_ready
        or not bundle.posting_ready_evidence_complete
        or not bundle.ordered_entries
        or bundle.ordered_entries[-1].entry_type != "collection"
    ):
        raise RegularJournalDraftEvidenceError(
            "Protected posting-ready evidence is not exact and complete."
        )

    entries = bundle.ordered_entries
    if [entry.sequence_order for entry in entries] != list(
        range(1, len(entries) + 1)
    ):
        raise RegularJournalDraftEvidenceError(
            "Protected posting-ready entries are not contiguous and ordered."
        )

    source_keys = [entry.source_event_key for entry in entries]
    bundle_keys = [entry.bundle_entry_key for entry in entries]
    if (
        len(set(source_keys)) != len(source_keys)
        or len(set(bundle_keys)) != len(bundle_keys)
        or sum(entry.entry_type == "collection" for entry in entries) != 1
        or any(
            entry.posting_eligible
            or not entry.balanced
            or entry.amount <= Decimal("0")
            or entry.total_debit != entry.amount
            or entry.total_credit != entry.amount
            or entry.fiscal_period_status != "open"
            or not entry.journal_lines
            for entry in entries
        )
    ):
        raise RegularJournalDraftEvidenceError(
            "Protected posting-ready entry evidence is not exact."
        )

    zero_cent_ids = set(bundle.zero_cent_fiscal_period_ids)
    if any(
        entry.entry_type == "eir_accrual_period"
        and entry.fiscal_period_id in zero_cent_ids
        for entry in entries
    ):
        raise RegularJournalDraftEvidenceError(
            "Zero-cent fiscal periods cannot receive journal draft entries."
        )
    return entries


def regular_journal_draft_review_fingerprint(
    bundle: RegularCrossPeriodPostingReadyEvidenceBundle,
) -> str:
    entries = _validated_entries(bundle)
    evidence = {
        "draft_policy_version": REGULAR_JOURNAL_DRAFT_POLICY_VERSION,
        "transaction_id": str(bundle.transaction_id),
        "collection_source_event_key": bundle.collection_source_event_key,
        "sequence_policy_version": bundle.sequence_policy_version,
        "coordinate_policy_version": bundle.coordinate_policy_version,
        "identity_policy_version": bundle.identity_policy_version,
        "bundle_policy_version": bundle.bundle_policy_version,
        "disposition": bundle.disposition,
        "blocker_code": bundle.blocker_code,
        "posting_eligible": bundle.posting_eligible,
        "automatic_source_posting_enabled": (
            bundle.automatic_source_posting_enabled
        ),
        "posting_coordinate_ready": bundle.posting_coordinate_ready,
        "posting_identity_ready": bundle.posting_identity_ready,
        "posting_ready_evidence_complete": bundle.posting_ready_evidence_complete,
        "ordered_entries": [_entry_evidence(entry) for entry in entries],
        "zero_cent_fiscal_period_ids": [
            str(period_id) for period_id in bundle.zero_cent_fiscal_period_ids
        ],
    }
    encoded = json.dumps(
        evidence,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def regular_journal_draft_entries(
    bundle: RegularCrossPeriodPostingReadyEvidenceBundle,
) -> list[dict[str, Any]]:
    entries = _validated_entries(bundle)
    return [
        {
            "sequence_order": entry.sequence_order,
            "entry_type": entry.entry_type,
            "bundle_entry_key": entry.bundle_entry_key,
            "source_type": entry.source_type,
            "source_reference": entry.source_reference,
            "source_event_key": entry.source_event_key,
            "related_collection_source_event_key": (
                entry.related_collection_source_event_key
            ),
            "posting_date": entry.proposed_posting_date.isoformat(),
            "amount": _money(entry.amount),
            "fiscal_period_id": str(entry.fiscal_period_id),
            "fiscal_period_label": entry.fiscal_period_label,
            "fiscal_period_start_date": entry.fiscal_period_start_date.isoformat(),
            "fiscal_period_end_date": entry.fiscal_period_end_date.isoformat(),
            "fiscal_period_status": entry.fiscal_period_status,
            "journal_lines": [_line_evidence(line) for line in entry.journal_lines],
            "total_debit": _money(entry.total_debit),
            "total_credit": _money(entry.total_credit),
            "balanced": entry.balanced,
        }
        for entry in entries
    ]


def regular_journal_draft_review_set_fingerprint(
    bundles: tuple[RegularCrossPeriodPostingReadyEvidenceBundle, ...],
) -> str:
    if not bundles:
        raise RegularJournalDraftEvidenceError(
            "At least one protected posting-ready bundle is required."
        )
    fingerprints = [
        {
            "transaction_id": str(bundle.transaction_id),
            "bundle_fingerprint": regular_journal_draft_review_fingerprint(bundle),
        }
        for bundle in bundles
    ]
    transaction_ids = [item["transaction_id"] for item in fingerprints]
    if len(set(transaction_ids)) != len(transaction_ids):
        raise RegularJournalDraftEvidenceError(
            "Protected posting-ready review set contains duplicate transactions."
        )
    evidence = {
        "draft_policy_version": REGULAR_JOURNAL_DRAFT_POLICY_VERSION,
        "bundle_policy_version": (
            REGULAR_CROSS_PERIOD_POSTING_READY_EVIDENCE_POLICY_VERSION
        ),
        "bundles": fingerprints,
    }
    encoded = json.dumps(
        evidence,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

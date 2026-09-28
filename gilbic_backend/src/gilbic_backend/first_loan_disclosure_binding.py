"""Task 4 binding guards; the owning approval transaction must call them.

These helpers do not authenticate callers, create approvals, or activate a route.
Call the database helpers only after the existing persisted actor/device check,
using the SAME transaction as the proposed approval or new lifecycle action.
Historical retries compare immutable identities separately from new-action checks.
"""

from contextlib import contextmanager
from copy import deepcopy
from decimal import Context, localcontext
from uuid import UUID


class DisclosureBindingError(ValueError):
    """A missing or malformed immutable source pair, not a financial decision."""


def source_pair(calculation_id, expected_digest):
    if not isinstance(calculation_id, (str, UUID)) or not isinstance(
        expected_digest, str
    ):
        raise DisclosureBindingError("The saved disclosure ID and digest are required.")
    try:
        identity = str(UUID(str(calculation_id)))
    except ValueError as error:
        raise DisclosureBindingError(
            "The saved disclosure ID and digest are required."
        ) from error
    if len(expected_digest) != 64 or any(
        character not in "0123456789abcdef" for character in expected_digest
    ):
        raise DisclosureBindingError("The saved disclosure ID and digest are required.")
    return identity, expected_digest


def retry_matches(packet, calculation_id, expected_digest):
    """Identity comparison only; authorize and verify the packet hash first."""
    if not isinstance(packet, dict) or type(packet.get("schema_version")) is not int:
        return False
    version = packet["schema_version"]
    if version == 1 and "tax_disclosure" not in packet:
        return calculation_id is None and expected_digest is None
    binding = packet.get("tax_disclosure")
    if (
        version != 2
        or not isinstance(binding, dict)
        or set(binding) != {"calculation_id", "review_digest", "financial_snapshot"}
        or not isinstance(binding["financial_snapshot"], dict)
    ):
        return False
    try:
        identity, digest = source_pair(calculation_id, expected_digest)
    except DisclosureBindingError:
        return False
    return binding["calculation_id"] == identity and binding["review_digest"] == digest


@contextmanager
def _bounded_binding(cursor):
    # Lazy imports let the existing owner delegate without circular imports.
    from . import first_loan_disclosure_repository as reviews
    from .office_review_evidence_storage import EvidenceFileError

    conflict = reviews._owner().FirstLoanConflict
    try:
        isolation = cursor.execute("show transaction_isolation").fetchone()
        if isolation is None or isolation["transaction_isolation"] != "read committed":
            raise conflict("Disclosure binding requires a READ COMMITTED transaction.")
        cursor.execute("set local lock_timeout = '2s'")
        yield
    except (
        reviews.errors.LockNotAvailable,
        reviews.errors.DeadlockDetected,
        reviews.errors.SerializationFailure,
    ) as error:
        raise conflict(
            "The disclosure source is changing. Retry the same request."
        ) from error
    except EvidenceFileError as error:
        raise conflict(
            "The retained calculation support is unavailable or invalid."
        ) from error


def require_for_approval(
    cursor,
    *,
    calculation_id,
    expected_digest,
    application_version_id,
    terms,
    rows,
):
    """Return a safe binding under the caller's already-authorized transaction.

    Reuse the source service's rule-table SHARE and application/Client locks.
    Check the latest review AFTER those locks: readback's advisory readiness
    alone is not authority to consume a review during concurrent supersession.
    """
    from . import first_loan_disclosure_repository as reviews
    from .first_loan_disclosure import (
        parse_components,
        public_financial_snapshot,
        require_component_compatibility,
    )
    from .first_loan_terms import schedule_payload

    conflict = reviews._owner().FirstLoanConflict
    try:
        identity, digest = source_pair(calculation_id, expected_digest)
    except DisclosureBindingError as error:
        raise conflict(str(error)) from error
    terms = reviews._terms(terms)
    with _bounded_binding(cursor):
        review = reviews._load_review(cursor, UUID(identity), application_version_id)
        if review["review_digest"] != digest or review["input_snapshot"][
            "terms"
        ] != terms.model_dump(mode="json"):
            raise conflict("The saved disclosure differs from the proposed approval.")
        context = reviews.review_context(
            cursor,
            application_version_id=review["application_version_id"],
            cif_version_id=review["cif_version_id"],
            terms=terms,
            dst_rule_id=review["dst_rule_id"],
            grt_rule_id=review["grt_rule_id"],
        )
        latest = cursor.execute(
            "select id from lending.first_loan_disclosure_calculations "
            "where application_id = %s order by version_number desc limit 1",
            (review["application_id"],),
        ).fetchone()
        if (
            latest is None
            or latest["id"] != review["id"]
            or context["context_digest"]
            != review["input_snapshot"]["expected_context_digest"]
        ):
            raise conflict("The saved disclosure source changed. Obtain a new review.")
        try:
            components = parse_components(review["review_snapshot"]["components"])
            checked_rows = tuple(rows)
            require_component_compatibility(terms, checked_rows, components)
            if review["source_snapshot"]["schedule"] != schedule_payload(checked_rows):
                raise ValueError("The retained schedule differs.")
        except (KeyError, TypeError, ValueError) as error:
            raise conflict(
                "The disclosed components do not match the supported schedule."
            ) from error
        reviews._support_bytes(review)
        # Recheck time-sensitive validity after private-file I/O. Source and
        # rule locks remain held by the same owning transaction throughout.
        if (
            reviews.review_context(
                cursor,
                application_version_id=review["application_version_id"],
                cif_version_id=review["cif_version_id"],
                terms=terms,
                dst_rule_id=review["dst_rule_id"],
                grt_rule_id=review["grt_rule_id"],
            )
            != context
        ):
            raise conflict("The disclosure source changed while checking its support.")
        financial = public_financial_snapshot(review["review_snapshot"])
        if any(
            financial["disclosure_values"][name] is None
            for name in (
                "amount_financed",
                "finance_charge_total",
                "non_finance_charge_total",
                "effective_interest_rate",
            )
        ):
            raise conflict("The saved disclosure is missing required reviewed values.")
        return {
            "calculation_id": identity,
            "review_digest": digest,
            "financial_snapshot": deepcopy(financial),
        }


def require_packet_source(cursor, *, row):
    """Reject a new action on an unbound or changed packet; never rewrite it."""
    from . import first_loan_disclosure_repository as reviews
    from .first_loan_terms import (
        generate_first_loan_schedule,
        schedule_payload,
        snapshot_digest,
    )

    conflict = reviews._owner().FirstLoanConflict
    packet = row["packet"]
    if not isinstance(packet, dict) or packet.get("schema_version") != 2:
        raise conflict(
            "A reviewed disclosure is required. Obtain a revised approval before a new action."
        )
    binding = packet.get("tax_disclosure")
    if (
        type(packet["schema_version"]) is not int
        or not isinstance(binding, dict)
        or not retry_matches(
            packet, binding.get("calculation_id"), binding.get("review_digest")
        )
        or snapshot_digest(packet) != row["packet_hash"]
    ):
        raise conflict("The packet requires its exact saved disclosure binding.")
    try:
        if any(
            packet[field] != str(row[field])
            for field in ("loan_id", "client_id", "cif_version_id")
        ) or (
            packet["packet_id"] != str(row["id"])
            or packet["application"]["id"] != str(row["application_version_id"])
        ):
            raise ValueError("Packet coordinates differ.")
        terms = reviews._terms(packet["terms"])
        with localcontext(Context(prec=40)):
            rows = tuple(generate_first_loan_schedule(terms))
        if packet["schedule"] != schedule_payload(rows):
            raise ValueError("The packet schedule differs.")
    except (KeyError, TypeError, ValueError) as error:
        raise conflict(
            "The packet source or schedule differs from its approval."
        ) from error
    expected = require_for_approval(
        cursor,
        calculation_id=binding["calculation_id"],
        expected_digest=binding["review_digest"],
        application_version_id=row["application_version_id"],
        terms=terms,
        rows=rows,
    )
    if binding != expected:
        raise conflict("The packet financial snapshot differs from its saved review.")
    return expected

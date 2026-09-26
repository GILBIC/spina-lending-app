"""Protected pre-release reviews, not loan approval or tax-accounting events.

Reuse the existing source guards, exact values and private file store. No route
is activated here. Historical results remain immutable; current blockers are
readback metadata, never permission to repeat a financial transition.
"""

from __future__ import annotations

import base64
import hashlib
from contextlib import contextmanager
from copy import deepcopy
from datetime import date
from decimal import Context, Decimal, localcontext
from uuid import UUID, uuid4, uuid5
from zoneinfo import ZoneInfo

from psycopg import errors
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .database import open_connection
from .first_loan_disclosure import (
    DisclosureReviewRequest,
    canonical_review_digest,
    project_components,
    public_financial_snapshot,
    require_component_compatibility,
)
from .first_loan_terms import (
    FirstLoanTerms,
    generate_first_loan_schedule,
    schedule_payload,
    snapshot_digest,
)
from .office_review_evidence_storage import (
    EvidenceFileError,
    PrivateEvidenceStore,
    validate_evidence_content,
)

MANILA = ZoneInfo("Asia/Manila")
AUDIT_ACTION = "lending.first_loan.disclosure_reviewed"


def _owner():
    # The owning first-loan repository can delegate here without an import cycle.
    from . import first_loan_repository

    return first_loan_repository


def _json_value(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise _owner().FirstLoanConflict("The saved source is invalid.")
        return format(value, "f")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    raise _owner().FirstLoanConflict("The saved source requires exact values.")


def _terms(value):
    with localcontext(Context(prec=40)):
        if isinstance(value, FirstLoanTerms):
            value = value.model_dump(mode="python", warnings=False)
        return FirstLoanTerms.model_validate(value)


@contextmanager
def _transaction(actor_user_id, registered_device_id, *, management=True):
    owner = _owner()
    try:
        with (
            open_connection() as connection,
            connection.transaction(),
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            isolation = cursor.execute("show transaction_isolation").fetchone()
            if (
                isolation is None
                or isolation["transaction_isolation"] != "read committed"
            ):
                raise owner.FirstLoanConflict(
                    "Disclosure review requires a READ COMMITTED transaction."
                )
            cursor.execute("set local lock_timeout = '2s'")
            owner._actor(
                cursor,
                actor_user_id,
                registered_device_id,
                owner.APPROVE_PERMISSION if management else owner.REVIEW_PERMISSION,
                management=management,
            )
            yield cursor
    except (
        errors.LockNotAvailable,
        errors.DeadlockDetected,
        errors.SerializationFailure,
    ) as error:
        raise owner.FirstLoanConflict(
            "The disclosure source is changing. Retry the same request."
        ) from error
    except (
        errors.UniqueViolation,
        errors.CheckViolation,
        errors.ForeignKeyViolation,
    ) as error:
        raise owner.FirstLoanConflict(
            "The disclosure request conflicts with its saved source."
        ) from error
    except EvidenceFileError as error:
        raise owner.FirstLoanConflict(
            "The retained calculation support is unavailable or invalid."
        ) from error


def _clock(cursor):
    now = cursor.execute("select clock_timestamp() as t").fetchone()["t"]
    return now, now.astimezone(MANILA).date()


def _rules(cursor, terms, rows, dst_rule_id, grt_rule_id):
    result = {}
    maturity = (rows[-1].due_date - terms.schedule_basis_date).days
    for kind, rule_id, tax_type, start, end in (
        (
            "dst",
            dst_rule_id,
            "documentary_stamp_tax",
            terms.schedule_basis_date,
            terms.schedule_basis_date,
        ),
        (
            "grt",
            grt_rule_id,
            "percentage_tax_lending",
            rows[0].due_date,
            rows[-1].due_date,
        ),
    ):
        rule = cursor.execute(
            "select * from accounting.v1_tax_rule_evidence where id = %s",
            (rule_id,),
        ).fetchone()
        if (
            rule is None
            or rule["tax_type"] != tax_type
            or rule["effective_from"] > start
            or (rule["effective_to"] is not None and rule["effective_to"] < end)
            or (
                rule["maturity_max_days"] is not None
                and maturity > rule["maturity_max_days"]
            )
        ):
            raise _owner().FirstLoanConflict(
                "The selected tax rule does not cover the proposed date and term."
            )
        later = cursor.execute(
            "select 1 from accounting.v1_tax_rule_evidence "
            "where tax_type = %s and rule_key = %s and rule_version > %s "
            "and effective_from <= %s "
            "and (effective_to is null or effective_to >= %s) "
            "and (maturity_max_days is null or maturity_max_days >= %s) limit 1",
            (tax_type, rule["rule_key"], rule["rule_version"], end, start, maturity),
        ).fetchone()
        if later is not None:
            raise _owner().FirstLoanConflict(
                "The selected tax rule is superseded for the proposed schedule."
            )
        result[kind] = _json_value(rule)
    return result


def review_context(
    cursor, *, application_version_id, cif_version_id, terms, dst_rule_id, grt_rule_id
):
    """Internal: the caller must hold the authorized transaction boundary."""
    from .client_cif_identity_information import cif_information_from_row

    terms = _terms(terms)
    with localcontext(Context(prec=40)):
        rows = tuple(generate_first_loan_schedule(terms))
    # The existing rule writer takes ROW EXCLUSIVE when inserting. SHARE stops
    # new-version phantoms, unlike a lock on only the selected old rule row.
    cursor.execute("lock table accounting.v1_tax_rule_evidence in share mode")
    app, cif, client, privacy = _owner()._source(cursor, application_version_id)
    now, business_date = _clock(cursor)
    if (
        str(cif["id"]) != str(cif_version_id)
        or cif["activated_at"] > now
        or cif["expires_at"] <= now
        or terms.schedule_basis_date < business_date
    ):
        raise _owner().FirstLoanConflict(
            "The proposed disclosure requires a current source and date basis."
        )
    product = cursor.execute(
        "select id, code, calculation_mode, daily_interest_per_1000 "
        "from lending.loan_types where id = %s and is_active for share",
        (terms.loan_type_id,),
    ).fetchone()
    allowed = (
        {"seven_by_seven"}
        if terms.product_code == "seven_by_seven"
        else {"fixed_daily", "fixed_total"}
    )
    if product is None or product["calculation_mode"] not in allowed:
        raise _owner().FirstLoanConflict("The proposed loan product is unavailable.")
    if (
        terms.product_code == "seven_by_seven"
        and product["daily_interest_per_1000"] != terms.daily_interest_per_1000
    ):
        raise _owner().FirstLoanConflict("The proposed product pricing has changed.")
    source = {
        "application_id": str(app["application_id"]),
        "application_version_id": str(app["id"]),
        "application_version_number": app["version_number"],
        "client_id": str(client["id"]),
        "cif_version_id": str(cif["id"]),
        "cif_version_number": cif["version_number"],
        "application_digest": snapshot_digest(app["information"]),
        "cif_digest": snapshot_digest(cif_information_from_row(cif)),
        "privacy_id": str(privacy["id"]),
        "privacy_digest": snapshot_digest(privacy["review_snapshot"]),
        "business_date": business_date.isoformat(),
        "currency": "PHP",
        "terms": terms.model_dump(mode="json"),
        "schedule": schedule_payload(rows),
        "product": _json_value(product),
    }
    rules = _rules(cursor, terms, rows, dst_rule_id, grt_rule_id)
    context = {"source": source, "rules": rules}
    return {**context, "context_digest": canonical_review_digest(context)}


def _context_for_request(cursor, request):
    return review_context(
        cursor,
        application_version_id=request.application_version_id,
        cif_version_id=request.cif_version_id,
        terms=request.terms,
        dst_rule_id=request.dst_rule_id,
        grt_rule_id=request.grt_rule_id,
    )


def _request_digest(inputs, support_sha256, actor_user_id, registered_device_id):
    return canonical_review_digest(
        {
            "input": inputs,
            "support_sha256": support_sha256,
            "actor_user_id": str(actor_user_id),
            "registered_device_id": str(registered_device_id),
        }
    )


def _review_envelope(row):
    # Database review time is immutable and database-owned, not caller-hashed.
    return {
        key: row[key]
        for key in (
            "id",
            "schema_version",
            "request_id",
            "application_id",
            "application_version_id",
            "client_id",
            "cif_version_id",
            "version_number",
            "supersedes_calculation_id",
            "dst_rule_id",
            "grt_rule_id",
            "request_digest",
            "input_snapshot",
            "source_snapshot",
            "rule_snapshot",
            "review_snapshot",
            "support_storage_key",
            "support_sha256",
            "support_media_type",
            "support_byte_count",
            "reviewed_by_user_id",
            "reviewed_device_id",
        )
    }


def _load_review(cursor, calculation_id, application_version_id=None):
    row = cursor.execute(
        "select * from lending.first_loan_disclosure_calculations where id = %s",
        (calculation_id,),
    ).fetchone()
    if row is None or (
        application_version_id is not None
        and str(row["application_version_id"]) != str(application_version_id)
    ):
        raise _owner().FirstLoanConflict("The disclosure record is unavailable.")
    _verify_review(row)
    return row


def _verify_review(row):
    try:
        valid = (
            row["schema_version"] == 1
            and canonical_review_digest(_review_envelope(row)) == row["review_digest"]
            and row["review_snapshot"] == row["input_snapshot"]
            and row["input_snapshot"]["terms"] == row["source_snapshot"]["terms"]
            and _request_digest(
                row["input_snapshot"],
                row["support_sha256"],
                row["reviewed_by_user_id"],
                row["reviewed_device_id"],
            )
            == row["request_digest"]
            and canonical_review_digest(
                {"source": row["source_snapshot"], "rules": row["rule_snapshot"]}
            )
            == row["input_snapshot"]["expected_context_digest"]
        )
        if not valid:
            raise ValueError("Review digest mismatch")
        public_financial_snapshot(row["review_snapshot"])
    except (KeyError, ValueError, TypeError) as error:
        raise _owner().FirstLoanConflict(
            "The saved disclosure failed its integrity check."
        ) from error


def _support_bytes(row):
    content = PrivateEvidenceStore().read(
        row["support_storage_key"], row["support_sha256"], row["support_byte_count"]
    )
    validate_evidence_content(content, row["support_media_type"])
    return content


def _component_blockers(request):
    with localcontext(Context(prec=40)):
        rows = tuple(generate_first_loan_schedule(request.terms))
        total = sum((row.contractual_amount for row in rows), Decimal("0.00"))
        if total != request.components.total_scheduled_payable:
            raise _owner().FirstLoanConflict(
                "The reviewed total differs from the agreed schedule."
            )
        if (
            request.components.grt_in_repayments != 0
            or request.components.other_scheduled_charges != 0
        ):
            return ["component_integration_required"]
        try:
            require_component_compatibility(request.terms, rows, request.components)
        except ValueError as error:
            raise _owner().FirstLoanConflict(
                "The reviewed components differ from the agreed schedule."
            ) from error
    return []


def _public(cursor, row):
    _verify_review(row)
    inputs = row["input_snapshot"]
    financial = public_financial_snapshot(row["review_snapshot"])
    blockers = [
        f"missing_{name}"
        for name in (
            "amount_financed",
            "finance_charge_total",
            "non_finance_charge_total",
            "effective_interest_rate",
        )
        if financial["disclosure_values"][name] is None
    ]
    if (
        Decimal(financial["components"]["grt_in_repayments"]) != 0
        or Decimal(financial["components"]["other_scheduled_charges"]) != 0
    ):
        blockers.append("component_integration_required")
    newer = cursor.execute(
        "select 1 from lending.first_loan_disclosure_calculations "
        "where application_id = %s and version_number > %s limit 1",
        (row["application_id"], row["version_number"]),
    ).fetchone()
    if newer is not None:
        blockers.append("calculation_superseded")
    try:
        _support_bytes(row)
    except EvidenceFileError:
        blockers.append("support_unavailable")
    try:
        # A stale historical source must not poison the readback transaction.
        with cursor.connection.transaction():
            context = review_context(
                cursor,
                application_version_id=row["application_version_id"],
                cif_version_id=row["cif_version_id"],
                terms=inputs["terms"],
                dst_rule_id=row["dst_rule_id"],
                grt_rule_id=row["grt_rule_id"],
            )
            if context["context_digest"] != inputs["expected_context_digest"]:
                blockers.append("source_context_changed")
    except (_owner().FirstLoanConflict, EvidenceFileError):
        blockers.append("source_context_changed")
    except (errors.LockNotAvailable, errors.DeadlockDetected):
        blockers.append("source_context_busy")
    return {
        "id": str(row["id"]),
        "review_digest": row["review_digest"],
        "version_number": row["version_number"],
        "application_version_id": str(row["application_version_id"]),
        "cif_version_id": str(row["cif_version_id"]),
        "financial_snapshot": financial,
        "reviewed_at": row["reviewed_at"].isoformat(),
        "approval_ready": not blockers,
        "blockers": blockers,
    }


def record_review(cursor, *, actor_user_id, registered_device_id, request):
    """Internal write; caller owns the authenticated transaction and rollback."""
    request = DisclosureReviewRequest.model_validate(request)
    support = base64.b64decode(request.support_base64, validate=True)
    validate_evidence_content(support, request.support_media_type)
    inputs = request.model_dump(mode="json", exclude={"support_base64"})
    support_hash = hashlib.sha256(support).hexdigest()
    request_hash = _request_digest(
        inputs, support_hash, actor_user_id, registered_device_id
    )
    cursor.execute(
        "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
        (f"spina.r1.review:{request.request_id}",),
    )
    existing = cursor.execute(
        "select * from lending.first_loan_disclosure_calculations "
        "where request_id = %s",
        (request.request_id,),
    ).fetchone()
    if existing is not None:
        if existing["request_digest"] != request_hash:
            raise _owner().FirstLoanConflict(
                "The review request identity is already used with different inputs."
            )
        _verify_review(existing)
        if _support_bytes(existing) != support:
            raise _owner().FirstLoanConflict("The retained support differs.")
        return _public(cursor, existing)

    context = _context_for_request(cursor, request)
    if context["context_digest"] != request.expected_context_digest:
        raise _owner().FirstLoanConflict("Reload the current disclosure context.")
    prior = cursor.execute(
        "select id, version_number from lending.first_loan_disclosure_calculations "
        "where application_id = %s order by version_number desc limit 1",
        (context["source"]["application_id"],),
    ).fetchone()
    expected_prior = None if prior is None else prior["id"]
    if request.supersedes_calculation_id != expected_prior:
        raise _owner().FirstLoanConflict(
            "A new review must name the current application review."
        )
    version = 1 if prior is None else prior["version_number"] + 1
    if version > 2147483647:
        raise _owner().FirstLoanConflict("The review version limit was reached.")
    _component_blockers(request)
    calculation_id = uuid4()
    version_reference = (
        f"application-version:{request.application_version_id}:"
        f"context:{request.expected_context_digest}"
    )
    projected = project_components(
        request.components,
        references={
            "loan_version_reference": version_reference,
            "tax_loan_version_reference": version_reference,
            "tax_rule_snapshot_reference": canonical_review_digest(context["rules"]),
            "tax_calculation_reference": str(calculation_id),
        },
    )
    if projected != request.components.model_dump(mode="json"):
        raise _owner().FirstLoanConflict("The disclosure projection differs.")
    storage_key = uuid5(request.request_id, "spina.r1.support.v1")
    store = PrivateEvidenceStore()
    stored_hash = store.put(storage_key, support, request.support_media_type)
    if (
        stored_hash != support_hash
        or store.read(storage_key, support_hash, len(support)) != support
    ):
        raise _owner().FirstLoanConflict("The retained support differs.")
    # Recheck wall-clock/source after bounded private-file I/O. A failed commit
    # leaves only an unreferenced immutable staged file for an exact retry.
    if _context_for_request(cursor, request) != context:
        raise _owner().FirstLoanConflict("The disclosure context changed.")
    source = context["source"]
    record = {
        "id": calculation_id,
        "schema_version": 1,
        "request_id": request.request_id,
        "application_id": UUID(source["application_id"]),
        "application_version_id": request.application_version_id,
        "client_id": UUID(source["client_id"]),
        "cif_version_id": request.cif_version_id,
        "version_number": version,
        "supersedes_calculation_id": request.supersedes_calculation_id,
        "dst_rule_id": request.dst_rule_id,
        "grt_rule_id": request.grt_rule_id,
        "request_digest": request_hash,
        "input_snapshot": inputs,
        "source_snapshot": source,
        "rule_snapshot": context["rules"],
        "review_snapshot": deepcopy(inputs),
        "support_storage_key": storage_key,
        "support_sha256": support_hash,
        "support_media_type": request.support_media_type,
        "support_byte_count": len(support),
        "reviewed_by_user_id": actor_user_id,
        "reviewed_device_id": registered_device_id,
    }
    record["review_digest"] = canonical_review_digest(_review_envelope(record))
    parameters = dict(record)
    for name in (
        "input_snapshot",
        "source_snapshot",
        "rule_snapshot",
        "review_snapshot",
    ):
        parameters[name] = Jsonb(record[name])
    saved = cursor.execute(
        """
        insert into lending.first_loan_disclosure_calculations (
            id, schema_version, request_id, application_id, application_version_id,
            client_id, cif_version_id, version_number, supersedes_calculation_id,
            dst_rule_id, grt_rule_id, request_digest, review_digest, input_snapshot,
            source_snapshot, rule_snapshot, review_snapshot, support_storage_key,
            support_sha256, support_media_type, support_byte_count,
            reviewed_by_user_id, reviewed_device_id
        ) values (
            %(id)s, %(schema_version)s, %(request_id)s, %(application_id)s,
            %(application_version_id)s, %(client_id)s, %(cif_version_id)s,
            %(version_number)s, %(supersedes_calculation_id)s, %(dst_rule_id)s,
            %(grt_rule_id)s, %(request_digest)s, %(review_digest)s, %(input_snapshot)s,
            %(source_snapshot)s, %(rule_snapshot)s, %(review_snapshot)s,
            %(support_storage_key)s, %(support_sha256)s, %(support_media_type)s,
            %(support_byte_count)s, %(reviewed_by_user_id)s, %(reviewed_device_id)s
        ) returning *
        """,
        parameters,
    ).fetchone()
    cursor.execute(
        "insert into core.audit_logs "
        "(actor_user_id, action, target_type, target_id, details) "
        "values (%s, %s, 'first_loan_disclosure_calculation', %s, %s)",
        (
            actor_user_id,
            AUDIT_ACTION,
            saved["id"],
            Jsonb(
                {
                    "review_digest": saved["review_digest"],
                    "version_number": version,
                    "context_digest": request.expected_context_digest,
                    "registered_device_id": str(registered_device_id),
                }
            ),
        ),
    )
    return _public(cursor, saved)


class PostgresFirstLoanDisclosureRepository:
    """Small transaction facade; reuse its cursor helpers in the owning flow."""

    def context(
        self,
        *,
        actor_user_id,
        registered_device_id,
        application_version_id,
        cif_version_id,
        terms,
        dst_rule_id,
        grt_rule_id,
    ):
        with _transaction(actor_user_id, registered_device_id) as cursor:
            return review_context(
                cursor,
                application_version_id=application_version_id,
                cif_version_id=cif_version_id,
                terms=terms,
                dst_rule_id=dst_rule_id,
                grt_rule_id=grt_rule_id,
            )

    def record(self, *, actor_user_id, registered_device_id, request):
        with _transaction(actor_user_id, registered_device_id) as cursor:
            return record_review(
                cursor,
                actor_user_id=actor_user_id,
                registered_device_id=registered_device_id,
                request=request,
            )

    def get(
        self,
        *,
        actor_user_id,
        registered_device_id,
        calculation_id,
        application_version_id=None,
    ):
        with _transaction(
            actor_user_id, registered_device_id, management=False
        ) as cursor:
            row = _load_review(cursor, calculation_id, application_version_id)
            return _public(cursor, row)

    def by_request(self, *, actor_user_id, registered_device_id, request_id):
        with _transaction(actor_user_id, registered_device_id) as cursor:
            row = cursor.execute(
                "select * from lending.first_loan_disclosure_calculations "
                "where request_id = %s and reviewed_by_user_id = %s",
                (request_id, actor_user_id),
            ).fetchone()
            if row is None:
                raise _owner().FirstLoanConflict(
                    "The disclosure record is unavailable."
                )
            return _public(cursor, row)

    def support(
        self,
        *,
        actor_user_id,
        registered_device_id,
        calculation_id,
        application_version_id=None,
    ):
        with _transaction(actor_user_id, registered_device_id) as cursor:
            row = _load_review(cursor, calculation_id, application_version_id)
            content = _support_bytes(row)
            return {
                "calculation_id": str(row["id"]),
                "content_sha256": row["support_sha256"],
                "media_type": row["support_media_type"],
                "byte_count": row["support_byte_count"],
            }, content

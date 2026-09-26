"""Office first-loan coordination; no parallel schedule, cash or Auth engine."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

from psycopg.rows import dict_row, tuple_row
from psycopg.types.json import Jsonb

from .database import open_connection
from .first_loan_terms import (
    FirstLoanTerms,
    generate_first_loan_schedule,
    schedule_payload,
    snapshot_digest,
)
from .loan_application_information import parse_loan_application_information
from .contract_schedule_registration_service import register_verified_contract_schedule
from .contract_schedule_registration_repository import (
    SevenBySevenPricingComplianceReview,
    build_7x7_penalty_policy_schedule_settings,
    build_7x7_pricing_compliance_terms_fingerprint,
)
from .office_review_evidence_repository import (
    capture_evidence,
    require_evidence,
    cif_review_snapshot,
    application_review_snapshot,
    OfficeReviewEvidenceConflict,
)
from .office_review_evidence_storage import PrivateEvidenceStore
from .privacy_record_repository import build_privacy_context
from .client_cif_identity_information import cif_information_from_row

APPROVE_PERMISSION = "lending.first_loan.approve"
RELEASE_PERMISSION = "lending.first_loan.release"
REVIEW_PERMISSION = "client_onboarding.requirement.review"


class FirstLoanError(RuntimeError):
    pass


class FirstLoanConflict(FirstLoanError):
    pass


class FirstLoanAccessDenied(FirstLoanError):
    pass


def _actor(
    cursor, actor_user_id, registered_device_id, permission, *, management=False
):
    roles = ["management"] if management else ["management", "employee"]
    row = cursor.execute(
        """
        select u.id from core.users u join core.devices d on d.user_id=u.id
        where u.id=%s and u.status='active' and d.id=%s and d.status='active'
        and exists(select 1 from core.user_roles ur join core.roles r on r.id=ur.role_id
                   join core.role_permissions rp on rp.role_id=r.id
                   where ur.user_id=u.id and r.code=any(%s) and rp.permission_code=%s)
        for share of u,d
        """,
        (actor_user_id, registered_device_id, roles, permission),
    ).fetchone()
    if row is None:
        raise FirstLoanAccessDenied(
            "An active authorized office account and device are required."
        )


def _source(cursor, version_id):
    app = cursor.execute(
        """select v.*,a.application_reference from lending.loan_application_versions v
        join lending.loan_applications a on a.id=v.application_id where v.id=%s for update of a""",
        (version_id,),
    ).fetchone()
    if app is None:
        raise FirstLoanConflict(
            "A current confirmed application and active CIF are required."
        )
    client = cursor.execute(
        "select * from lending.clients where id=%s for update", (app["client_id"],)
    ).fetchone()
    cif = cursor.execute(
        """select * from lending.client_cif_versions where id=%s and client_id=%s
        and status='active' and is_current and activated_at<=now() and expires_at>now()
        and reverification_required_at is null and baseline_liveness_status='passed'
        and btrim(coalesce(baseline_face_scan_evidence_reference,''))<>'' for share""",
        (app["cif_version_id"], app["client_id"]),
    ).fetchone()
    confirmation = cursor.execute(
        "select * from lending.loan_application_review_confirmations where application_version_id=%s",
        (app["id"],),
    ).fetchone()
    cif_confirmation = cursor.execute(
        "select * from lending.client_cif_review_confirmations where cif_version_id=%s",
        (app["cif_version_id"],),
    ).fetchone()
    latest = cursor.execute(
        "select max(version_number) as n from lending.loan_application_versions where application_id=%s",
        (app["application_id"],),
    ).fetchone()["n"]
    eligible = cursor.execute(
        "select 1 from lending.client_onboarding_applicants where promoted_client_id=%s and status='eligible_for_cif'",
        (app["client_id"],),
    ).fetchone()
    if not (
        client
        and client["status"] == "active"
        and cif
        and confirmation
        and cif_confirmation
        and eligible
        and latest == app["version_number"]
    ):
        raise FirstLoanConflict(
            "A current confirmed application and active CIF are required."
        )
    information = parse_loan_application_information(app["information"])
    if information.missing_fields():
        raise FirstLoanConflict("The confirmed application information is incomplete.")
    cif_information = cif_information_from_row(cif)
    if cif_confirmation["review_snapshot"] != cif_information:
        raise FirstLoanConflict("The CIF confirmation no longer matches its source.")
    try:
        require_evidence(
            cursor,
            evidence_reference=cif_confirmation[
                "applicant_confirmation_evidence_reference"
            ],
            actor_user_id=cif_confirmation["witnessed_by_user_id"],
            client_id=app["client_id"],
            purpose="cif_review",
            subject_id=app["cif_version_id"],
            review_snapshot=cif_review_snapshot(
                client_id=app["client_id"],
                cif_version_id=app["cif_version_id"],
                information=cif_information,
            ),
        )
        require_evidence(
            cursor,
            evidence_reference=confirmation[
                "applicant_confirmation_evidence_reference"
            ],
            actor_user_id=confirmation["witnessed_by_user_id"],
            client_id=app["client_id"],
            purpose="application_review",
            subject_id=app["id"],
            review_snapshot=application_review_snapshot(
                client_id=app["client_id"],
                cif_version_id=app["cif_version_id"],
                application_id=app["application_id"],
                application_version_id=app["id"],
                information=information.model_dump(mode="json"),
                cif_information=cif_information,
            ),
        )
    except OfficeReviewEvidenceConflict as exc:
        raise FirstLoanConflict(
            "Protected applicant confirmation evidence is required."
        ) from exc
    privacy = cursor.execute(
        "select * from lending.client_privacy_acknowledgments where client_id=%s and cif_version_id=%s order by acknowledged_at desc,id desc limit 1",
        (app["client_id"], cif["id"]),
    ).fetchone()
    if privacy is None:
        raise FirstLoanConflict("Exact-version privacy acknowledgment is required.")
    privacy_context = build_privacy_context(
        cursor,
        client_id=app["client_id"],
        cif_version_id=cif["id"],
        optional_service_communications=privacy["optional_service_communications"],
    )
    if (
        not privacy_context["issuable"]
        or privacy_context["review_snapshot"] != privacy["review_snapshot"]
    ):
        raise FirstLoanConflict(
            "The current privacy package requires acknowledgment before loan approval."
        )
    require_evidence(
        cursor,
        evidence_reference=f"office-evidence:{privacy['evidence_id']}",
        actor_user_id=privacy["acknowledged_by_user_id"],
        client_id=app["client_id"],
        purpose="privacy_acknowledgment",
        subject_id=cif["id"],
        review_snapshot=privacy["review_snapshot"],
    )
    return app, cif, client, privacy


def _load(cursor, loan_id):
    row = cursor.execute(
        """select a.*,l.status as loan_status,l.loan_number,l.date_released,l.due_date
        from lending.first_loan_approvals a join lending.loans l on l.id=a.loan_id
        where a.loan_id=%s for update of l""",
        (loan_id,),
    ).fetchone()
    if row is None:
        raise FirstLoanConflict("The first-loan record is unavailable.")
    if snapshot_digest(row["packet"]) != row["packet_hash"]:
        raise FirstLoanConflict("The locked packet failed its integrity check.")
    return row


def _locked_source(cursor, row):
    sources = _source(cursor, row["application_version_id"])
    if sources[3]["review_snapshot"] != row["packet"]["privacy"]["review_snapshot"]:
        raise FirstLoanConflict(
            "The privacy package differs from the approved packet. Obtain a revised approval."
        )
    return sources


def _template(cursor, row, *, execution=False):
    template = cursor.execute(
        "select * from lending.first_loan_document_templates where version=%s for share",
        (row["template_version"],),
    ).fetchone()
    if (
        not template
        or not template["is_active"]
        or template["content_sha256"] != row["packet"]["template"]["content_sha256"]
        or (execution and not template["approved_for_execution"])
    ):
        raise FirstLoanConflict(
            "An active approved legal-template version is required for execution."
        )
    return template


def _authorization(cursor, row, authorization_id):
    authorization = cursor.execute(
        """select a.* from lending.first_loan_authorizations a
        where a.id=%s and a.loan_id=%s and a.packet_hash=%s
        and not exists(select 1 from lending.first_loan_authorization_revocations r where r.authorization_id=a.id)
        and not exists(select 1 from lending.first_loan_authorizations newer where newer.loan_id=a.loan_id
            and (newer.authorized_at,newer.id)>(a.authorized_at,a.id))""",
        (authorization_id, row["loan_id"], row["packet_hash"]),
    ).fetchone()
    if authorization is None:
        raise FirstLoanConflict(
            "The exact current Management release authorization is required."
        )
    # Revoked/inactive Management cannot leave a live authorization behind.
    valid = cursor.execute(
        """select 1 from core.users u where u.id=%s and u.status='active'
        and exists(select 1 from core.user_roles ur join core.roles r on r.id=ur.role_id
        join core.role_permissions p on p.role_id=r.id where ur.user_id=u.id and r.code='management'
        and p.permission_code=%s) for share of u""",
        (authorization["authorized_by_user_id"], APPROVE_PERMISSION),
    ).fetchone()
    if valid is None:
        raise FirstLoanConflict("Management release authorization is no longer valid.")
    return authorization


def _document(cursor, row, *, execution=False):
    document = cursor.execute(
        "select * from lending.first_loan_packet_documents where loan_id=%s and packet_hash=%s",
        (row["loan_id"], row["packet_hash"]),
    ).fetchone()
    if document is None:
        raise FirstLoanConflict(
            "Generate and review the exact populated contract packet PDF before signing."
        )
    PrivateEvidenceStore().read(
        document["storage_key"], document["content_sha256"], document["byte_count"]
    )
    terms = FirstLoanTerms.model_validate(row["packet"]["terms"])
    if execution and document["pricing_snapshot"] != _pricing_settings(
        cursor, row, terms, generate_first_loan_schedule(terms)
    ):
        raise FirstLoanConflict(
            "Pricing authority differs from the issued packet. Cancel and issue a revised approval before signing or release."
        )
    return {
        "id": str(document["id"]),
        "content_sha256": document["content_sha256"],
        "byte_count": document["byte_count"],
        "pricing_snapshot": document["pricing_snapshot"],
    }


def _sign_snapshot(row, document):
    return {
        "schema_version": 1,
        "scope": "first_loan_locked_contract",
        "loan_id": str(row["loan_id"]),
        "packet_id": str(row["id"]),
        "packet_hash": row["packet_hash"],
        "packet": row["packet"],
        "document": document,
        "witnessed_wet_signature": True,
    }


def _cash_snapshot(row, authorization_id, document):
    terms = FirstLoanTerms.model_validate(row["packet"]["terms"])
    return {
        "schema_version": 1,
        "scope": "first_loan_cash_receipt",
        "loan_id": str(row["loan_id"]),
        "packet_hash": row["packet_hash"],
        "authorization_id": str(authorization_id),
        "client_id": str(row["client_id"]),
        "cash_amount": str(terms.net_cash),
        "schedule_basis_date": terms.schedule_basis_date.isoformat(),
        "document": document,
    }


def _pricing_settings(cursor, row, terms, rows):
    if terms.product_code != "seven_by_seven":
        return {}
    fingerprint = build_7x7_pricing_compliance_terms_fingerprint(
        context=SimpleNamespace(
            loan_id=row["loan_id"],
            principal=terms.principal,
            daily_interest_per_1000=terms.daily_interest_per_1000,
        ),
        payment_frequency=terms.payment_frequency,
        contract_reference=str(row["id"]),
        contract_signed_date=terms.schedule_basis_date,
        effective_from=terms.schedule_basis_date,
        grace_days=terms.grace_days,
        agreed_daily_payment=terms.installment_amount,
        installments=rows,
    )
    evidence = cursor.execute(
        """select * from lending.seven_by_seven_pricing_compliance_reviews
        where loan_id=%s and terms_fingerprint=%s order by reviewed_at desc,id desc limit 1""",
        (row["loan_id"], fingerprint),
    ).fetchone()
    if evidence is None:
        raise FirstLoanConflict(
            "The exact 7x7 terms require existing pricing/compliance review before signing."
        )
    review = SevenBySevenPricingComplianceReview(**evidence)
    if not review.penalty_authority_ready:
        raise FirstLoanConflict(
            "The latest exact 7x7 pricing/disclosure review is not ready."
        )
    return build_7x7_penalty_policy_schedule_settings(review=review)


def _public(cursor, row, actor_user_id=None):
    release = cursor.execute(
        "select * from lending.first_loan_releases where loan_id=%s", (row["loan_id"],)
    ).fetchone()
    authorization = cursor.execute(
        """select a.*,exists(select 1 from lending.first_loan_authorization_revocations r where r.authorization_id=a.id) as revoked
        from lending.first_loan_authorizations a where loan_id=%s order by authorized_at desc,id desc limit 1""",
        (row["loan_id"],),
    ).fetchone()
    intent = cursor.execute(
        "select id,status,last_error_code from lending.first_loan_credential_intents where loan_id=%s",
        (row["loan_id"],),
    ).fetchone()
    document = cursor.execute(
        "select id,content_sha256,byte_count,generated_at,pricing_snapshot from lending.first_loan_packet_documents where loan_id=%s",
        (row["loan_id"],),
    ).fetchone()
    terms = FirstLoanTerms.model_validate(row["packet"]["terms"])
    try:
        pricing_snapshot = _pricing_settings(
            cursor, row, terms, generate_first_loan_schedule(terms)
        )
    except FirstLoanConflict:
        pricing_snapshot = None
    evidence = {}
    if actor_user_id and document and row["loan_status"] == "approved":
        metadata = {
            key: (str(document[key]) if key == "id" else document[key])
            for key in ("id", "content_sha256", "byte_count", "pricing_snapshot")
        }
        snapshots = {"borrower_contract_signed": _sign_snapshot(row, metadata)}
        if authorization and not authorization["revoked"]:
            snapshots["borrower_cash_received"] = _cash_snapshot(
                row, authorization["id"], metadata
            )
        captures = cursor.execute(
            "select id,purpose,review_snapshot,captured_at from lending.office_review_evidence where subject_id=%s and (purpose='borrower_contract_signed' or captured_by_user_id=%s) order by captured_at desc,id desc",
            (row["id"], actor_user_id),
        ).fetchall()
        for capture in captures:
            purpose = capture["purpose"]
            if purpose not in evidence and capture["review_snapshot"] == snapshots.get(
                purpose
            ):
                evidence[purpose] = {
                    "evidence_reference": f"office-evidence:{capture['id']}",
                    "captured_at": capture["captured_at"],
                }
    return {
        "loan_id": str(row["loan_id"]),
        "client_id": str(row["client_id"]),
        "packet_id": str(row["id"]),
        "packet_hash": row["packet_hash"],
        "packet": row["packet"],
        "loan_number": row["loan_number"],
        "evidence": evidence,
        "pricing_snapshot": pricing_snapshot,
        "status": "released"
        if release
        else (
            "approved_pending_release"
            if row["loan_status"] == "approved"
            else row["loan_status"]
        ),
        "approved_at": row["approved_at"],
        "approved_by_user_id": str(row["approved_by_user_id"]),
        "document": None
        if document is None
        else {**document, "id": str(document["id"])},
        "authorization": None
        if authorization is None
        else {
            "id": str(authorization["id"]),
            "revoked": authorization["revoked"],
            "authorized_at": authorization["authorized_at"],
        },
        "release": None
        if release is None
        else {
            "id": str(release["id"]),
            "released_at": release["released_at"],
            "receipt": release["receipt"],
        },
        "credential_intent": None
        if intent is None
        else {
            "id": str(intent["id"]),
            "status": intent["status"],
            "error_code": intent["last_error_code"],
        },
    }


class PostgresFirstLoanRepository:
    def register_packet_document(
        self,
        *,
        actor_user_id,
        registered_device_id,
        loan_id,
        packet_hash,
        content,
        expected_pricing_snapshot,
    ):
        """Trusted renderer seam only. Never expose this as a browser PDF upload."""
        from .first_loan_disclosure_binding import require_packet_source

        with (
            open_connection() as connection,
            connection.transaction(),
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            _actor(
                cursor,
                actor_user_id,
                registered_device_id,
                APPROVE_PERMISSION,
                management=True,
            )
            row = _load(cursor, loan_id)
            if row["packet_hash"] != packet_hash:
                raise FirstLoanConflict("The exact approved packet is required.")
            existing = cursor.execute(
                "select * from lending.first_loan_packet_documents where loan_id=%s",
                (loan_id,),
            ).fetchone()
            if existing:
                import hashlib

                if (
                    existing["content_sha256"] != hashlib.sha256(content).hexdigest()
                    or existing["pricing_snapshot"] != expected_pricing_snapshot
                ):
                    raise FirstLoanConflict(
                        "The issued packet is immutable; create a revised approval."
                    )
                # An authorized exact retry reads the retained original. It is
                # not new issuance, even after sources change or cash is released.
                return _document(cursor, row)
            if row["loan_status"] != "approved":
                raise FirstLoanConflict(
                    "The exact unreleased approved packet is required."
                )
            require_packet_source(cursor, row=row)
            _template(cursor, row, execution=True)
            _locked_source(cursor, row)
            terms = FirstLoanTerms.model_validate(row["packet"]["terms"])
            pricing_snapshot = _pricing_settings(
                cursor, row, terms, generate_first_loan_schedule(terms)
            )
            if pricing_snapshot != expected_pricing_snapshot:
                raise FirstLoanConflict(
                    "The pricing authority changed while generating the packet. Reload its exact terms."
                )
            document_id = uuid4()
            digest = PrivateEvidenceStore().put(document_id, content, "application/pdf")
            cursor.execute(
                "insert into lending.first_loan_packet_documents(id,loan_id,packet_hash,content_sha256,byte_count,storage_key,pricing_snapshot,generated_by_user_id) values(%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    document_id,
                    loan_id,
                    packet_hash,
                    digest,
                    len(content),
                    document_id,
                    Jsonb(pricing_snapshot),
                    actor_user_id,
                ),
            )
            return _document(cursor, row)

    def packet_document(self, *, actor_user_id, registered_device_id, loan_id):
        with (
            open_connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            _actor(cursor, actor_user_id, registered_device_id, REVIEW_PERMISSION)
            row = _load(cursor, loan_id)
            metadata = _document(cursor, row)
            document = cursor.execute(
                "select * from lending.first_loan_packet_documents where loan_id=%s",
                (loan_id,),
            ).fetchone()
            return metadata, PrivateEvidenceStore().read(
                document["storage_key"],
                document["content_sha256"],
                document["byte_count"],
            )

    def context(self, *, actor_user_id, registered_device_id):
        with (
            open_connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            _actor(cursor, actor_user_id, registered_device_id, REVIEW_PERMISSION)
            templates = cursor.execute(
                "select version,content_sha256,approved_for_execution from lending.first_loan_document_templates where is_active order by version"
            ).fetchall()
            products = cursor.execute(
                "select id,code,name,calculation_mode,daily_interest_per_1000 from lending.loan_types where is_active and calculation_mode in ('fixed_daily','fixed_total','seven_by_seven') order by name,id"
            ).fetchall()
            today = cursor.execute(
                "select (clock_timestamp() at time zone 'Asia/Manila')::date as d"
            ).fetchone()["d"]
            return {
                "server_business_date": today.isoformat(),
                "templates": templates,
                "products": [
                    {
                        **p,
                        "id": str(p["id"]),
                        "daily_interest_per_1000": str(p["daily_interest_per_1000"]),
                    }
                    for p in products
                ],
            }

    def get(self, *, actor_user_id, registered_device_id, loan_id):
        with (
            open_connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            _actor(cursor, actor_user_id, registered_device_id, REVIEW_PERMISSION)
            return _public(cursor, _load(cursor, loan_id), actor_user_id)

    def by_application(self, *, actor_user_id, registered_device_id, application_id):
        with (
            open_connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            _actor(cursor, actor_user_id, registered_device_id, REVIEW_PERMISSION)
            rows = cursor.execute(
                """select a.loan_id from lending.first_loan_approvals a
                join lending.loan_application_versions v on v.id=a.application_version_id
                where v.application_id=%s order by a.approved_at desc,a.id desc""",
                (application_id,),
            ).fetchall()
            decisions = cursor.execute(
                "select d.id,d.application_version_id,d.decision,d.reason,d.recorded_at from lending.first_loan_decisions d join lending.loan_application_versions v on v.id=d.application_version_id where v.application_id=%s order by d.recorded_at desc,d.id desc",
                (application_id,),
            ).fetchall()
            return {
                "loans": [
                    _public(cursor, _load(cursor, r["loan_id"]), actor_user_id)
                    for r in rows
                ],
                "decisions": [
                    {
                        **d,
                        "id": str(d["id"]),
                        "application_version_id": str(d["application_version_id"]),
                    }
                    for d in decisions
                ],
            }

    def approve(
        self,
        *,
        actor_user_id,
        registered_device_id,
        application_version_id,
        terms,
        template_version,
        request_id,
        disclosure_calculation_id=None,
        expected_disclosure_digest=None,
    ):
        from .first_loan_disclosure_binding import require_for_approval, retry_matches

        terms = FirstLoanTerms.model_validate(terms)
        rows = generate_first_loan_schedule(terms)
        with (
            open_connection() as connection,
            connection.transaction(),
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            _actor(
                cursor,
                actor_user_id,
                registered_device_id,
                APPROVE_PERMISSION,
                management=True,
            )
            # Advisory request lock avoids divergent retries before a row exists.
            cursor.execute(
                "select pg_advisory_xact_lock(hashtextextended(%s,0))",
                (str(request_id),),
            )
            existing = cursor.execute(
                "select loan_id from lending.first_loan_approvals where request_id=%s",
                (request_id,),
            ).fetchone()
            if existing:
                row = _load(cursor, existing["loan_id"])
                if (
                    row["approved_by_user_id"] != actor_user_id
                    or row["application_version_id"] != application_version_id
                    or row["packet"]["terms"] != terms.model_dump(mode="json")
                    or row["template_version"] != template_version
                    or not retry_matches(
                        row["packet"],
                        disclosure_calculation_id,
                        expected_disclosure_digest,
                    )
                ):
                    raise FirstLoanConflict(
                        "This approval request identity is already used."
                    )
                return _public(cursor, row, actor_user_id)
            # New approvals consume the exact saved review in this transaction.
            # Authorized committed retries above do not revalidate current sources.
            disclosure = require_for_approval(
                cursor,
                calculation_id=disclosure_calculation_id,
                expected_digest=expected_disclosure_digest,
                application_version_id=application_version_id,
                terms=terms,
                rows=rows,
            )
            app, cif, client, privacy = _source(cursor, application_version_id)
            if cursor.execute(
                "select 1 from lending.loans where client_id=%s and status not in ('draft','cancelled')",
                (app["client_id"],),
            ).fetchone():
                raise FirstLoanConflict(
                    "This Client already has an approved or released loan; use the existing renewal workflow."
                )
            product = cursor.execute(
                "select * from lending.loan_types where id=%s and is_active for share",
                (terms.loan_type_id,),
            ).fetchone()
            expected = (
                "seven_by_seven" if terms.product_code == "seven_by_seven" else None
            )
            if (
                not product
                or (expected and product["calculation_mode"] != expected)
                or (
                    not expected
                    and product["calculation_mode"]
                    not in ("fixed_daily", "fixed_total")
                )
            ):
                raise FirstLoanConflict(
                    "The approved product is not an active supported catalog product."
                )
            if (
                expected
                and product["daily_interest_per_1000"] != terms.daily_interest_per_1000
            ):
                raise FirstLoanConflict(
                    "The approved 7x7 interest must match its authoritative product basis."
                )
            template = cursor.execute(
                "select * from lending.first_loan_document_templates where version=%s and is_active for share",
                (template_version,),
            ).fetchone()
            if template is None:
                raise FirstLoanConflict(
                    "A configured controlled template version is required."
                )
            today = cursor.execute(
                "select (clock_timestamp() at time zone 'Asia/Manila')::date as d"
            ).fetchone()["d"]
            if terms.schedule_basis_date < today:
                raise FirstLoanConflict(
                    "An approval cannot invent a past actual release date."
                )
            loan_id, packet_id = uuid4(), uuid4()
            packet = {
                "schema_version": 2,
                "tax_disclosure": disclosure,
                "packet_id": str(packet_id),
                "loan_id": str(loan_id),
                "client_id": str(app["client_id"]),
                "borrower": cif_information_from_row(cif),
                "cif_version_id": str(cif["id"]),
                "cif_version_number": cif["version_number"],
                "application": {
                    "id": str(app["id"]),
                    "application_id": str(app["application_id"]),
                    "reference": app["application_reference"],
                    "version_number": app["version_number"],
                    "information": app["information"],
                },
                "terms": terms.model_dump(mode="json"),
                "schedule": schedule_payload(rows),
                "template": {
                    "version": template_version,
                    "content_sha256": template["content_sha256"],
                },
                "product_name": product["name"],
                "contract_reference": str(packet_id),
                "planned_contract_date": terms.schedule_basis_date.isoformat(),
                "privacy": {
                    "id": str(privacy["id"]),
                    "evidence_id": str(privacy["evidence_id"]),
                    "acknowledged_at": privacy["acknowledged_at"].isoformat(),
                    "review_snapshot": privacy["review_snapshot"],
                },
                "net_cash": str(terms.net_cash),
                "total_deductions": str(terms.total_deductions),
            }
            cursor.execute(
                """insert into lending.loans(id,loan_number,client_id,loan_type_id,principal,daily_amount,interest_rate,date_released,due_date,status,created_by_user_id)
                values(%s,%s,%s,%s,%s,%s,%s,null,null,'approved',%s)""",
                (
                    loan_id,
                    f"FL-{loan_id.hex.upper()}",
                    app["client_id"],
                    terms.loan_type_id,
                    terms.principal,
                    terms.installment_amount,
                    terms.interest_rate_percent,
                    actor_user_id,
                ),
            )
            cursor.execute(
                """insert into lending.first_loan_approvals(id,request_id,loan_id,client_id,application_version_id,cif_version_id,template_version,packet,packet_hash,approved_by_user_id,approved_device_id)
                values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    packet_id,
                    request_id,
                    loan_id,
                    app["client_id"],
                    app["id"],
                    cif["id"],
                    template_version,
                    Jsonb(packet),
                    snapshot_digest(packet),
                    actor_user_id,
                    registered_device_id,
                ),
            )
            return _public(cursor, _load(cursor, loan_id), actor_user_id)

    def reject(
        self,
        *,
        actor_user_id,
        registered_device_id,
        application_version_id,
        reason,
        request_id,
    ):
        reason = reason.strip()
        if not reason:
            raise FirstLoanConflict("A decision reason is required.")
        with (
            open_connection() as connection,
            connection.transaction(),
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            _actor(
                cursor,
                actor_user_id,
                registered_device_id,
                APPROVE_PERMISSION,
                management=True,
            )
            cursor.execute(
                "select pg_advisory_xact_lock(hashtextextended(%s,0))",
                (str(request_id),),
            )
            existing = cursor.execute(
                "select * from lending.first_loan_decisions where request_id=%s",
                (request_id,),
            ).fetchone()
            if existing:
                if (
                    existing["application_version_id"] != application_version_id
                    or existing["reason"] != reason
                    or existing["actor_user_id"] != actor_user_id
                    or existing["decision"] != "rejected"
                ):
                    raise FirstLoanConflict(
                        "This decision request identity is already used."
                    )
                return {"decision_id": str(existing["id"]), "decision": "rejected"}
            _source(cursor, application_version_id)
            if cursor.execute(
                "select 1 from lending.first_loan_approvals a join lending.loans l on l.id=a.loan_id where a.application_version_id=%s and l.status<>'cancelled'",
                (application_version_id,),
            ).fetchone():
                raise FirstLoanConflict(
                    "This application has an approved loan. Use the exact approval cancellation workflow."
                )
            row = cursor.execute(
                "insert into lending.first_loan_decisions(request_id,application_version_id,decision,reason,actor_user_id) values(%s,%s,'rejected',%s,%s) returning id",
                (request_id, application_version_id, reason, actor_user_id),
            ).fetchone()
            return {"decision_id": str(row["id"]), "decision": "rejected"}

    def cancel_approval(
        self,
        *,
        actor_user_id,
        registered_device_id,
        loan_id,
        packet_hash,
        reason,
        request_id,
    ):
        if not reason.strip():
            raise FirstLoanConflict("A cancellation reason is required.")
        with (
            open_connection() as connection,
            connection.transaction(),
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            _actor(
                cursor,
                actor_user_id,
                registered_device_id,
                APPROVE_PERMISSION,
                management=True,
            )
            row = _load(cursor, loan_id)
            existing = cursor.execute(
                "select * from lending.first_loan_decisions where request_id=%s",
                (request_id,),
            ).fetchone()
            if (
                existing
                and existing["loan_id"] == row["loan_id"]
                and existing["actor_user_id"] == actor_user_id
                and existing["reason"] == reason.strip()
                and existing["decision"] == "approval_cancelled"
            ):
                return _public(cursor, row, actor_user_id)
            if (
                existing
                or row["loan_status"] != "approved"
                or packet_hash != row["packet_hash"]
            ):
                raise FirstLoanConflict(
                    "Only the exact unreleased approval can be cancelled."
                )
            cursor.execute(
                "update lending.loans set status='cancelled',updated_at=now() where id=%s",
                (loan_id,),
            )
            cursor.execute(
                "insert into lending.first_loan_decisions(request_id,application_version_id,loan_id,decision,reason,actor_user_id) values(%s,%s,%s,'approval_cancelled',%s,%s)",
                (
                    request_id,
                    row["application_version_id"],
                    loan_id,
                    reason.strip(),
                    actor_user_id,
                ),
            )
            return _public(cursor, _load(cursor, loan_id), actor_user_id)

    def authorize_release(
        self, *, actor_user_id, registered_device_id, loan_id, packet_hash, request_id
    ):
        from .first_loan_disclosure_binding import require_packet_source

        with (
            open_connection() as connection,
            connection.transaction(),
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            _actor(
                cursor,
                actor_user_id,
                registered_device_id,
                APPROVE_PERMISSION,
                management=True,
            )
            row = _load(cursor, loan_id)
            existing = cursor.execute(
                "select * from lending.first_loan_authorizations where request_id=%s",
                (request_id,),
            ).fetchone()
            if existing:
                if (
                    existing["loan_id"] != row["loan_id"]
                    or existing["packet_hash"] != packet_hash
                    or existing["authorized_by_user_id"] != actor_user_id
                ):
                    raise FirstLoanConflict(
                        "This authorization request identity is already used."
                    )
                return {
                    "authorization_id": str(existing["id"]),
                    "packet_hash": packet_hash,
                }
            if row["loan_status"] != "approved" or row["packet_hash"] != packet_hash:
                raise FirstLoanConflict(
                    "Only the exact unreleased approved packet may be authorized."
                )
            require_packet_source(cursor, row=row)
            _template(cursor, row, execution=True)
            _document(cursor, row, execution=True)
            _locked_source(cursor, row)
            terms = FirstLoanTerms.model_validate(row["packet"]["terms"])
            _pricing_settings(cursor, row, terms, generate_first_loan_schedule(terms))
            item = cursor.execute(
                "insert into lending.first_loan_authorizations(request_id,loan_id,packet_hash,authorized_by_user_id) values(%s,%s,%s,%s) returning id",
                (request_id, loan_id, packet_hash, actor_user_id),
            ).fetchone()
            return {"authorization_id": str(item["id"]), "packet_hash": packet_hash}

    def revoke_release(
        self,
        *,
        actor_user_id,
        registered_device_id,
        loan_id,
        authorization_id,
        reason,
        request_id,
    ):
        if not reason.strip():
            raise FirstLoanConflict("A revocation reason is required.")
        with (
            open_connection() as connection,
            connection.transaction(),
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            _actor(
                cursor,
                actor_user_id,
                registered_device_id,
                APPROVE_PERMISSION,
                management=True,
            )
            row = _load(cursor, loan_id)
            if row["loan_status"] != "approved":
                raise FirstLoanConflict(
                    "A completed release cannot be revoked by this workflow."
                )
            existing = cursor.execute(
                "select * from lending.first_loan_authorization_revocations where request_id=%s",
                (request_id,),
            ).fetchone()
            if existing:
                if (
                    existing["authorization_id"] != authorization_id
                    or existing["revoked_by_user_id"] != actor_user_id
                    or existing["reason"] != reason.strip()
                ):
                    raise FirstLoanConflict(
                        "This revocation request identity is already used."
                    )
                return {"revocation_id": str(existing["id"])}
            _authorization(cursor, row, authorization_id)
            revocation = cursor.execute(
                "insert into lending.first_loan_authorization_revocations(request_id,authorization_id,reason,revoked_by_user_id) values(%s,%s,%s,%s) returning id",
                (request_id, authorization_id, reason.strip(), actor_user_id),
            ).fetchone()
            return {"revocation_id": str(revocation["id"])}

    def capture(
        self,
        *,
        actor_user_id,
        registered_device_id,
        loan_id,
        packet_hash,
        purpose,
        content,
        media_type,
        request_id,
        authorization_id=None,
        witnessed_wet_signature=False,
    ):
        from .first_loan_disclosure_binding import require_packet_source

        if purpose not in ("borrower_contract_signed", "borrower_cash_received"):
            raise FirstLoanConflict("Unsupported first-loan evidence purpose.")
        if (
            purpose == "borrower_contract_signed"
            and witnessed_wet_signature is not True
        ):
            raise FirstLoanConflict(
                "The named borrower wet signature must be witnessed at the office."
            )
        with (
            open_connection() as connection,
            connection.transaction(),
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            _actor(cursor, actor_user_id, registered_device_id, RELEASE_PERMISSION)
            row = _load(cursor, loan_id)
            if packet_hash != row["packet_hash"]:
                raise FirstLoanConflict("The exact approved packet is required.")
            # Use the evidence owner's request lock before deciding whether this
            # is a committed replay. Its exact immutable comparison still runs.
            cursor.execute(
                "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (str(request_id),),
            )
            existing = cursor.execute(
                "select id from lending.office_review_evidence where request_id = %s",
                (request_id,),
            ).fetchone()
            if existing is not None:
                document = _document(cursor, row)
            else:
                if row["loan_status"] != "approved":
                    raise FirstLoanConflict("The exact unreleased packet is required.")
                require_packet_source(cursor, row=row)
                _template(cursor, row, execution=True)
                _locked_source(cursor, row)
                terms = FirstLoanTerms.model_validate(row["packet"]["terms"])
                today = cursor.execute(
                    "select (clock_timestamp() at time zone 'Asia/Manila')::date as d"
                ).fetchone()["d"]
                if today != terms.schedule_basis_date:
                    raise FirstLoanConflict(
                        "The signed date basis changed; obtain a revised approved packet and signatures."
                    )
                _pricing_settings(
                    cursor, row, terms, generate_first_loan_schedule(terms)
                )
                document = _document(cursor, row, execution=True)
            snapshot = _sign_snapshot(row, document)
            if purpose == "borrower_cash_received":
                if existing is None:
                    _authorization(cursor, row, authorization_id)
                snapshot = _cash_snapshot(row, authorization_id, document)
            evidence = capture_evidence(
                cursor,
                actor_user_id=actor_user_id,
                client_id=row["client_id"],
                cif_version_id=row["cif_version_id"],
                application_id=UUID(row["packet"]["application"]["application_id"]),
                application_version_id=row["application_version_id"],
                purpose=purpose,
                subject_id=row["id"],
                review_snapshot=snapshot,
                content=content,
                media_type=media_type,
                request_id=request_id,
            )
            return {
                "evidence_reference": evidence.evidence_reference,
                "content_sha256": evidence.content_sha256,
                "captured_at": evidence.captured_at,
                "purpose": purpose,
                "packet_hash": packet_hash,
            }

    def release(
        self,
        *,
        actor_user_id,
        registered_device_id,
        loan_id,
        packet_hash,
        authorization_id,
        contract_evidence_reference,
        cash_evidence_reference,
        cash_amount,
        borrower_confirmed,
        request_id,
    ):
        from .first_loan_disclosure_binding import require_packet_source

        if borrower_confirmed is not True:
            raise FirstLoanConflict(
                "The named borrower must confirm actual cash received."
            )
        cash = Decimal(cash_amount)
        if not cash.is_finite() or cash <= 0 or cash != cash.quantize(Decimal("0.01")):
            raise FirstLoanConflict("Exact cash received is required.")
        with (
            open_connection() as connection,
            connection.transaction(),
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            _actor(cursor, actor_user_id, registered_device_id, RELEASE_PERMISSION)
            row = _load(cursor, loan_id)
            existing = cursor.execute(
                "select * from lending.first_loan_releases where loan_id=%s or request_id=%s",
                (loan_id, request_id),
            ).fetchone()
            if existing:
                if (
                    existing["loan_id"] != row["loan_id"]
                    or existing["request_id"] != request_id
                    or existing["released_by_user_id"] != actor_user_id
                    or existing["packet_hash"] != packet_hash
                    or existing["authorization_id"] != authorization_id
                    or existing["cash_amount"] != cash
                    or existing["contract_evidence_reference"]
                    != contract_evidence_reference
                    or existing["cash_evidence_reference"] != cash_evidence_reference
                ):
                    raise FirstLoanConflict(
                        "The release request conflicts with the recorded handoff; reload its receipt."
                    )
                return _public(cursor, row, actor_user_id)
            if row["loan_status"] != "approved" or row["packet_hash"] != packet_hash:
                raise FirstLoanConflict(
                    "The exact unreleased approved packet is required."
                )
            require_packet_source(cursor, row=row)
            _template(cursor, row, execution=True)
            document = _document(cursor, row, execution=True)
            _locked_source(cursor, row)
            authorization = _authorization(cursor, row, authorization_id)
            terms = FirstLoanTerms.model_validate(row["packet"]["terms"])
            if cash != terms.net_cash:
                raise FirstLoanConflict(
                    "Actual cash must equal the approved net cash exactly; partial release is not allowed."
                )
            moment = cursor.execute(
                "with instant as materialized (select clock_timestamp() as ts) select ts,(ts at time zone 'Asia/Manila')::date as d from instant"
            ).fetchone()
            if moment["d"] != terms.schedule_basis_date:
                raise FirstLoanConflict(
                    "Actual release date differs from the signed basis; obtain a revised approved packet and signatures."
                )
            for purpose, reference, snapshot in (
                (
                    "borrower_contract_signed",
                    contract_evidence_reference,
                    _sign_snapshot(row, document),
                ),
                (
                    "borrower_cash_received",
                    cash_evidence_reference,
                    _cash_snapshot(row, authorization_id, document),
                ),
            ):
                witness_id = actor_user_id
                if purpose == "borrower_contract_signed":
                    witness = cursor.execute(
                        "select captured_by_user_id from lending.office_review_evidence where ('office-evidence:'||id::text)=%s and subject_id=%s and purpose='borrower_contract_signed'",
                        (reference, row["id"]),
                    ).fetchone()
                    if witness is None:
                        raise FirstLoanConflict(
                            "Protected exact contract signing evidence is required."
                        )
                    witness_id = witness["captured_by_user_id"]
                require_evidence(
                    cursor,
                    evidence_reference=reference,
                    actor_user_id=witness_id,
                    client_id=row["client_id"],
                    purpose=purpose,
                    subject_id=row["id"],
                    review_snapshot=snapshot,
                )
            rows = generate_first_loan_schedule(terms)
            if schedule_payload(rows) != row["packet"]["schedule"]:
                raise FirstLoanConflict(
                    "The authoritative schedule no longer matches the locked packet."
                )
            settings = _pricing_settings(cursor, row, terms, rows)
            settings["first_loan_packet_hash"] = packet_hash
            release_id = uuid4()
            receipt_reference = f"FLR-{release_id.hex.upper()}"
            cursor.execute(
                "update lending.loans set status='active',date_released=%s,due_date=%s,updated_at=now() where id=%s",
                (moment["d"], rows[-1].due_date, loan_id),
            )
            with connection.cursor(row_factory=tuple_row) as schedule_cursor:
                schedule_id = register_verified_contract_schedule(
                    schedule_cursor,
                    loan_id=UUID(str(loan_id)),
                    payment_frequency=terms.payment_frequency,
                    contract_reference=str(row["id"]),
                    contract_signed_date=terms.schedule_basis_date,
                    effective_from=moment["d"],
                    grace_days=terms.grace_days,
                    installments=rows,
                    evidence_basis="signed_contract",
                    evidence_reference=contract_evidence_reference,
                    verification_note=f"Exact office first-loan packet {packet_hash}",
                    verified_by_user_id=authorization["authorized_by_user_id"],
                    agreed_daily_payment=terms.installment_amount
                    if terms.product_code == "seven_by_seven"
                    else None,
                    schedule_settings=settings,
                    confirmed=True,
                )
            event = cursor.execute(
                "select accounting.record_loan_disbursement_evidence(%s,%s,'new_loan_release',%s,%s,%s,0,%s,'cash_office',%s,%s) as id",
                (
                    loan_id,
                    actor_user_id,
                    moment["d"],
                    moment["ts"],
                    cash,
                    terms.total_deductions,
                    receipt_reference,
                    f"Office first-loan packet {packet_hash}",
                ),
            ).fetchone()
            remaining = (
                terms.principal
                if terms.product_code == "seven_by_seven"
                else sum((r.contractual_amount for r in rows), Decimal("0.00"))
            )
            cursor.execute(
                "insert into lending.loan_collection_state(loan_id,remaining_balance) values(%s,%s)",
                (loan_id, remaining),
            )
            receipt = {
                "receipt_reference": receipt_reference,
                "loan_id": str(loan_id),
                "loan_number": row["loan_number"],
                "client_id": str(row["client_id"]),
                "borrower_name": row["packet"]["borrower"]["full_name"],
                "packet_id": str(row["id"]),
                "packet_hash": packet_hash,
                "gross_principal": str(terms.principal),
                "deductions": str(terms.total_deductions),
                "actual_cash_received": str(cash),
                "released_at": moment["ts"].isoformat(),
                "management_authorizer_id": str(authorization["authorized_by_user_id"]),
                "releasing_staff_id": str(actor_user_id),
                "contract_evidence_reference": contract_evidence_reference,
                "cash_evidence_reference": cash_evidence_reference,
            }
            cursor.execute(
                """insert into lending.first_loan_releases(id,request_id,loan_id,authorization_id,packet_hash,contract_evidence_reference,cash_evidence_reference,cash_amount,receipt_reference,schedule_id,disbursement_event_id,released_by_user_id,released_device_id,released_at,receipt)
                values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    release_id,
                    request_id,
                    loan_id,
                    authorization_id,
                    packet_hash,
                    contract_evidence_reference,
                    cash_evidence_reference,
                    cash,
                    receipt_reference,
                    schedule_id,
                    event["id"],
                    actor_user_id,
                    registered_device_id,
                    moment["ts"],
                    Jsonb(receipt),
                ),
            )
            cursor.execute(
                """insert into lending.first_loan_credential_intents(client_id,loan_id,release_id,email,requested_by_user_id)
                values(%s,%s,%s,%s,%s)""",
                (
                    row["client_id"],
                    loan_id,
                    release_id,
                    terms.account_email,
                    actor_user_id,
                ),
            )
            return _public(cursor, _load(cursor, loan_id), actor_user_id)

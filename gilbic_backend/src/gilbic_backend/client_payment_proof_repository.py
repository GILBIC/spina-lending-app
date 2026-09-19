"""Borrower payment evidence; never an authority to post or confirm money."""

from __future__ import annotations

import hashlib
from uuid import UUID, uuid5

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .database import open_connection
from .office_review_evidence_storage import (
    EVIDENCE_MEDIA_TYPES,
    MAX_EVIDENCE_BYTES,
    EvidenceFileError,
    PrivateEvidenceStore,
    validate_evidence_content,
)

REVIEW_PERMISSION = "client_payment_proof.review"
IDENTITY_NAMESPACE = UUID("d40c0bca-5cdd-4c9d-8b89-41fc9e74cc86")
DECISIONS = frozenset({"reviewed", "correction_required", "rejected"})


class PaymentProofAccessDenied(RuntimeError):
    pass


class PaymentProofNotFound(RuntimeError):
    pass


class PaymentProofConflict(RuntimeError):
    pass


class PaymentProofInvalid(ValueError):
    pass


def payment_proof_capability() -> dict:
    try:
        PrivateEvidenceStore()
        available = True
    except EvidenceFileError:
        available = False
    return {
        "upload_available": available,
        "allowed_media_types": sorted(EVIDENCE_MEDIA_TYPES),
        "max_bytes": MAX_EVIDENCE_BYTES,
        "posts_payment": False,
        "message": (
            "Payment proofs are evidence for office review. Only official posted payments change your balance."
            if available
            else "Payment-proof uploads are unavailable. Contact the office for assistance."
        ),
    }


def _text(value: str) -> str:
    if not isinstance(value, str) or len(value) > 1000 or "\x00" in value:
        raise PaymentProofInvalid("Use a note or reason of at most 1000 characters.")
    return value.strip()


def _actor(cursor, actor_user_id, registered_device_id, management):
    if registered_device_id is None:
        raise PaymentProofAccessDenied(
            "An active registered account and device are required."
        )
    row = cursor.execute(
        """select u.id from core.users u join core.devices d on d.user_id=u.id
        where u.id=%s and u.status='active' and d.id=%s and d.status='active'
        and exists(select 1 from core.user_roles ur join core.roles r on r.id=ur.role_id
            where ur.user_id=u.id and r.code=%s and (%s=false or exists(
                select 1 from core.role_permissions rp where rp.role_id=r.id and rp.permission_code=%s)))
        for share of u,d""",
        (
            actor_user_id,
            registered_device_id,
            "management" if management else "client",
            management,
            REVIEW_PERMISSION,
        ),
    ).fetchone()
    if row is None:
        raise PaymentProofAccessDenied(
            "An active authorized account and device are required."
        )


_PROOF_QUERY = """select p.*,l.loan_number,t.name as loan_type_name,
    c.client_code,c.full_name as client_name
    from lending.client_payment_proofs p
    join lending.loans l on l.id=p.loan_id and l.client_id=p.client_id
    join lending.clients c on c.id=p.client_id
    join lending.loan_types t on t.id=l.loan_type_id
    where (%s::uuid is null or c.user_id=%s)"""


def _proof(cursor, proof_id, actor_user_id, management, *, lock=False):
    owner = None if management else actor_user_id
    row = cursor.execute(
        _PROOF_QUERY + " and p.id=%s" + (" for update of p" if lock else ""),
        (owner, owner, proof_id),
    ).fetchone()
    if row is None:
        raise PaymentProofNotFound("Payment proof was not found.")
    return row


def _version_payload(row):
    return {
        "version_id": str(row["id"]),
        "version_number": row["version_number"],
        "media_type": row["media_type"],
        "byte_count": row["byte_count"],
        "sha256": row["content_sha256"],
        "uploaded_at": row["uploaded_at"].isoformat(),
        "note": row["note"],
    }


def _review_payload(row):
    return {
        "review_id": str(row["id"]),
        "decision": row["decision"],
        "reason": row["reason"],
        "reviewed_at": row["reviewed_at"].isoformat(),
    }


def _details(cursor, proofs, management, *, history=False):
    if not proofs:
        return []
    versions = cursor.execute(
        "select "
        + ("" if history else "distinct on (proof_id) ")
        + "* from lending.client_payment_proof_versions where proof_id=any(%s) order by proof_id,version_number desc",
        ([row["id"] for row in proofs],),
    ).fetchall()
    reviews = cursor.execute(
        "select "
        + ("" if history else "distinct on (version_id) ")
        + "* from lending.client_payment_proof_reviews where version_id=any(%s) order by version_id,review_number desc",
        ([row["id"] for row in versions],),
    ).fetchall()
    available = payment_proof_capability()["upload_available"]
    result = []
    for proof in proofs:
        own_versions = [row for row in versions if row["proof_id"] == proof["id"]]
        if not own_versions:
            raise PaymentProofConflict(
                "The payment proof is incomplete. Refresh the record."
            )
        version = own_versions[0]
        own_reviews = [row for row in reviews if row["version_id"] == version["id"]]
        latest = own_reviews[0] if own_reviews else None
        summary = {
            "proof_id": str(proof["id"]),
            "loan_id": str(proof["loan_id"]),
            "loan_number": proof["loan_number"],
            "loan_type_name": proof["loan_type_name"],
            "submitted_at": proof["created_at"].isoformat(),
            "status": latest["decision"] if latest else "under_review",
            "current_version": _version_payload(version),
            "latest_review": _review_payload(latest) if latest else None,
            "can_reupload": available and not management,
            "official_payment_posted": False,
        }
        if management:
            summary.update(
                client_name=proof["client_name"], client_code=proof["client_code"]
            )
        detail = {"proof": summary}
        if history:
            detail["history"] = [
                {
                    "version": _version_payload(row),
                    "reviews": [
                        _review_payload(review)
                        for review in reviews
                        if review["version_id"] == row["id"]
                    ],
                }
                for row in own_versions
            ]
        result.append(detail)
    return result


def _audit(cursor, actor, proof_id, action, details):
    cursor.execute(
        """insert into core.audit_logs(actor_user_id,action,target_type,target_id,details)
        values(%s,%s,'client_payment_proof',%s,%s)""",
        (actor, action, proof_id, Jsonb(details)),
    )


def _request_lock(cursor, request_id):
    cursor.execute(
        "select pg_advisory_xact_lock(hashtextextended(%s,0))",
        (f"client-payment-proof:{request_id}",),
    )


class PostgresClientPaymentProofRepository:
    def list_proofs(
        self,
        *,
        actor_user_id,
        registered_device_id,
        management=False,
        limit=50,
        offset=0,
    ):
        if not 1 <= limit <= 100 or not 0 <= offset <= 100000:
            raise PaymentProofInvalid("Invalid payment-proof page.")
        with (
            open_connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            _actor(cursor, actor_user_id, registered_device_id, management)
            owner = None if management else actor_user_id
            proofs = cursor.execute(
                _PROOF_QUERY
                + " order by p.created_at desc,p.id desc limit %s offset %s",
                (owner, owner, limit + 1, offset),
            ).fetchall()
            return {
                "proofs": [
                    item["proof"]
                    for item in _details(cursor, proofs[:limit], management)
                ],
                "has_more": len(proofs) > limit,
                "capability": payment_proof_capability(),
            }

    def get(self, *, actor_user_id, registered_device_id, proof_id, management=False):
        with (
            open_connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            _actor(cursor, actor_user_id, registered_device_id, management)
            row = _proof(cursor, proof_id, actor_user_id, management)
            return _details(cursor, [row], management, history=True)[0]

    def upload(
        self,
        *,
        actor_user_id,
        registered_device_id,
        request_id,
        content,
        media_type,
        note="",
        loan_id=None,
        proof_id=None,
        expected_version=None,
    ):
        note = _text(note)
        try:
            validate_evidence_content(content, media_type)
        except EvidenceFileError as error:
            raise PaymentProofInvalid(
                "Upload a PDF, PNG or JPEG file up to 10 MiB."
            ) from error
        if (proof_id is None) != (expected_version is None) or (
            proof_id is None and loan_id is None
        ):
            raise PaymentProofInvalid(
                "An owned loan or exact previous proof version is required."
            )
        digest = hashlib.sha256(content).hexdigest()
        with (
            open_connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            _actor(cursor, actor_user_id, registered_device_id, False)
            _request_lock(cursor, request_id)
            previous = cursor.execute(
                "select * from lending.client_payment_proof_versions where request_id=%s",
                (request_id,),
            ).fetchone()
            if previous:
                if (
                    previous["uploaded_by_user_id"] != actor_user_id
                    or previous["uploaded_device_id"] != registered_device_id
                ):
                    raise PaymentProofConflict(
                        "This upload request identity is already used."
                    )
                row = _proof(cursor, previous["proof_id"], actor_user_id, False)
                if (
                    previous["content_sha256"] != digest
                    or previous["media_type"] != media_type
                    or previous["byte_count"] != len(content)
                    or previous["note"] != note
                    or (
                        proof_id is None
                        and (
                            previous["version_number"] != 1 or row["loan_id"] != loan_id
                        )
                    )
                    or (
                        proof_id is not None
                        and (
                            previous["proof_id"] != proof_id
                            or previous["version_number"] != expected_version + 1
                        )
                    )
                ):
                    raise PaymentProofConflict(
                        "Keep the same file, note and target when retrying an upload."
                    )
                PrivateEvidenceStore().read(
                    previous["storage_key"], digest, len(content)
                )
                return _details(cursor, [row], False, history=True)[0]
            if proof_id is None:
                loan = cursor.execute(
                    """select l.id,l.client_id from lending.loans l join lending.clients c on c.id=l.client_id
                    where l.id=%s and c.user_id=%s and l.date_released is not null
                    and l.status not in ('draft','approved','cancelled') for share of l,c""",
                    (loan_id, actor_user_id),
                ).fetchone()
                if loan is None:
                    raise PaymentProofNotFound(
                        "A released loan belonging to this account was not found."
                    )
                proof_id = uuid5(
                    IDENTITY_NAMESPACE, f"proof:{actor_user_id}:{request_id}"
                )
                cursor.execute(
                    """insert into lending.client_payment_proofs(id,client_id,loan_id,created_by_user_id,created_device_id)
                    values(%s,%s,%s,%s,%s)""",
                    (
                        proof_id,
                        loan["client_id"],
                        loan_id,
                        actor_user_id,
                        registered_device_id,
                    ),
                )
                number = 1
                row = _proof(cursor, proof_id, actor_user_id, False, lock=True)
            else:
                row = _proof(cursor, proof_id, actor_user_id, False, lock=True)
                current = cursor.execute(
                    "select max(version_number) as number from lending.client_payment_proof_versions where proof_id=%s",
                    (proof_id,),
                ).fetchone()["number"]
                if current != expected_version:
                    raise PaymentProofConflict(
                        "The proof changed. Refresh before uploading a replacement."
                    )
                number = current + 1
            version_id = uuid5(
                IDENTITY_NAMESPACE, f"upload:{actor_user_id}:{request_id}"
            )
            try:
                PrivateEvidenceStore().put(version_id, content, media_type)
            except EvidenceFileError as error:
                if "identity is already used" in str(error):
                    raise PaymentProofConflict(
                        "This upload request identity is already used for another file."
                    ) from error
                raise
            cursor.execute(
                """insert into lending.client_payment_proof_versions(id,proof_id,version_number,request_id,note,
                media_type,content_sha256,byte_count,storage_key,uploaded_by_user_id,uploaded_device_id)
                values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    version_id,
                    proof_id,
                    number,
                    request_id,
                    note,
                    media_type,
                    digest,
                    len(content),
                    version_id,
                    actor_user_id,
                    registered_device_id,
                ),
            )
            _audit(
                cursor,
                actor_user_id,
                proof_id,
                "client_payment_proof.uploaded",
                {
                    "version_id": str(version_id),
                    "version_number": number,
                    "request_id": str(request_id),
                },
            )
            return _details(cursor, [row], False, history=True)[0]

    def content(
        self,
        *,
        actor_user_id,
        registered_device_id,
        proof_id,
        version_number,
        management=False,
    ):
        with (
            open_connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            _actor(cursor, actor_user_id, registered_device_id, management)
            _proof(cursor, proof_id, actor_user_id, management)
            row = cursor.execute(
                "select * from lending.client_payment_proof_versions where proof_id=%s and version_number=%s",
                (proof_id, version_number),
            ).fetchone()
            if row is None:
                raise PaymentProofNotFound("Payment proof was not found.")
            content = PrivateEvidenceStore().read(
                row["storage_key"], row["content_sha256"], row["byte_count"]
            )
            _audit(
                cursor,
                actor_user_id,
                proof_id,
                "client_payment_proof.downloaded",
                {"version_id": str(row["id"]), "version_number": version_number},
            )
            return _version_payload(row), content

    def review(
        self,
        *,
        actor_user_id,
        registered_device_id,
        proof_id,
        request_id,
        expected_version,
        expected_review_id,
        decision,
        reason="",
    ):
        reason = _text(reason)
        if decision not in DECISIONS or (decision != "reviewed" and not reason):
            raise PaymentProofInvalid(
                "A review decision and correction/rejection reason are required."
            )
        with (
            open_connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            _actor(cursor, actor_user_id, registered_device_id, True)
            _request_lock(cursor, request_id)
            row = _proof(cursor, proof_id, actor_user_id, True, lock=True)
            previous = cursor.execute(
                """select r.*,v.version_number from lending.client_payment_proof_reviews r
                join lending.client_payment_proof_versions v on v.id=r.version_id where r.request_id=%s""",
                (request_id,),
            ).fetchone()
            if previous:
                if (
                    previous["proof_id"] != proof_id
                    or previous["version_number"] != expected_version
                    or previous["previous_review_id"] != expected_review_id
                    or previous["decision"] != decision
                    or previous["reason"] != reason
                    or previous["reviewed_by_user_id"] != actor_user_id
                    or previous["reviewed_device_id"] != registered_device_id
                ):
                    raise PaymentProofConflict(
                        "Keep the same target and decision when retrying a review."
                    )
                return _details(cursor, [row], True, history=True)[0]
            version = cursor.execute(
                "select * from lending.client_payment_proof_versions where proof_id=%s order by version_number desc limit 1",
                (proof_id,),
            ).fetchone()
            latest = cursor.execute(
                "select * from lending.client_payment_proof_reviews where version_id=%s order by review_number desc limit 1",
                (version["id"],),
            ).fetchone()
            if (
                version["version_number"] != expected_version
                or (latest["id"] if latest else None) != expected_review_id
            ):
                raise PaymentProofConflict(
                    "The proof or review changed. Refresh before recording a decision."
                )
            # Review applies to the exact bytes that remain available, not a
            # filename, borrower claim or a missing/tampered stored artifact.
            PrivateEvidenceStore().read(
                version["storage_key"], version["content_sha256"], version["byte_count"]
            )
            review_id = uuid5(
                IDENTITY_NAMESPACE, f"review:{actor_user_id}:{request_id}"
            )
            cursor.execute(
                """insert into lending.client_payment_proof_reviews(id,proof_id,version_id,review_number,request_id,
                previous_review_id,decision,reason,reviewed_by_user_id,reviewed_device_id)
                values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    review_id,
                    proof_id,
                    version["id"],
                    latest["review_number"] + 1 if latest else 1,
                    request_id,
                    expected_review_id,
                    decision,
                    reason,
                    actor_user_id,
                    registered_device_id,
                ),
            )
            _audit(
                cursor,
                actor_user_id,
                proof_id,
                "client_payment_proof.reviewed",
                {
                    "version_id": str(version["id"]),
                    "review_id": str(review_id),
                    "decision": decision,
                },
            )
            return _details(cursor, [row], True, history=True)[0]

"""Current source authority for an exact loan payout, never release by inference."""

from uuid import UUID

from .treasury_authorization import TreasuryConflict, TreasuryDenied


def first_loan_source(conn, actor, command, *, released=False, staff_authority=True):
    from . import first_loan_repository as source
    from .first_loan_disclosure_binding import require_packet_source

    try:
        with conn.cursor() as cursor:
            if staff_authority:
                source._actor(
                    cursor,
                    actor.user_id,
                    actor.registered_device_id,
                    source.RELEASE_PERMISSION,
                )
            row = source._load(cursor, command.source_id)
            if row["packet_hash"] != command.packet_hash or (
                not released and row["loan_status"] != "approved"
            ):
                raise TreasuryConflict(
                    "The exact approved, unreleased first-loan packet is required."
                )
            require_packet_source(cursor, row=row)
            source._template(cursor, row, execution=True)
            document = source._document(cursor, row, execution=True)
            source._locked_source(cursor, row)
            authorization = source._authorization(cursor, row, command.authorization_id)
            terms = source.FirstLoanTerms.model_validate(row["packet"]["terms"])
            if not released:
                today = cursor.execute(
                    "select (clock_timestamp() at time zone 'Asia/Manila')::date as d"
                ).fetchone()["d"]
                if today != terms.schedule_basis_date:
                    raise TreasuryConflict(
                        "The signed release date changed; obtain the protected revised approval and signatures."
                    )
            witness = cursor.execute(
                "select captured_by_user_id from lending.office_review_evidence where ('office-evidence:'||id::text)=%s and subject_id=%s and purpose='borrower_contract_signed'",
                (command.contract_evidence_reference, row["id"]),
            ).fetchone()
            if witness is None:
                raise TreasuryConflict(
                    "Protected exact contract signing evidence is required."
                )
            source.require_evidence(
                cursor,
                evidence_reference=command.contract_evidence_reference,
                actor_user_id=witness["captured_by_user_id"],
                client_id=row["client_id"],
                purpose="borrower_contract_signed",
                subject_id=row["id"],
                review_snapshot=source._sign_snapshot(row, document),
            )
            return {
                "loan_id": str(row["loan_id"]),
                "client_id": str(row["client_id"]),
                "label": row["loan_number"],
                "amount": str(terms.net_cash),
                "packet_id": str(row["id"]),
                "packet_hash": row["packet_hash"],
                "authorization_id": str(authorization["id"]),
                "contract_evidence_reference": command.contract_evidence_reference,
                "schedule_basis_date": terms.schedule_basis_date.isoformat(),
                "document": document,
            }
    except source.FirstLoanAccessDenied as error:
        raise TreasuryDenied(str(error)) from error
    except (source.FirstLoanConflict, source.OfficeReviewEvidenceConflict) as error:
        raise TreasuryConflict(str(error)) from error


def renewal_source(conn, actor, command, *, released=False, staff_authority=True):
    from fastapi import HTTPException

    from .renewal_workflow_api import _authoritative_execution, _renewal_row
    from .treasury_authorization import require_live_permission
    from .treasury_repository import json_value

    if staff_authority:
        require_live_permission(conn, actor, "renewal.manage")
    try:
        with conn.cursor() as cursor:
            row = _renewal_row(cursor, request_id=command.source_id)
            if (
                row["status"] != "approved"
                or row["client_decision"] != "accepted"
                or row["office_processing_required"]
                or row["signer_readiness_status"] != "ready"
                or (not released and row["activation_status"] == "active")
                or any(
                    row[key] is not None
                    for key in (
                        "cash_released_to_collector_at",
                        "collector_cash_received_at",
                        "cash_given_to_client_at",
                        "client_cash_confirmed_at",
                    )
                )
            ):
                raise TreasuryConflict(
                    "The accepted renewal and all required signatures must be ready, without a competing cash handover."
                )
            signers = cursor.execute(
                """select id,party_role,user_id,government_id_verified_at,selfie_verified_at,signed_at
                from lending.renewal_required_signers where renewal_request_id=%s and is_required order by id for share""",
                (command.source_id,),
            ).fetchall()
            if not signers or any(
                any(
                    s[key] is None
                    for key in (
                        "user_id",
                        "government_id_verified_at",
                        "selfie_verified_at",
                        "signed_at",
                    )
                )
                for s in signers
            ):
                raise TreasuryConflict(
                    "Every required renewal signer must have independently completed verification and signing."
                )
            execution = _authoritative_execution(cursor, row=row)
            event = cursor.execute(
                """select d.* from lending.loan_disbursement_events d
                join lending.loan_renewal_execution_events e on e.disbursement_event_id=d.id
                where e.id=%s and not d.is_voided for update of d""",
                (execution["execution_id"],),
            ).fetchone()
            if (
                event is None
                or event["funding_account_system_key"] != "cash_bank_gcash"
            ):
                raise TreasuryConflict(
                    "The authoritative renewal must identify bank/GCash funding; an Office-cash source cannot be relabelled."
                )
            if cursor.execute(
                """select 1 from accounting.journal_entries where source_event_key=any(%s) limit 1""",
                (
                    [
                        "loan_disbursement:" + str(event["id"]),
                        "loan_renewal_execution:" + str(execution["execution_id"]),
                    ],
                ),
            ).fetchone():
                raise TreasuryConflict(
                    "Existing renewal journals require protected reconciliation before Treasury funding can be bound."
                )
            cursor.execute(
                "select lending.require_current_cif_for_new_credit(%s)",
                (row["client_id"],),
            )
            today = cursor.execute(
                "select (clock_timestamp() at time zone 'Asia/Manila')::date as d"
            ).fetchone()["d"]
            if not released and execution["release_date"] != today:
                raise TreasuryConflict(
                    "The authoritative renewal release date changed; review the protected source before payout."
                )
            return {
                "loan_id": str(execution["new_loan_id"]),
                "client_id": str(row["client_id"]),
                "label": row["loan_number"],
                "amount": str(execution["cash_disbursed_amount"]),
                "offset_amount": str(execution["old_loan_settlement_amount"]),
                "old_loan_id": str(row["loan_id"]),
                "execution_id": str(execution["execution_id"]),
                "disbursement_id": str(event["id"]),
                "signers": json_value(signers),
                "borrower_user_id": str(row["borrower_user_id"])
                if row["borrower_user_id"]
                else None,
                "schedule_basis_date": execution["release_date"].isoformat(),
            }
    except HTTPException as error:
        raise TreasuryConflict(
            error.detail.get("message", "The protected renewal source is unavailable.")
            if isinstance(error.detail, dict)
            else str(error.detail)
        ) from error


def current_source(conn, actor, command, *, released=False, staff_authority=True):
    if command.source_kind == "first_loan":
        result = first_loan_source(
            conn, actor, command, released=released, staff_authority=staff_authority
        )
    else:
        result = renewal_source(
            conn, actor, command, released=released, staff_authority=staff_authority
        )
    client = conn.execute(
        "select area,full_name from lending.clients where id=%s for share",
        (UUID(result["client_id"]),),
    ).fetchone()
    if client is None:
        raise TreasuryConflict("The named borrower is unavailable.")
    collector = None
    payee_name = client["full_name"]
    if command.destination == "collector":
        conn.execute(
            "select id from lending.collector_area_assignments where is_active and lending.area_path_contains(area,%s,true) order by id for share",
            (client["area"] or "",),
        ).fetchall()
        collector = conn.execute(
            "select lending.collector_area_owner(%s) as id", (client["area"] or "",)
        ).fetchone()["id"]
        active = conn.execute(
            """select u.id,u.full_name from core.users u where u.id=%s and u.status='active'
            and exists(select 1 from core.user_roles ur join core.roles r on r.id=ur.role_id
                       where ur.user_id=u.id and r.code='collector') for share of u""",
            (collector,),
        ).fetchone()
        if active is None:
            raise TreasuryConflict(
                "A current active assigned Collector is required; no recipient was chosen automatically."
            )
        payee_name = active["full_name"]
    result.update(
        payee_name=payee_name,
        collector_user_id=str(collector) if collector else None,
        payee_id=str(collector)
        if command.destination == "collector"
        else result["client_id"],
    )
    return result

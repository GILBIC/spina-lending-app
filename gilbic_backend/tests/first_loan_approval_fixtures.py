"""Explicit synthetic approval fixtures; never an autouse review or a bypass.

All new-operation fixtures record real reviewed support through the production
service. The schema-one seed exists only for historical storage/migration proof.
No value here establishes a live tax treatment, charge authority, or legal EIR.
"""

from contextlib import contextmanager
from decimal import Decimal
from uuid import UUID, uuid4


def review_for_approval(connection, monkeypatch, case):
    """Record a real synthetic review after the test has chosen its exact terms."""
    from gilbic_backend.first_loan_terms import (
        FirstLoanTerms,
        generate_first_loan_schedule,
    )
    from test_first_loan_disclosure_register_postgres import _rule
    from test_first_loan_disclosure_repository_postgres import _payload

    from gilbic_backend import first_loan_disclosure_repository as reviews

    @contextmanager
    def acquire():
        with connection.transaction():
            yield connection

    monkeypatch.setattr(reviews, "open_connection", acquire)
    case["dst_rule"] = _rule(connection, case["actor"], "documentary_stamp_tax")
    case["grt_rule"] = _rule(connection, case["actor"], "percentage_tax_lending")
    repository = reviews.PostgresFirstLoanDisclosureRepository()
    payload = _payload(connection, repository, case)
    terms = FirstLoanTerms.model_validate(case["terms"])
    assert not terms.deductions, (
        "This explicit fixture supports no borrower deductions."
    )
    rows = generate_first_loan_schedule(terms)
    total = sum((row.contractual_amount for row in rows), Decimal("0.00"))
    interest = total - terms.principal
    # Copy the existing schedule's arithmetic into synthetic reviewed evidence;
    # do not create a second pricing engine or alter an operational installment.
    payload["components"].update(
        principal=str(terms.principal),
        contractual_interest=str(interest),
        net_proceeds=str(terms.net_cash),
        total_scheduled_payable=str(total),
    )
    payload["disclosure_values"] = {
        "amount_financed": str(terms.principal),
        "amount_financed_reference": "SYNTHETIC support section 3",
        "finance_charge_total": str(interest),
        "finance_charge_reference": "SYNTHETIC support section 4",
        "non_finance_charge_total": "0.00",
        "non_finance_charge_reference": "SYNTHETIC support section 5",
        "effective_interest_rate": "20.0000",
        "effective_interest_rate_reference": "SYNTHETIC support section 6",
        "rate_period": "synthetic contract period",
        "calculation_method": "SYNTHETIC precomputed example only",
    }
    record = repository.record(
        actor_user_id=case["actor"],
        registered_device_id=case["device"],
        request=payload,
    )
    assert record["approval_ready"], record["blockers"]
    case["disclosure"] = {
        "disclosure_calculation_id": UUID(record["id"]),
        "expected_disclosure_digest": record["review_digest"],
    }
    return record


def reviewed_setup(connection, monkeypatch):
    """Opt-in only; the original shared source setup remains unchanged."""
    from test_first_loan_postgres import setup

    module, repository, case = setup(connection, monkeypatch)
    review_for_approval(connection, monkeypatch, case)
    return module, repository, case


def seed_historical_schema_one_approval(connection, case):
    """Insert an explicit old-format synthetic packet for migration retention.

    This is not a new-approval entrypoint. The guarded disposable test supplies
    the connection; no production bypass flag or old approval method is used.
    """
    from psycopg.types.json import Jsonb

    from gilbic_backend import first_loan_repository as owner

    terms = owner.FirstLoanTerms.model_validate(case["terms"])
    rows = owner.generate_first_loan_schedule(terms)
    loan_id, packet_id = uuid4(), uuid4()
    with connection.cursor() as cursor:
        app, cif, _, privacy = owner._source(cursor, case["app"].id)
        template = cursor.execute(
            "select * from lending.first_loan_document_templates where version=%s",
            (case["template"],),
        ).fetchone()
        product = cursor.execute(
            "select * from lending.loan_types where id=%s", (terms.loan_type_id,)
        ).fetchone()
        assert template is not None and product is not None
        packet = {
            "schema_version": 1,
            "packet_id": str(packet_id),
            "loan_id": str(loan_id),
            "client_id": str(app["client_id"]),
            "borrower": owner.cif_information_from_row(cif),
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
            "schedule": owner.schedule_payload(rows),
            "template": {
                "version": case["template"],
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
            "insert into lending.loans("
            "id,loan_number,client_id,loan_type_id,principal,daily_amount,"
            "interest_rate,date_released,due_date,status,created_by_user_id) "
            "values(%s,%s,%s,%s,%s,%s,%s,null,null,'approved',%s)",
            (
                loan_id,
                f"SYN-HISTORICAL-{loan_id.hex}",
                app["client_id"],
                terms.loan_type_id,
                terms.principal,
                terms.installment_amount,
                terms.interest_rate_percent,
                case["actor"],
            ),
        )
        return cursor.execute(
            "insert into lending.first_loan_approvals("
            "id,request_id,loan_id,client_id,application_version_id,cif_version_id,"
            "template_version,packet,packet_hash,approved_by_user_id,"
            "approved_device_id) "
            "values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning *",
            (
                packet_id,
                uuid4(),
                loan_id,
                app["client_id"],
                app["id"],
                cif["id"],
                case["template"],
                Jsonb(packet),
                owner.snapshot_digest(packet),
                case["actor"],
                case["device"],
            ),
        ).fetchone()

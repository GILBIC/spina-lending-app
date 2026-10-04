"""Synthetic recovery fixtures through real approval, debit and release services."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row


def seed_loan_payouts(dsn, private_root, pdf):
    from run_release_recovery_drill import DATABASE_NAME, DrillError

    params = conninfo_to_dict(dsn)
    if params.get("host") not in {
        "127.0.0.1",
        "localhost",
        "::1",
    } or not DATABASE_NAME.fullmatch(params.get("dbname", "")):
        raise DrillError(
            "Loan payout fixtures require a drill-owned loopback database."
        )
    # Reuse the same explicit reviewed/signed fixtures as the acceptance suite;
    # no schema or source-authority bypass is installed in the application.
    import pytest

    sys.path.insert(
        0, str(Path(__file__).resolve().parents[1] / "gilbic_backend/tests")
    )
    from first_loan_approval_fixtures import reviewed_setup
    from gilbic_backend.account_repository import AccountContext
    from gilbic_backend.office_review_evidence_storage import PrivateEvidenceStore
    from gilbic_backend.treasury_claims import upload_evidence
    from gilbic_backend.treasury_models import COMMAND_ADAPTER, LoanPayoutPreview
    from gilbic_backend.treasury_repository import TreasuryService
    from test_first_loan_postgres import private_fixture_configuration, ready
    from treasury_test_support import actor

    support = private_root / "loan-payout-support"
    support.mkdir()

    def connection():
        return psycopg.connect(dsn, row_factory=dict_row)

    with pytest.MonkeyPatch.context() as patch:
        private_fixture_configuration.__wrapped__(patch, support)
        patch.setenv("SPINA_TREASURY_ENABLED", "true")
        for destination in ("collector", "borrower"):
            with connection() as conn:
                _, repository, case = reviewed_setup(conn, patch)
                approved, release = ready(repository, case)
                collector = actor(conn, "collector")
                area = "SYNTHETIC-RECOVERY-PAYOUT-" + uuid4().hex
                conn.execute(
                    "update lending.clients set area=%s where id=%s",
                    (area, case["client"]),
                )
                conn.execute(
                    "insert into lending.collector_area_assignments(collector_user_id,area) values(%s,%s)",
                    (collector.user_id, area),
                )
                conn.commit()
                owner = AccountContext(
                    case["actor"],
                    case["actor"],
                    "synthetic",
                    None,
                    "Synthetic recovery owner",
                    "active",
                    ("management",),
                    (),
                    True,
                    case["device"],
                )
                patch.setenv("SPINA_EMPLOYEE_OWNER_USER_ID", str(owner.user_id))
                service = TreasuryService(
                    connection, PrivateEvidenceStore(private_root)
                )
                account, context = uuid4(), uuid4()

                def version(target=account):
                    with connection() as current:
                        return current.execute(
                            "select version from treasury.accounts where id=%s",
                            (target,),
                        ).fetchone()["version"]

                def run(
                    action, service=service, owner=owner, account=account, **fields
                ):
                    return service.execute(
                        owner,
                        COMMAND_ADAPTER.validate_python(
                            {
                                "action": action,
                                "request_id": uuid4(),
                                "account_id": account,
                                "expected_version": 0
                                if action == "account_configure"
                                else version(),
                                **fields,
                            }
                        ),
                    )

                def evidence(service=service, owner=owner, account=account):
                    return upload_evidence(
                        service,
                        owner,
                        uuid4(),
                        account,
                        "recipient",
                        pdf,
                        "application/pdf",
                    )["target_id"]

                run(
                    "account_configure",
                    ledger_context_id=context,
                    context="synthetic",
                    kind="gcash",
                    alias="Synthetic payout recovery",
                    ownership="synthetic",
                    custodian_user_id=owner.user_id,
                )
                source = {
                    "source_kind": "first_loan",
                    "source_id": approved["loan_id"],
                    "destination": destination,
                    "recipient_reference": "SYNTHETIC RECOVERY DESTINATION",
                    "authorization_id": release["authorization_id"],
                    "packet_hash": approved["packet_hash"],
                    "contract_evidence_reference": release[
                        "contract_evidence_reference"
                    ],
                }
                preview = service.loan_payout_preview(
                    owner,
                    LoanPayoutPreview(
                        account_id=account, expected_version=version(), **source
                    ),
                )
                prepared = run(
                    "loan_payout_prepare",
                    source_digest=preview["source_digest"],
                    **source,
                )
                payout = prepared["target_id"]
                debit = run(
                    "disbursement_record",
                    amount="1000.00",
                    provider="gcash",
                    reference="SYNTHETIC-RECOVERY-" + uuid4().hex,
                    effective_at=datetime.now(timezone.utc) - timedelta(seconds=2),
                    evidence_id=evidence(),
                    recipient_attestation="Synthetic exact debit",
                    purpose="loan_release",
                    source_id=payout,
                    source_version=1,
                    payee_id=collector.user_id
                    if destination == "collector"
                    else case["client"],
                    reason="Synthetic recovery debit",
                )
                if (
                    debit["result"]["source_link"]["status"]
                    != "funded_pending_recipient"
                ):
                    raise DrillError(
                        "Recovery fixture failed to bind its protected payout."
                    )
                run(
                    "loan_payout_recipient_confirm",
                    payout_id=payout,
                    payout_version=2,
                    evidence_id=evidence(),
                    reviewed_amount="1000.00",
                    received=True,
                    acknowledged_at=datetime.now(timezone.utc) - timedelta(seconds=1),
                    recipient_attestation="Synthetic actual recipient receipt",
                )
                complete = run(
                    "loan_payout_first_loan_complete",
                    payout_id=payout,
                    payout_version=3,
                    evidence_id=evidence(),
                    reviewed_amount="1000.00",
                    borrower_confirmed=True,
                    receipt_method="cash" if destination == "collector" else "gcash",
                    acknowledged_at=datetime.now(timezone.utc),
                    borrower_attestation="Synthetic Office-witnessed borrower handover",
                )
                if complete["result"]["payout"]["status"] != "completed":
                    raise DrillError(
                        "Recovery fixture did not complete its protected source."
                    )

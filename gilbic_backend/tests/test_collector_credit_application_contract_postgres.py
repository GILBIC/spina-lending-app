"""Export actual synthetic service responses for both client contract verifiers."""

import json
import os
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest
from gilbic_backend.collector_settlement import preview, source_snapshot
from gilbic_backend.treasury_authorization import TreasuryDenied
from gilbic_backend.treasury_models import COMMAND_ADAPTER, SettlementPreview
from gilbic_backend.treasury_repository import json_value
from test_collector_credit_application_postgres import (
    collector_accounting as _collector_accounting,
)
from test_collector_credit_application_postgres import (
    credit_application as _credit_application,
)

collector_accounting = _collector_accounting
credit_application = _credit_application


@pytest.mark.parametrize(
    ("credit_application", "physical", "applied"),
    [("10.00", "98.00", "4.00"), ("100.00", "0.00", "100.00")],
    indirect=["credit_application"],
)
def test_actual_application_service_contract(
    credit_application, monkeypatch, physical, applied
):
    f = credit_application
    monkeypatch.setenv("SPINA_TREASURY_ENABLED", "true")

    @contextmanager
    def borrowed():
        yield f["conn"]

    monkeypatch.setattr(f["service"], "connect", borrowed)
    examples = []

    def send(tag, who=None, reference=None, records=None, **fields):
        account = (
            f["conn"]
            .execute("SELECT * FROM treasury.accounts WHERE id=%s", (f["wallet"],))
            .fetchone()
        )
        actor = who or f["actor"]
        model = COMMAND_ADAPTER.validate_python(
            {
                "action": tag,
                "request_id": uuid4(),
                **(
                    {"account_id": f["wallet"], "expected_version": account["version"]}
                    if who is None
                    else {}
                ),
                **fields,
            }
        )
        result = f["service"].execute(actor, model)
        assert f["service"].execute(actor, model) == result
        if reference is not None:
            examples.append(
                json_value(
                    {
                        "command": model.model_dump(mode="json"),
                        "response": result,
                        "reference": reference,
                        "records": records or {},
                        "actor": {
                            "user_id": actor.user_id,
                            "device_id": actor.registered_device_id,
                        },
                        "account_id": f["wallet"],
                        "ledger_context_id": f["context"],
                        "collector_user_id": f["collector"].user_id,
                    }
                )
            )
        return result["result"]

    credit = f["credit"]
    digest = source_snapshot(f["conn"], f["later"])[2]
    request = send(
        "collector_surplus_application_request",
        who=f["collector"],
        credit_id=credit["id"],
        credit_version=credit["version"],
        remittance_id=f["later"],
        source_digest=digest,
        amount=applied,
        reason="Apply my retained credit to this exact later obligation",
    )["request"]
    approval = send(
        "collector_surplus_application_prepare",
        reference=credit,
        records={"credit": credit, "request": request},
        credit_id=credit["id"],
        credit_version=credit["version"],
        collector_request_id=request["id"],
        collector_request_version=request["version"],
        remittance_id=f["later"],
        source_digest=digest,
        amount=applied,
        evidence_id=f["evidence"],
        reason="Independent exact approval for this synthetic count",
    )["action_record"]
    account = (
        f["conn"]
        .execute("SELECT * FROM treasury.accounts WHERE id=%s", (f["wallet"],))
        .fetchone()
    )
    reviewed = preview(
        f["service"],
        f["conn"],
        f["actor"],
        f["later"],
        SettlementPreview(
            account_id=f["wallet"],
            expected_version=account["version"],
            credit_application_id=approval["id"],
            credit_application_version=approval["version"],
        ),
    )
    count = send(
        "collector_count_record",
        reference=reviewed,
        records={"count_review": reviewed},
        remittance_id=f["later"],
        source_digest=reviewed["source_digest"],
        counted_amount=physical,
        counted_at=f["service"].clock(),
        evidence_id=f["evidence"],
        recipient_attestation="Synthetic physical count separate from liability consumed",
        review_acknowledged=True,
        credit_application_id=approval["id"],
        credit_application_version=approval["version"],
    )["count"]
    result = send(
        "collector_count_accept",
        reference=count,
        records={"count": count},
        count_id=count["id"],
        count_version=count["version"],
        source_digest=count["source_digest"],
        physical_receipt_acknowledged=True,
        credit_application_id=approval["id"],
        credit_application_version=approval["version"],
    )
    assert result["settlement"]["physical_amount"] == physical
    assert result["settlement"]["authorized_credit_amount"] == applied
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")
    f["conn"].execute(
        "UPDATE treasury.account_access SET private_history=false WHERE account_id=%s",
        (f["wallet"],),
    )
    with pytest.raises(TreasuryDenied), f["conn"].transaction():
        f["service"].execute(
            f["actor"], COMMAND_ADAPTER.validate_python(examples[0]["command"])
        )
    destination = os.getenv("ACCOUNTING_COLLECTOR_CREDIT_CONTRACT_DIRECTORY")
    if destination:
        path = Path(destination) / f"application-{physical}.json"
        path.write_text(
            json.dumps({"synthetic": True, "examples": examples}, indent=2) + "\n",
            encoding="utf-8",
        )

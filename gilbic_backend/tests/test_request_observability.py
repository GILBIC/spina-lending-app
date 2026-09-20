from __future__ import annotations

import json
import logging
import re

from fastapi.testclient import TestClient
from gilbic_backend.main import create_app


def test_request_trace_is_server_generated_and_does_not_log_private_input(caplog):
    app = create_app()

    @app.get("/test/borrowers/{borrower_id}")
    def borrower(borrower_id: str):
        return {"ok": bool(borrower_id)}

    with caplog.at_level(logging.INFO, logger="gilbic.request"):
        response = TestClient(app).get(
            "/test/borrowers/private-person?token=private-query",
            headers={
                "Authorization": "Bearer private-token",
                "X-Device-Id": "private-device",
                "X-Request-ID": "private-injected-id",
            },
        )
    assert response.status_code == 200
    request_id = response.headers.get("X-Request-ID", "")
    assert re.fullmatch(r"[a-f0-9]{32}", request_id)
    messages = [r.message for r in caplog.records if r.name == "gilbic.request"]
    assert len(messages) == 1
    assert "private-" not in messages[0]
    record = json.loads(messages[0])
    assert record["request_id"] == request_id
    assert record["route"] == "/test/borrowers/{borrower_id}"
    assert record["method"] == "GET"
    assert record["status"] == 200
    assert record["completed"] is True
    assert record["duration_ms"] >= 0


def test_unmatched_request_does_not_log_raw_path(caplog):
    with caplog.at_level(logging.INFO, logger="gilbic.request"):
        response = TestClient(create_app()).get("/private-secret-in-path")
    assert response.status_code == 404
    messages = [r.message for r in caplog.records if r.name == "gilbic.request"]
    assert len(messages) == 1
    assert "private-secret" not in messages[0]
    assert json.loads(messages[0])["route"] == "unmatched"


def test_failed_request_reports_failure_without_exception_contents(caplog):
    app = create_app()

    @app.get("/test/failure")
    def fail():
        raise ValueError("private-connection-password")

    with caplog.at_level(logging.INFO, logger="gilbic.request"):
        response = TestClient(app, raise_server_exceptions=False).get("/test/failure")
    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    request_id = response.headers.get("X-Request-ID", "")
    assert re.fullmatch(r"[a-f0-9]{32}", request_id)
    messages = [r.message for r in caplog.records if r.name == "gilbic.request"]
    assert len(messages) == 1
    assert "private-connection" not in messages[0]
    record = json.loads(messages[0])
    assert record["status"] == 500
    assert record["request_id"] == request_id
    assert record["completed"] is False


def test_trace_ids_are_distinct_and_health_contract_is_preserved():
    client = TestClient(create_app())
    first = client.get("/health/live")
    second = client.get("/health/live")
    assert first.json() == {"status": "ok", "service": "gilbic-backend"}
    assert first.headers.get("X-Request-ID")
    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]

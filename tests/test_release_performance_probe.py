"""Real local HTTP traffic, with synthetic credentials and no hosted services."""

from __future__ import annotations

import importlib.util
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools/run_release_performance_probe.py"


def module():
    assert TOOL.is_file(), "bounded loopback performance probe is not implemented"
    specification = importlib.util.spec_from_file_location("performance_probe", TOOL)
    assert specification is not None and specification.loader is not None
    result = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(result)
    return result


def configuration(*scenarios):
    return {
        "schema_version": 1,
        "template_only": False,
        "synthetic_workload": {
            "synthetic": True,
            "label": "isolated-test-fixture",
            "clients": 10,
            "active_loans": 10,
            "route_entries": 10,
            "collectors": 3,
            "employees": 3,
        },
        "scenarios": list(scenarios),
    }


def scenario(name="health", path="/health/live", credential="none", status=200):
    return {
        "name": name,
        "path": path,
        "credential": credential,
        "expected_status": status,
    }


@pytest.fixture
def local_server():
    state = {"active": 0, "maximum_active": 0, "requests": [], "target_requests": 0}
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_arguments):
            pass

        def do_GET(self):
            with lock:
                state["active"] += 1
                state["maximum_active"] = max(state["maximum_active"], state["active"])
                state["requests"].append((self.path, self.headers.get("Authorization")))
            try:
                time.sleep(0.02)
                status = 200
                if self.path == "/api/v1/management/dashboard-overview":
                    status = 403
                elif self.path == "/health/ready":
                    status = 302
                elif self.path == "/api/v1/auth/me":
                    status = 503
                self.send_response(status)
                if status == 302:
                    self.send_header(
                        "Location", "/redirect-must-not-be-followed?secret=private"
                    )
                if self.path.startswith("/redirect-must-not-be-followed"):
                    state["target_requests"] += 1
                self.end_headers()
                if self.path == "/api/v1/client/loans":
                    for _ in range(5):
                        self.wfile.write(b" ")
                        self.wfile.flush()
                        time.sleep(0.08)
                elif self.path == "/api/v1/employee-operations/workspace":
                    self.wfile.write(b"x" * 1024)
                else:
                    self.wfile.write(b'{"private":"response-body-must-not-leak"}')
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                with lock:
                    state["active"] -= 1

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def run(probe, origin, config, **overrides):
    values = {
        "allow_disposable": True,
        "requests_per_scenario": 4,
        "concurrency": 3,
        "timeout_seconds": 1,
        "credentials": {
            "employee": {"token": "test-private-token", "device_id": "test-device"}
        },
    }
    values.update(overrides)
    return probe.run_probe(origin, config, **values)


def test_real_http_concurrency_counts_expected_denial_and_sanitized_result(
    local_server,
):
    probe = module()
    origin, state = local_server
    report = run(
        probe,
        origin,
        configuration(
            scenario(),
            scenario(
                "denied", "/api/v1/management/dashboard-overview", "employee", 403
            ),
        ),
    )
    assert len(state["requests"]) == 8
    assert 1 < state["maximum_active"] <= 3
    assert report["completed_requests"] == 8
    assert report["outcome"] == "measured"
    assert report["threshold_assessment"] == "not_evaluated"
    assert report["production_acceptance"] is False
    assert len(report["source_commit"]) == 40
    assert report["synthetic_workload"]["clients"] == 10
    assert report["scenarios"][1]["status_counts"] == {"403": 4}
    for record in report["scenarios"]:
        assert record["error_counts"] == {}
        assert 0 <= record["p50_ms"] <= record["p95_ms"] <= record["max_ms"]
    rendered = json.dumps(report)
    assert "test-private-token" not in rendered
    assert "test-device" not in rendered
    assert "response-body-must-not-leak" not in rendered
    assert all(
        header is None for path, header in state["requests"] if path == "/health/live"
    )


def test_redirect_and_unexpected_status_are_errors_without_following(local_server):
    probe = module()
    origin, state = local_server
    report = run(
        probe,
        origin,
        configuration(
            scenario("redirect", "/health/ready"),
            scenario("unavailable", "/api/v1/auth/me"),
        ),
    )
    assert report["outcome"] == "request_errors"
    assert report["scenarios"][0]["error_counts"] == {"redirect_refused": 4}
    assert report["scenarios"][1]["error_counts"] == {"unexpected_status": 4}
    assert state["target_requests"] == 0
    assert "secret=private" not in json.dumps(report)


@pytest.mark.parametrize(
    "origin",
    [
        "https://example.com",
        "http://localhost:8000",
        "http://127.0.0.1.evil.test",
        "http://0.0.0.0",
        "file:///tmp/local",
        "http://private-user:private-password@127.0.0.1",
        "http://127.0.0.1/private",
        "http://127.0.0.1?token=private",
        "http://127.0.0.1#private",
        "http://[::ffff:127.0.0.1]",
    ],
)
def test_unsafe_origin_is_rejected_without_echoing_input(origin):
    probe = module()
    with pytest.raises(ValueError) as failure:
        run(probe, origin, configuration(scenario()))
    assert "private" not in str(failure.value)


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/employee-operations/actions",
        "/api/v1/collector/routes/today",
        "/health/live?token=x",
        "//evil.test",
        "/health/live/../ready",
    ],
)
def test_route_allowlist_refuses_arbitrary_paths(path):
    with pytest.raises(ValueError):
        run(module(), "http://127.0.0.1:1", configuration(scenario(path=path)))


@pytest.mark.parametrize(
    "overrides",
    [
        {"allow_disposable": False},
        {"concurrency": 0},
        {"concurrency": 9},
        {"requests_per_scenario": 0},
        {"requests_per_scenario": 101},
        {"timeout_seconds": 0},
        {"timeout_seconds": 11},
        {"timeout_seconds": float("nan")},
    ],
)
def test_explicit_permission_and_hard_bounds(overrides):
    with pytest.raises(ValueError):
        run(module(), "http://127.0.0.1:1", configuration(scenario()), **overrides)


def test_template_and_missing_auth_cannot_be_reported_as_measurements():
    probe = module()
    template = configuration(scenario())
    template["template_only"] = True
    with pytest.raises(ValueError):
        run(probe, "http://127.0.0.1:1", template)
    with pytest.raises(ValueError):
        run(
            probe,
            "http://127.0.0.1:1",
            configuration(
                scenario(
                    "employee", "/api/v1/employee-operations/workspace", "employee"
                )
            ),
            credentials={},
        )


def test_thresholds_are_explicit_and_do_not_claim_production_acceptance(local_server):
    probe = module()
    origin, _state = local_server
    report = run(
        probe, origin, configuration(scenario()), max_p95_ms=0.001, max_error_rate=0
    )
    assert report["threshold_assessment"] == "exceeded"
    assert report["outcome"] == "threshold_exceeded"
    assert report["production_acceptance"] is False


def test_whole_request_deadline_stops_a_trickling_response(local_server):
    origin, _state = local_server
    report = run(
        module(),
        origin,
        configuration(scenario("slow", "/api/v1/client/loans")),
        requests_per_scenario=1,
        timeout_seconds=0.12,
    )
    assert report["scenarios"][0]["error_counts"] == {"timeout": 1}
    assert report["scenarios"][0]["status_counts"] == {"200": 1}
    assert report["scenarios"][0]["max_ms"] < 350


def test_response_body_limit_is_counted_without_recording_body(local_server):
    probe = module()
    probe.MAX_RESPONSE_BYTES = 64
    origin, _state = local_server
    report = run(
        probe,
        origin,
        configuration(scenario("large", "/api/v1/employee-operations/workspace")),
        requests_per_scenario=1,
    )
    assert report["scenarios"][0]["error_counts"] == {"response_too_large": 1}
    assert "xxxx" not in json.dumps(report)


def test_total_request_limit_and_mutating_scenario_fields_are_rejected():
    probe = module()
    with pytest.raises(ValueError):
        run(
            probe,
            "http://127.0.0.1:1",
            configuration(*(scenario(f"health_{index}") for index in range(8))),
            requests_per_scenario=40,
        )
    invalid = scenario()
    invalid["method"] = "POST"
    with pytest.raises(ValueError):
        run(probe, "http://127.0.0.1:1", configuration(invalid))


def test_cli_reads_private_token_file_and_never_emits_its_contents(
    tmp_path, local_server, capsys
):
    probe = module()
    origin, _state = local_server
    config = tmp_path / "scenarios.json"
    config.write_text(
        json.dumps(
            configuration(
                scenario(
                    "denied", "/api/v1/management/dashboard-overview", "employee", 403
                )
            )
        ),
        encoding="utf-8",
    )
    tokens = tmp_path / "tokens.json"
    tokens.write_text(
        json.dumps(
            {
                "employee": {
                    "token": "private-cli-token",
                    "device_id": "private-cli-device",
                }
            }
        ),
        encoding="utf-8",
    )
    tokens.chmod(0o600)
    output = tmp_path / "result.json"
    status = probe.main(
        [
            "--base-url",
            origin,
            "--scenarios",
            str(config),
            "--token-file",
            str(tokens),
            "--output",
            str(output),
            "--allow-disposable",
            "--requests",
            "2",
        ]
    )
    assert status == 0
    captured = capsys.readouterr()
    rendered = captured.out + captured.err + output.read_text(encoding="utf-8")
    assert "private-cli" not in rendered
    assert "response-body-must-not-leak" not in rendered


def test_invalid_private_file_is_reported_without_parse_error_or_secret(
    tmp_path, capsys
):
    probe = module()
    config = tmp_path / "scenarios.json"
    config.write_text(json.dumps(configuration(scenario())), encoding="utf-8")
    tokens = tmp_path / "tokens.json"
    tokens.write_text('{"private-secret": invalid}', encoding="utf-8")
    tokens.chmod(0o600)
    status = probe.main(
        [
            "--base-url",
            "http://127.0.0.1:1",
            "--scenarios",
            str(config),
            "--token-file",
            str(tokens),
            "--output",
            str(tmp_path / "result.json"),
            "--allow-disposable",
        ]
    )
    assert status == 2
    captured = capsys.readouterr()
    assert "private-secret" not in captured.out + captured.err

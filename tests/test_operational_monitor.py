"""Operational alerts must fail closed and never expose private journal text."""

import importlib.util
import json
import ssl
from pathlib import Path
from types import SimpleNamespace

PATH = Path(__file__).resolve().parents[1] / "tools/check_operational_health.py"


def module():
    assert PATH.exists(), "Operational monitor is missing"
    spec = importlib.util.spec_from_file_location("monitor", PATH)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_missing_stale_future_or_malformed_backup_is_an_alert(tmp_path):
    monitor = module()
    stamp = tmp_path / "last-success"
    assert not monitor.backup_fresh(stamp, now=1000, maximum_age=100)
    for value in ("899", "1001", "private-invalid-input"):
        stamp.write_text(value)
        assert not monitor.backup_fresh(stamp, now=1000, maximum_age=100)
    stamp.write_text("950")
    assert monitor.backup_fresh(stamp, now=1000, maximum_age=100)


def test_journal_counts_only_structured_request_events_without_raw_text():
    monitor = module()
    records = [
        {"MESSAGE": json.dumps({"event": "http_request", "status": 200})},
        {"MESSAGE": json.dumps({"event": "http_request", "status": 503})},
        {"MESSAGE": "credential and customer payload must never appear in report"},
    ]
    assert monitor.error_counts("\n".join(map(json.dumps, records))) == (2, 1)


def test_failed_delivery_is_retried_and_not_recorded_as_notified(tmp_path, monkeypatch):
    monitor = module()
    state = tmp_path / "alert-state.json"
    monkeypatch.setattr(
        monitor,
        "send_alert",
        lambda failures: (_ for _ in ()).throw(RuntimeError("secret")),
    )
    assert monitor.notify(["readiness"], state, now=1000) is False
    assert not state.exists()


def test_unchanged_alert_cooldown_and_recovery_delivery(tmp_path, monkeypatch):
    monitor = module()
    state = tmp_path / "alert-state.json"
    deliveries = []
    monkeypatch.setattr(
        monitor, "send_alert", lambda failures: deliveries.append(list(failures))
    )
    assert monitor.notify(["readiness"], state, now=1000)
    assert monitor.notify(["readiness"], state, now=1010)
    assert monitor.notify([], state, now=1020)
    assert deliveries == [["readiness"], []]


def test_tls_failure_prevents_authentication_or_delivery(monkeypatch):
    monitor = module()
    for key, value in {
        "SPINA_ALERT_ENABLED": "yes",
        "SPINA_ALERT_FROM": "test@example.invalid",
        "SPINA_ALERT_TO": "test@example.invalid",
        "SPINA_ALERT_SMTP_HOST": "example.invalid",
        "SPINA_ALERT_SMTP_USER": "synthetic",
        "SPINA_ALERT_SMTP_PASSWORD": "synthetic",
        "SPINA_ALERT_SMTP_MODE": "starttls",
    }.items():
        monkeypatch.setenv(key, value)
    calls = []

    class SMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def starttls(self, *, context):
            assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
            calls.append("tls")
            raise ssl.SSLCertVerificationError("synthetic invalid certificate")

        def login(self, *args):
            calls.append("login")

        def send_message(self, *args):
            calls.append("send")

    monkeypatch.setattr(monitor.smtplib, "SMTP", SMTP)
    try:
        monitor.send_alert(["test"])
    except ssl.SSLCertVerificationError:
        pass
    else:
        raise AssertionError("TLS failure must propagate")
    assert calls == ["tls"]


def test_corrupt_alert_state_does_not_prevent_delivery(tmp_path, monkeypatch):
    monitor = module()
    state = tmp_path / "alert-state.json"
    state.write_text('["invalid state shape"]')
    deliveries = []
    monkeypatch.setattr(
        monitor, "send_alert", lambda failures: deliveries.append(failures)
    )
    assert monitor.notify(["readiness"], state, now=1000)
    assert deliveries == [["readiness"]]


def test_fresh_server_backup_cannot_hide_missing_or_failed_pc_copy(
    tmp_path, monkeypatch
):
    monitor = module()
    monkeypatch.setenv("SPINA_BACKUP_STATE", str(tmp_path))
    monkeypatch.setenv("SPINA_MONITOR_PC_BACKUP_REQUIRED", "yes")
    monkeypatch.setenv(
        "SPINA_MONITOR_PUBLIC_URL", "https://example.invalid/health/ready"
    )
    monkeypatch.setattr(monitor.time, "time", lambda: 1000)
    monkeypatch.setattr(monitor, "healthy", lambda url: True)
    monkeypatch.setattr(
        monitor, "command", lambda *args: "success" if args[0] == "systemctl" else ""
    )
    monkeypatch.setattr(
        monitor.shutil, "disk_usage", lambda path: SimpleNamespace(used=1, total=10)
    )
    (tmp_path / "last-success").write_text("1000")
    assert set(monitor.checks()) == {"pc_backup_age", "pc_backup_attempt"}
    (tmp_path / "pc-last-success").write_text("1000")
    (tmp_path / "pc-last-result").write_text("success")
    assert monitor.checks() == []
    (tmp_path / "pc-last-result").write_text("failed")
    assert monitor.checks() == ["pc_backup_attempt"]

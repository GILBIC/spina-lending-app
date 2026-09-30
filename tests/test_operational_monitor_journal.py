"""Non-text journal fields must not interrupt sanitized operational alerts."""

import json
import sys
from types import SimpleNamespace

import pytest
from test_operational_monitor import module


@pytest.mark.parametrize(
    "message",
    [None, [0, 255], ["first", "second"], {}, 123, False],
    ids=["elided", "binary", "repeated", "object", "number", "boolean"],
)
def test_non_text_message_does_not_hide_later_structured_events(message):
    monitor = module()
    records = [
        {"MESSAGE": json.dumps({"event": "http_request", "status": 200})},
        {"MESSAGE": message},
        {"MESSAGE": 'INFO: {"event":"http_request","status":503}'},
        {"MESSAGE": "private unrelated journal text"},
        {"MESSAGE": json.dumps({"event": "http_request", "status": 500})},
    ]
    assert monitor.error_counts("\n".join(map(json.dumps, records))) == (3, 2)


def _host_fixture(tmp_path, monkeypatch):
    monitor = module()
    for name in tuple(monitor.os.environ):
        if name.startswith(("SPINA_MONITOR_", "SPINA_BACKUP_", "SPINA_ALERT_")):
            monkeypatch.delenv(name)
    monkeypatch.setenv("SPINA_BACKUP_STATE", str(tmp_path))
    monkeypatch.setenv("SPINA_MONITOR_STATE", str(tmp_path / "monitor"))
    monkeypatch.setenv(
        "SPINA_MONITOR_PUBLIC_URL", "https://example.invalid/health/ready"
    )
    monkeypatch.setattr(sys, "argv", ["check_operational_health.py"])
    monkeypatch.setattr(monitor.os, "umask", lambda mask: 0o077)
    monkeypatch.setattr(monitor.time, "time", lambda: 1000)
    monkeypatch.setattr(monitor, "healthy", lambda url: True)
    monkeypatch.setattr(
        monitor.shutil, "disk_usage", lambda path: SimpleNamespace(used=1, total=10)
    )
    (tmp_path / "last-success").write_text("1000")
    # journalctl may emit null for a MESSAGE larger than its JSON field limit.
    records = [{"MESSAGE": None}, {"MESSAGE": "PRIVATE-SYNTHETIC-LOG"}]
    records.extend(
        {"MESSAGE": json.dumps({"event": "http_request", "status": 503})}
        for _ in range(3)
    )

    def command(*args):
        if args[0] == "systemctl":
            return "success"
        assert args[0] == "journalctl"
        assert "--all" not in args
        return "\n".join(map(json.dumps, records))

    monkeypatch.setattr(monitor, "command", command)
    return monitor, records, tmp_path / "monitor" / "alert-state.json"


def test_null_message_preserves_error_alert_cooldown_and_recovery(
    tmp_path, monkeypatch, capsys
):
    monitor, records, state = _host_fixture(tmp_path, monkeypatch)
    deliveries = []
    monkeypatch.setattr(
        monitor, "send_alert", lambda failures: deliveries.append(list(failures))
    )
    assert monitor.main() == 1
    assert deliveries == [["server_errors"]]
    assert json.loads(capsys.readouterr().out) == {
        "failures": ["server_errors"],
        "notification_ok": True,
    }
    assert json.loads(state.read_text()) == {
        "failures": ["server_errors"],
        "notified_at": 1000,
    }
    assert monitor.main() == 1
    assert deliveries == [["server_errors"]]
    capsys.readouterr()
    records[:] = [
        {"MESSAGE": None},
        {"MESSAGE": json.dumps({"event": "http_request", "status": 200})},
    ]
    assert monitor.main() == 0
    assert deliveries == [["server_errors"], []]
    assert json.loads(capsys.readouterr().out) == {
        "failures": [],
        "notification_ok": True,
    }
    assert json.loads(state.read_text())["failures"] == []


def test_null_message_preserves_failed_delivery_retry_without_private_output(
    tmp_path, monkeypatch, capsys
):
    monitor, _, state = _host_fixture(tmp_path, monkeypatch)
    attempts = []

    def delivery(failures):
        attempts.append(list(failures))
        if len(attempts) == 1:
            raise RuntimeError("PRIVATE-SYNTHETIC-SMTP-DETAIL")

    monkeypatch.setattr(monitor, "send_alert", delivery)
    assert monitor.main() == 1
    assert not state.exists()
    assert json.loads(capsys.readouterr().out) == {
        "failures": ["server_errors"],
        "notification_ok": False,
    }
    assert monitor.main() == 1
    assert attempts == [["server_errors"], ["server_errors"]]
    assert json.loads(capsys.readouterr().out) == {
        "failures": ["server_errors"],
        "notification_ok": True,
    }
    assert json.loads(state.read_text())["failures"] == ["server_errors"]

"""Small host monitor. No customer data, credential values or raw errors leave it."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import shutil
import smtplib
import ssl
import subprocess
import time
import urllib.request
from email.message import EmailMessage
from pathlib import Path


def backup_fresh(path: Path, *, now: float, maximum_age: float) -> bool:
    try:
        return 0 <= now - int(path.read_text().strip()) <= maximum_age
    except (OSError, ValueError):
        return False


def error_counts(journal: str) -> tuple[int, int]:
    requests = errors = 0
    for line in journal.splitlines():
        try:
            message = json.loads(line)["MESSAGE"]
            event = json.loads(message[message.index("{") :])
            if (
                isinstance(event, dict)
                and event.get("event") == "http_request"
                and isinstance(event.get("status"), int)
            ):
                requests += 1
                errors += 500 <= event["status"] < 600
        except (ValueError, TypeError, KeyError):
            continue
    return requests, errors


def command(*args: str) -> str:
    result = subprocess.run(
        args, capture_output=True, text=True, timeout=15, check=True
    )
    return result.stdout


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def healthy(url: str) -> bool:
    try:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect()
        )
        with opener.open(url, timeout=5) as response:
            return response.status == 200
    except (OSError, ValueError, http.client.HTTPException):
        return False


def checks() -> list[str]:
    failures = []
    state = Path(os.environ.get("SPINA_BACKUP_STATE", "/var/lib/spina-backup"))
    maintenance = backup_fresh(state / "api-paused", now=time.time(), maximum_age=600)
    for label, url in (
        ("liveness", "http://127.0.0.1:8000/health/live"),
        ("readiness", "http://127.0.0.1:8000/health/ready"),
        ("public_https", os.environ["SPINA_MONITOR_PUBLIC_URL"]),
    ):
        if label == "public_https" and not url.startswith("https://"):
            failures.append("public_https_configuration")
        elif not maintenance and not healthy(url):
            failures.append(label)
    for service in ("spina-api", "caddy"):
        if maintenance and service == "spina-api":
            continue
        try:
            command("systemctl", "is-active", "--quiet", service)
        except (OSError, subprocess.SubprocessError):
            failures.append(service)
    disk = shutil.disk_usage("/")
    if disk.used / disk.total * 100 >= float(
        os.environ.get("SPINA_MONITOR_DISK_PERCENT", "85")
    ):
        failures.append("disk")
    if not backup_fresh(
        state / "last-success",
        now=time.time(),
        maximum_age=float(os.environ.get("SPINA_MONITOR_BACKUP_MAX_HOURS", "30"))
        * 3600,
    ):
        failures.append("backup_age")
    if os.environ.get("SPINA_MONITOR_PC_BACKUP_REQUIRED") == "yes":
        if not backup_fresh(
            state / "pc-last-success",
            now=time.time(),
            maximum_age=float(os.environ.get("SPINA_MONITOR_BACKUP_MAX_HOURS", "30"))
            * 3600,
        ):
            failures.append("pc_backup_age")
        try:
            if (state / "pc-last-result").read_text().strip() != "success":
                failures.append("pc_backup_attempt")
        except OSError:
            failures.append("pc_backup_attempt")
    for unit, label in (
        ("spina-backup.service", "backup_attempt"),
        ("spina-backup-check.service", "backup_integrity"),
    ):
        try:
            if (
                command(
                    "systemctl", "show", unit, "--property=Result", "--value"
                ).strip()
                != "success"
            ):
                failures.append(label)
        except (OSError, subprocess.SubprocessError):
            failures.append(label)
    try:
        count, errors = error_counts(
            command(
                "journalctl",
                "-u",
                "spina-api",
                "--since",
                "5 minutes ago",
                "-n",
                "10000",
                "-o",
                "json",
                "--no-pager",
            )
        )
        if errors >= int(
            os.environ.get("SPINA_MONITOR_5XX_COUNT", "3")
        ) and errors / max(1, count) >= float(
            os.environ.get("SPINA_MONITOR_5XX_RATE", "0.05")
        ):
            failures.append("server_errors")
    except (OSError, subprocess.SubprocessError):
        failures.append("request_log_probe")
    return sorted(failures)


def send_alert(failures: list[str]) -> None:
    if os.environ.get("SPINA_ALERT_ENABLED") != "yes":
        raise RuntimeError("Alert delivery is not configured")
    message = EmailMessage()
    message["From"] = os.environ["SPINA_ALERT_FROM"]
    message["To"] = os.environ["SPINA_ALERT_TO"]
    message["Subject"] = "Spina operations: " + (
        "attention required" if failures else "recovered"
    )
    message.set_content(
        "Checks requiring attention: "
        + (", ".join(failures) or "none; previous checks recovered")
    )
    host = os.environ["SPINA_ALERT_SMTP_HOST"]
    mode = os.environ.get("SPINA_ALERT_SMTP_MODE", "starttls")
    port = int(
        os.environ.get("SPINA_ALERT_SMTP_PORT", "465" if mode == "ssl" else "587")
    )
    context = ssl.create_default_context()
    if mode not in {"ssl", "starttls"}:
        raise ValueError("TLS is required")
    connection = (
        smtplib.SMTP_SSL(host, port, timeout=10, context=context)
        if mode == "ssl"
        else smtplib.SMTP(host, port, timeout=10)
    )
    with connection as smtp:
        if mode == "starttls":
            smtp.starttls(context=context)
        smtp.login(
            os.environ["SPINA_ALERT_SMTP_USER"], os.environ["SPINA_ALERT_SMTP_PASSWORD"]
        )
        smtp.send_message(message)


def notify(failures: list[str], state: Path, *, now: float) -> bool:
    try:
        previous = json.loads(state.read_text())
        if (
            not isinstance(previous, dict)
            or not isinstance(previous.get("failures"), list)
            or not isinstance(previous.get("notified_at"), (int, float))
        ):
            raise TypeError("Invalid notification state")
        if not 0 <= previous["notified_at"] <= now:
            raise ValueError("Invalid notification timestamp")
    except (OSError, ValueError, TypeError):
        previous = {"failures": [], "notified_at": 0}
    changed = failures != previous.get("failures")
    repeat_due = failures and now - previous.get("notified_at", 0) >= 3600
    if not changed and not repeat_due:
        return True
    try:
        send_alert(failures)
        state.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = state.with_suffix(".new")
        temporary.write_text(json.dumps({"failures": failures, "notified_at": now}))
        temporary.replace(state)
        return True
    except (OSError, ValueError, KeyError, RuntimeError, smtplib.SMTPException):
        # Do not suppress future attempts after a delivery failure.
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-alert", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.test_alert:
            send_alert(["operator_requested_delivery_test"])
            print(
                json.dumps(
                    {"delivery": "smtp_accepted", "recipient_receipt_verified": False}
                )
            )
            return 0
        failures = checks()
        state = (
            Path(os.environ.get("SPINA_MONITOR_STATE", "/var/lib/spina-monitor"))
            / "alert-state.json"
        )
        delivered = notify(failures, state, now=time.time())
        print(json.dumps({"failures": failures, "notification_ok": delivered}))
        return int(bool(failures) or not delivered)
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        RuntimeError,
        smtplib.SMTPException,
    ):
        print(
            json.dumps(
                {
                    "failures": ["monitor_configuration_or_execution"],
                    "notification_ok": False,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

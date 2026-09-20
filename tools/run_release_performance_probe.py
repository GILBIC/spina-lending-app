"""Bounded GET measurements against an explicitly authorized loopback fixture."""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import math
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_PATHS = frozenset(
    {
        "/health/live",
        "/health/ready",
        "/api/v1/auth/me",
        "/api/v1/client/loans",
        "/api/v1/collector/cash-accountability",
        "/api/v1/employee-operations/workspace",
        "/api/v1/management/dashboard-overview",
    }
)
CREDENTIAL_NAMES = frozenset(
    {"client", "collector", "employee", "management", "revoked"}
)
WORKLOAD_COUNTS = frozenset(
    {"clients", "active_loans", "route_entries", "collectors", "employees"}
)
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_TOTAL_REQUESTS = 300


def loopback_origin(value: str) -> str:
    try:
        if not isinstance(value, str) or any(
            ord(char) <= 32 or char == "\\" for char in value
        ):
            raise ValueError
        parsed = urlsplit(value)
        address = ipaddress.ip_address(parsed.hostname or "")
        port = parsed.port
        if (
            parsed.scheme not in {"http", "https"}
            or not address.is_loopback
            or (address.version == 6 and str(address) != "::1")
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or "?" in value
            or "#" in value
            or (port is not None and not 1 <= port <= 65535)
        ):
            raise ValueError
        host = f"[{address}]" if address.version == 6 else str(address)
        return f"{parsed.scheme}://{host}" + (f":{port}" if port is not None else "")
    except (ValueError, TypeError, AttributeError):
        raise ValueError(
            "An explicit HTTP(S) loopback IP origin without credentials or path is required."
        ) from None


def _integer(value, low: int, high: int, label: str) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{label} is outside the allowed integer bounds.")
    return value


def _finite(
    value, low: float, high: float, label: str, *, inclusive_low=False
) -> float:
    if type(value) not in {int, float} or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number.")
    if not (low <= value <= high if inclusive_low else low < value <= high):
        raise ValueError(f"{label} is outside the allowed bounds.")
    return float(value)


def validate_configuration(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "template_only",
        "synthetic_workload",
        "scenarios",
    }:
        raise ValueError("The scenario document has unsupported fields.")
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["template_only"] is not False
    ):
        raise ValueError(
            "A completed version-1 synthetic scenario document is required; templates cannot run."
        )
    workload = value["synthetic_workload"]
    if not isinstance(workload, dict) or set(workload) != {
        "synthetic",
        "label",
        *WORKLOAD_COUNTS,
    }:
        raise ValueError("Declare the synthetic workload and its fixture counts.")
    if (
        workload["synthetic"] is not True
        or not isinstance(workload["label"], str)
        or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", workload["label"])
    ):
        raise ValueError(
            "A synthetic workload with a non-sensitive identifier is required."
        )
    for key in WORKLOAD_COUNTS:
        _integer(workload[key], 0, 2_000_000, "Synthetic fixture count")
    scenarios = value["scenarios"]
    if not isinstance(scenarios, list) or not 1 <= len(scenarios) <= 8:
        raise ValueError("One to eight read scenarios are required.")
    names = set()
    for scenario in scenarios:
        if not isinstance(scenario, dict) or set(scenario) != {
            "name",
            "path",
            "credential",
            "expected_status",
        }:
            raise ValueError(
                "A scenario contains unsupported fields; only fixed GET reads are supported."
            )
        name = scenario["name"]
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", name)
            or name in names
        ):
            raise ValueError("Scenario names must be unique non-sensitive identifiers.")
        names.add(name)
        if (
            not isinstance(scenario["path"], str)
            or scenario["path"] not in ALLOWED_PATHS
        ):
            raise ValueError("Scenario path is not an allowlisted read route.")
        if not isinstance(scenario["credential"], str) or scenario[
            "credential"
        ] not in {"none", *CREDENTIAL_NAMES}:
            raise ValueError("Scenario credential name is unsupported.")
        if scenario["path"].startswith("/health/") and scenario["credential"] != "none":
            raise ValueError("Health scenarios must not send credentials.")
        status = _integer(scenario["expected_status"], 200, 599, "Expected HTTP status")
        if 300 <= status < 400:
            raise ValueError("Redirects cannot be an accepted scenario outcome.")
    # The JSON-safe copy prevents callers changing a validated workload mid-run.
    return json.loads(json.dumps(value))


def validate_credentials(value: dict) -> dict:
    if not isinstance(value, dict) or not set(value) <= CREDENTIAL_NAMES:
        raise ValueError(
            "The private credential document has unsupported account labels."
        )
    for credential in value.values():
        if not isinstance(credential, dict) or set(credential) != {
            "token",
            "device_id",
        }:
            raise ValueError(
                "A private credential must contain a token and device identifier."
            )
        token, device = credential["token"], credential["device_id"]
        if (
            not isinstance(token, str)
            or not 1 <= len(token) <= 4096
            or not re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", token)
        ):
            raise ValueError("A private credential token is malformed.")
        if (
            not isinstance(device, str)
            or not 1 <= len(device) <= 300
            or any(not 32 <= ord(char) <= 126 for char in device)
        ):
            raise ValueError("A private device identifier is malformed.")
    return value


def _read_json(path: Path, *, private=False) -> dict:
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 32_768:
            raise ValueError
        if private and os.name == "posix" and path.stat().st_mode & 0o077:
            raise ValueError
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        label = "private credential" if private else "scenario"
        raise ValueError(
            f"The {label} file is unreadable, unsafe or invalid JSON."
        ) from None


def _source_identity() -> tuple[str, bool]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError
        return commit, bool(dirty)
    except (OSError, subprocess.SubprocessError, ValueError):
        raise ValueError("The local source revision could not be identified.") from None


async def _request(client, origin, scenario, credentials, timeout_seconds):
    started = time.perf_counter()
    status, error = None, None
    headers = {"Accept": "application/json"}
    if scenario["credential"] != "none":
        credential = credentials[scenario["credential"]]
        headers.update(
            {
                "Authorization": f"Bearer {credential['token']}",
                "X-Device-Id": credential["device_id"],
            }
        )
    try:
        # This bounds the entire request, including a response that trickles data.
        async with asyncio.timeout(timeout_seconds):
            async with client.stream(
                "GET", origin + scenario["path"], headers=headers
            ) as response:
                status = response.status_code
                if 300 <= status < 400:
                    error = "redirect_refused"
                else:
                    received = 0
                    async for chunk in response.aiter_bytes():
                        received += len(chunk)
                        if received > MAX_RESPONSE_BYTES:
                            error = "response_too_large"
                            break
                    if error is None and status != scenario["expected_status"]:
                        error = "unexpected_status"
    except (TimeoutError, httpx.TimeoutException):
        error = "timeout"
    except httpx.ConnectError:
        error = "connection"
    except (httpx.HTTPError, OSError):
        error = "transport"
    return status, error, (time.perf_counter() - started) * 1000


async def _measure(origin, scenarios, credentials, requests, concurrency, timeout):
    results = [[] for _ in scenarios]
    jobs = iter(
        (index, scenario)
        for _ in range(requests)
        for index, scenario in enumerate(scenarios)
    )
    async with httpx.AsyncClient(
        follow_redirects=False,
        trust_env=False,
        timeout=timeout,
        limits=httpx.Limits(
            max_connections=concurrency, max_keepalive_connections=concurrency
        ),
    ) as client:

        async def worker():
            for index, scenario in jobs:
                results[index].append(
                    await _request(client, origin, scenario, credentials, timeout)
                )

        async with asyncio.TaskGroup() as group:
            for _ in range(concurrency):
                group.create_task(worker())
    return results


def run_probe(
    base_url,
    configuration,
    *,
    allow_disposable,
    credentials=None,
    requests_per_scenario=10,
    concurrency=3,
    timeout_seconds=3,
    max_p95_ms=None,
    max_error_rate=None,
):
    if allow_disposable is not True:
        raise ValueError("Explicit disposable-fixture authorization is required.")
    origin = loopback_origin(base_url)
    config = validate_configuration(configuration)
    credentials = validate_credentials({} if credentials is None else credentials)
    requests = _integer(requests_per_scenario, 1, 100, "Requests per scenario")
    concurrency = _integer(concurrency, 1, 8, "Concurrency")
    timeout = _finite(timeout_seconds, 0, 10, "Whole-request timeout")
    if requests * len(config["scenarios"]) > MAX_TOTAL_REQUESTS:
        raise ValueError("The probe is limited to 300 total requests.")
    for scenario in config["scenarios"]:
        if (
            scenario["credential"] != "none"
            and scenario["credential"] not in credentials
        ):
            raise ValueError(
                "A scenario requires an account missing from the private credential file."
            )
    thresholds = {}
    if max_p95_ms is not None:
        thresholds["max_p95_ms"] = _finite(max_p95_ms, 0, 60_000, "p95 threshold")
    if max_error_rate is not None:
        thresholds["max_error_rate"] = _finite(
            max_error_rate, 0, 1, "Error-rate threshold", inclusive_low=True
        )
    commit, dirty = _source_identity()
    started = time.perf_counter()
    measurements = asyncio.run(
        _measure(
            origin, config["scenarios"], credentials, requests, concurrency, timeout
        )
    )
    records = []
    threshold_failed = False
    for scenario, values in zip(config["scenarios"], measurements, strict=True):
        durations = sorted(value[2] for value in values)
        errors = Counter(
            error for _status, error, _duration in values if error is not None
        )
        record = {
            "name": scenario["name"],
            "path": scenario["path"],
            "method": "GET",
            "expected_status": scenario["expected_status"],
            "requests": len(values),
            "status_counts": dict(
                sorted(
                    Counter(
                        str(status)
                        for status, _error, _duration in values
                        if status is not None
                    ).items()
                )
            ),
            "error_counts": dict(sorted(errors.items())),
            "p50_ms": round(durations[math.ceil(len(durations) * 0.5) - 1], 3),
            "p95_ms": round(durations[math.ceil(len(durations) * 0.95) - 1], 3),
            "max_ms": round(durations[-1], 3),
            "error_rate": sum(errors.values()) / len(values),
        }
        threshold_failed |= (
            max_p95_ms is not None and record["p95_ms"] > max_p95_ms
        ) or (max_error_rate is not None and record["error_rate"] > max_error_rate)
        records.append(record)
    return {
        "schema_version": 1,
        "measurement_only": True,
        "production_acceptance": False,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": commit,
        "source_tree_dirty": dirty,
        "backend_revision_verified": False,
        "business_read_only": True,
        "authenticated_reads_may_update_device_last_seen": True,
        "target": origin,
        "synthetic_workload": config["synthetic_workload"],
        "concurrency": concurrency,
        "whole_request_timeout_seconds": timeout,
        "completed_requests": sum(record["requests"] for record in records),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "scenarios": records,
        "thresholds": thresholds,
        "threshold_assessment": "exceeded"
        if threshold_failed
        else "met"
        if thresholds
        else "not_evaluated",
        "outcome": "threshold_exceeded"
        if threshold_failed
        else "request_errors"
        if any(record["error_counts"] for record in records)
        else "measured",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--scenarios", required=True, type=Path)
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--allow-disposable", action="store_true")
    parser.add_argument("--requests", type=int, default=10)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=float, default=3)
    parser.add_argument("--max-p95-ms", type=float)
    parser.add_argument("--max-error-rate", type=float)
    args = parser.parse_args(argv)
    try:
        sources = [args.scenarios, *([args.token_file] if args.token_file else [])]
        if args.output.resolve() in {path.resolve() for path in sources}:
            raise ValueError(
                "The output must be separate from the scenario and private credential files."
            )
        report = run_probe(
            args.base_url,
            _read_json(args.scenarios),
            allow_disposable=args.allow_disposable,
            credentials=validate_credentials(_read_json(args.token_file, private=True))
            if args.token_file
            else {},
            requests_per_scenario=args.requests,
            concurrency=args.concurrency,
            timeout_seconds=args.timeout_seconds,
            max_p95_ms=args.max_p95_ms,
            max_error_rate=args.max_error_rate,
        )
        rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
        args.output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 0 if report["outcome"] == "measured" else 1
    except ValueError as error:
        print(f"Performance probe refused: {error}", file=sys.stderr)
        return 2
    except OSError:
        print("Performance probe could not write its result file.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

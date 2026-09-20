"""Reject new diagnostics against retained fingerprints, without waiving old debt."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

FILES = {
    "ruff": "ruff.json",
    "pyright": "pyright.json",
    "bandit": "bandit.json",
    "gitleaks": "gitleaks-redacted.json",
    "pip_audit": "pip-audit.json",
    "format": "ruff-format.txt",
}


def relative_source(value: str) -> str:
    path = value.replace("\\", "/")
    for prefix in ("gilbic_backend/", "spina_backend_mobile/", "tools/", "tests/"):
        if prefix in path:
            return path[path.index(prefix) :]
    return path.removeprefix("./")


def fingerprint(tool: str, item: dict[str, Any]) -> str:
    if tool == "ruff":
        identity = [
            relative_source(item["filename"]),
            item["code"],
            item.get("severity", "error"),
            item["message"],
        ]
    elif tool == "pyright":
        identity = [
            relative_source(item["file"]),
            item.get("rule", ""),
            item["severity"],
            item["message"],
        ]
    elif tool == "bandit":
        identity = [
            relative_source(item["filename"]),
            item["test_id"],
            item["issue_severity"],
            item["issue_confidence"],
            item["issue_text"],
        ]
    elif tool == "gitleaks":
        identity = [item["Fingerprint"]]
    elif tool == "pip_audit":
        identity = [item["name"], item["version"], item["id"]]
    elif tool == "format":
        identity = [relative_source(item["path"])]
    else:
        raise ValueError("Unsupported scanner report")
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()


def load_reports(directory: Path) -> dict[str, dict[str, int]]:
    results = {}
    for tool, filename in FILES.items():
        text = (directory / filename).read_text(encoding="utf-8-sig")
        if tool == "format":
            # Ruff's summary alone cannot distinguish an empty report from success.
            if "file" not in text or not any(
                word in text for word in ("formatted", "reformatted", "reformat")
            ):
                raise ValueError("Missing Ruff formatting outcome")
            paths = {
                line.removeprefix("Would reformat: ")
                for line in text.splitlines()
                if line.startswith("Would reformat: ")
            }
            paths.update(re.findall(r"^\s*-->\s+(.+?):\d+:\d+\s*$", text, re.MULTILINE))
            items = [{"path": path} for path in sorted(paths)]
        else:
            payload = json.loads(text)
            if tool in {"ruff", "gitleaks"}:
                items = payload
            elif tool == "pyright":
                items = payload["generalDiagnostics"]
                if payload.get("version") != "1.1.414":
                    raise ValueError("Pyright version differs from retained baseline")
            elif tool == "bandit":
                if payload.get("errors"):
                    raise ValueError("Bandit skipped files because of errors")
                items = payload["results"]
            else:
                dependencies = payload["dependencies"]
                if not isinstance(dependencies, list) or not dependencies:
                    raise ValueError("Missing dependency audit coverage")
                audited = []
                for dependency in dependencies:
                    if not isinstance(dependency, dict):
                        raise TypeError("Invalid dependency audit entry")
                    if "skip_reason" in dependency:
                        if not (
                            dependency.get("name")
                            in {"gilbic-backend", "spina-mobile-collections"}
                            and dependency.get("version") is None
                            and dependency["skip_reason"]
                            == "distribution marked as editable"
                        ):
                            raise ValueError("Unexpected unaudited dependency")
                        continue
                    if not isinstance(
                        dependency.get("vulns"), list
                    ) or not dependency.get("version"):
                        raise ValueError("Missing dependency audit result")
                    audited.append(dependency)
                if not audited:
                    raise ValueError("No dependencies audited")
                items = [
                    {
                        "name": dependency["name"],
                        "version": dependency["version"],
                        "id": vulnerability["id"],
                    }
                    for dependency in audited
                    for vulnerability in dependency["vulns"]
                ]
            if not isinstance(items, list) or any(
                not isinstance(item, dict) for item in items
            ):
                raise ValueError("Invalid scanner report entries")
        results[tool] = dict(
            sorted(Counter(fingerprint(tool, item) for item in items).items())
        )
    return results


def compare(
    baseline: dict[str, dict[str, int]], current: dict[str, dict[str, int]]
) -> dict[str, Any]:
    tools = {}
    passed = set(baseline) == set(current)
    for tool in sorted(set(baseline) | set(current)):
        previous = Counter(baseline.get(tool, {}))
        latest = Counter(current.get(tool, {}))
        added = dict(latest - previous)
        removed = dict(previous - latest)
        passed = passed and not added and tool in current and tool in baseline
        tools[tool] = {
            "baseline_count": previous.total(),
            "current_count": latest.total(),
            "added": added,
            "removed": removed,
        }
    return {
        "kind": "scanner_regression_check",
        "status": "passed" if passed else "failed",
        "security_clearance": False,
        "tools": tools,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        if baseline["schema_version"] != 1 or set(baseline["tools"]) != set(FILES):
            raise ValueError("Incomplete baseline")
        result = compare(baseline["tools"], load_reports(args.reports_dir))
    except (OSError, ValueError, KeyError, TypeError):
        result = {
            "kind": "scanner_regression_check",
            "status": "failed",
            "security_clearance": False,
            "reason": "Missing, malformed or incompatible report/baseline",
        }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "security_clearance": False}))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

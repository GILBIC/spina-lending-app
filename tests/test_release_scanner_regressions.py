from __future__ import annotations

import importlib.util
import json

import pytest


def scanner():
    spec = importlib.util.find_spec("tools.check_release_scanner_regressions")
    assert spec is not None, "CI must reject added scanner findings"
    from tools import check_release_scanner_regressions

    return check_release_scanner_regressions


def test_finding_identity_ignores_checkout_root_and_line_but_retains_rule_and_message():
    check = scanner()
    finding = {
        "filename": "C:\\work\\spina\\gilbic_backend\\src\\gilbic_backend\\example.py",
        "code": "B608",
        "severity": "warning",
        "message": "unsafe query",
        "location": {"row": 10, "column": 2},
    }
    moved = {
        **finding,
        "filename": "/home/runner/work/spina/gilbic_backend/src/gilbic_backend/example.py",
        "location": {"row": 80, "column": 9},
    }
    assert check.fingerprint("ruff", finding) == check.fingerprint("ruff", moved)
    assert check.fingerprint("ruff", finding) != check.fingerprint(
        "ruff", {**moved, "message": "different problem"}
    )


def test_equal_total_cannot_hide_new_finding_and_duplicate_counts_are_enforced():
    check = scanner()
    result = check.compare({"ruff": {"old": 2}}, {"ruff": {"old": 1, "new": 1}})
    assert result["status"] == "failed"
    assert result["tools"]["ruff"]["added"] == {"new": 1}
    assert result["tools"]["ruff"]["removed"] == {"old": 1}
    assert (
        check.compare({"ruff": {"old": 1}}, {"ruff": {"old": 2}})["status"] == "failed"
    )


def test_removing_old_findings_passes_without_claiming_security_clearance():
    check = scanner()
    result = check.compare({"bandit": {"old": 2}}, {"bandit": {"old": 1}})
    assert result["status"] == "passed"
    assert result["security_clearance"] is False


def test_missing_tool_report_fails_closed():
    check = scanner()
    assert check.compare({"ruff": {}, "bandit": {}}, {"ruff": {}})["status"] == "failed"


def test_bandit_severity_and_confidence_are_part_of_identity():
    check = scanner()
    item = {
        "filename": "gilbic_backend/src/example.py",
        "test_id": "B608",
        "issue_severity": "MEDIUM",
        "issue_confidence": "LOW",
        "issue_text": "unsafe query",
    }
    assert check.fingerprint("bandit", item) != check.fingerprint(
        "bandit", {**item, "issue_confidence": "HIGH"}
    )


def write_reports(tmp_path, dependencies=None):
    check = scanner()
    reports = {
        "ruff.json": [],
        "pyright.json": {"version": "1.1.414", "generalDiagnostics": []},
        "bandit.json": {"errors": [], "results": []},
        "gitleaks-redacted.json": [],
        "pip-audit.json": {
            "dependencies": dependencies
            if dependencies is not None
            else [{"name": "pytest", "version": "8.4.0", "vulns": []}]
        },
    }
    for name, payload in reports.items():
        (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "ruff-format.txt").write_text(
        "unformatted: File would be reformatted\n"
        "  --> gilbic_backend/src/example.py:10:2\n"
        "  --> gilbic_backend/src/example.py:20:1\n"
        "1 file would be reformatted\n",
        encoding="utf-8",
    )
    return check


def test_current_ruff_format_diagnostics_are_counted_once_per_file(tmp_path):
    check = write_reports(tmp_path)
    assert sum(check.load_reports(tmp_path)["format"].values()) == 1


@pytest.mark.parametrize(
    "dependencies",
    [
        [],
        [
            {
                "name": "pytest",
                "version": "8.4.0",
                "skip_reason": "distribution not found",
            }
        ],
        [
            {
                "name": "gilbic-backend",
                "version": None,
                "skip_reason": "distribution marked as editable",
            }
        ],
        [{"name": "pytest", "version": "8.4.0"}],
    ],
)
def test_missing_or_skipped_dependency_audit_fails_closed(tmp_path, dependencies):
    check = write_reports(tmp_path, dependencies)
    with pytest.raises(ValueError):
        check.load_reports(tmp_path)


def test_only_known_editable_project_skips_are_allowed_with_audited_dependencies(
    tmp_path,
):
    check = write_reports(
        tmp_path,
        [
            {
                "name": "gilbic-backend",
                "version": None,
                "skip_reason": "distribution marked as editable",
            },
            {
                "name": "spina-mobile-collections",
                "version": None,
                "skip_reason": "distribution marked as editable",
            },
            {"name": "pytest", "version": "8.4.0", "vulns": []},
        ],
    )
    assert check.load_reports(tmp_path)["pip_audit"] == {}

"""Deployment recovery contracts; never execute host bootstrap or contact a host."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "ops" / "digitalocean" / "bootstrap.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "spina-digitalocean-deploy.yml"


def test_detached_runs_have_independent_staging_and_verified_revision() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    script = BOOTSTRAP.read_text(encoding="utf-8")
    assert "cancel-in-progress: false" in workflow
    assert (
        'REMOTE_RUN_DIR="/var/lib/spina-deploy/run-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"'
        in workflow
    )
    assert "/var/lib/spina-bootstrap.exit" not in workflow
    assert "/var/log/spina-bootstrap.log" not in workflow
    assert "--verify-active" in workflow
    assert '--verified-active-sha "$ACTIVE_SHA"' in workflow
    assert "readonly SHA HOSTNAME RUN_DIR ARCHIVE_SHA256" in script
    assert script.index("flock -n 9") < script.index("export DEBIAN_FRONTEND")
    assert (
        "ExecStartPre=/opt/spina/current/venv/bin/python -m gilbic_backend.release_preflight --profile runtime"
        in script
    )
    assert "s|/opt/spina/current|$RELEASE_DIR|g" in script


def test_two_staged_runs_keep_inputs_and_completion_separate(tmp_path: Path) -> None:
    assert "validate_staged_input()" in _lifecycle_script()
    result = _bash(
        tmp_path,
        r"""
mkdir -p run-a run-b seed-a seed-b
sha_a=$(printf 'a%.0s' {1..40})
sha_b=$(printf 'b%.0s' {1..40})
printf '%s\n' "$sha_a" > seed-a/spina-git-sha
printf '%s\n' "$sha_b" > seed-b/spina-git-sha
printf run-a-private > run-a/runtime.env
printf run-b-private > run-b/runtime.env
tar -czf run-a/release.tar.gz -C seed-a spina-git-sha
tar -czf run-b/release.tar.gz -C seed-b spina-git-sha
hash_a=$(sha256sum run-a/release.tar.gz | cut -d ' ' -f 1)
hash_b=$(sha256sum run-b/release.tar.gz | cut -d ' ' -f 1)
validate_staged_input "$sha_a" run-a "$hash_a"
validate_staged_input "$sha_b" run-b "$hash_b"
if validate_staged_input "$sha_a" run-b "$hash_b"; then exit 10; fi
if validate_staged_input "$sha_a" run-a "$hash_b"; then exit 11; fi
if (RUN_DIR="$PWD/run-a"; trap deployment_exit EXIT; exit 143); then exit 12; fi
test "$(cat run-a/exit-code)" = 143
test ! -e run-b/exit-code
test ! -e run-a/runtime.env
test "$(cat run-b/runtime.env)" = run-b-private
validate_staged_input "$sha_b" run-b "$hash_b"
""",
    )
    assert result.returncode == 0, result.stderr
    assert "private" not in result.stdout + result.stderr


def test_active_revision_requires_matching_runtime_and_portal(tmp_path: Path) -> None:
    assert "verify_release_paths()" in _lifecycle_script()
    result = _bash(
        tmp_path,
        r"""
mkdir -p old/dist candidate/dist
old_sha=$(printf 'a%.0s' {1..40})
new_sha=$(printf 'b%.0s' {1..40})
printf '%s\n' "$old_sha" > old/git-sha
printf '%s\n' "$new_sha" > candidate/git-sha
ln -s "$PWD/candidate" current
ln -s "$PWD/candidate/dist" portal
verify_release_paths "$new_sha" current portal "$PWD/candidate"
if verify_release_paths "$old_sha" current portal "$PWD/candidate"; then exit 10; fi
if verify_release_paths "$new_sha" current portal "$PWD/old"; then exit 11; fi
ln -sfn -T "$PWD/old/dist" portal
if verify_release_paths "$new_sha" current portal "$PWD/candidate"; then exit 12; fi
""",
    )
    assert result.returncode == 0, result.stderr


def test_workflow_and_remote_launch_shell_syntax_without_execution(
    tmp_path: Path,
) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    body = textwrap.dedent(
        workflow.split("        run: |\n", 1)[1].split("\n      - name:", 1)[0]
    )
    (tmp_path / "workflow.sh").write_text(body, encoding="utf-8")
    launch = re.search(
        r"          start_remote_bootstrap\(\) \{\n(.*?)\n          \}",
        workflow,
        re.DOTALL,
    )
    assert launch is not None
    result = _bash(
        tmp_path,
        """
bash -n workflow.sh
REMOTE_RUN_DIR=/var/lib/spina-deploy/run-123-1
GITHUB_SHA=$(printf 'a%.0s' {1..40})
HOSTNAME=spina.159-223-39-43.sslip.io
ARCHIVE_SHA256=$(printf 'b%.0s' {1..64})
ssh_with_retry() { bash -n -c "$1"; }
"""
        + textwrap.dedent(launch.group(1)),
    )
    assert result.returncode == 0, result.stderr


def test_snapshot_failure_does_not_run_rollback_before_activation(
    tmp_path: Path,
) -> None:
    result = _bash(
        tmp_path,
        """
mkdir backup unexpected-directory
printf existing-portal > portal
ACTIVATION_BACKUP=backup
DEPLOYMENT_PATHS=(unexpected-directory portal service caddy)
ACTIVATION_STARTED=false
ACTIVATED=false
trap deployment_exit EXIT
systemctl() { printf '%s\n' "$*" >> service-calls; }
snapshot_deployment backup "${DEPLOYMENT_PATHS[@]}"
""",
    )
    assert result.returncode == 1
    assert "ROLLBACK" not in result.stderr
    assert (tmp_path / "portal").read_text(encoding="utf-8") == "existing-portal"
    assert not (tmp_path / "service-calls").exists()


def test_request_logging_emits_safe_info_without_raw_access_lines() -> None:
    script = BOOTSTRAP.read_text(encoding="utf-8")
    assert "--no-access-log --log-config /opt/spina/current/logging.json" in script
    found = re.search(r"<<'LOGGING'\n(.*?)\nLOGGING", script, re.DOTALL)
    assert found is not None, "structured request INFO logging is not configured"
    program = """
import json, logging, logging.config, sys
logging.config.dictConfig(json.loads(sys.stdin.read()))
logging.getLogger('gilbic.request').info('{"request_id":"safe-id","status":200}')
logging.getLogger('uvicorn.access').info('raw-secret-in-query')
logging.getLogger('uvicorn.error').info('server-started')
"""
    result = subprocess.run(
        [sys.executable, "-c", program],
        input=found.group(1),
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '{"request_id":"safe-id","status":200}'
    assert "server-started" in result.stderr
    assert "raw-secret" not in result.stdout + result.stderr


def test_runtime_and_environment_are_selected_with_the_release() -> None:
    script = BOOTSTRAP.read_text(encoding="utf-8")
    assert "/opt/spina/venv" not in script, "shared packages survive a symlink rollback"
    assert "EnvironmentFile=/opt/spina/current/runtime.env" in script
    assert "EnvironmentFile=-/etc/spina/operator.env" in script
    assert "ExecStart=/opt/spina/current/venv/bin/python -m uvicorn" in script
    assert "install -d -m 0700 -o spina -g spina /var/lib/spina" in script
    assert "trap deployment_exit EXIT" in script


def _lifecycle_script() -> str:
    script = BOOTSTRAP.read_text(encoding="utf-8")
    marker = "# End deployment lifecycle functions."
    assert marker in script, "no recoverable deployment lifecycle is implemented"
    return script.split(marker, 1)[0]


def _bash(tmp_path: Path, body: str) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("bash")
    if executable is None and os.name == "nt":
        candidate = Path("C:/Program Files/Git/bin/bash.exe")
        executable = str(candidate) if candidate.is_file() else None
    if executable is None:
        pytest.skip("Bash is required for isolated deployment lifecycle tests")
    script = tmp_path / "lifecycle.sh"
    script.write_text(_lifecycle_script() + "\n" + body, encoding="utf-8")
    environment = os.environ.copy()
    if os.name == "nt":
        # Git Bash's POSIX link representation works without Windows symlink
        # privilege; Linux CI runs these same functions with native symlinks.
        environment["MSYS"] = "winsymlinks:lnk"
    return subprocess.run(
        [executable, str(script)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        env=environment,
        check=False,
        timeout=15,
    )


def test_operator_configuration_survives_first_upgrade_and_redeploy(
    tmp_path: Path,
) -> None:
    result = _bash(
        tmp_path,
        """
printf '%s\n' 'GILBIC_DATABASE_URL="old-secret"' 'GILBIC_ENVIRONMENT="production"' \\
  'SPINA_EMPLOYEE_OWNER_USER_ID="owner-id"' 'GILBIC_OFFICE_REVIEW_EVIDENCE_ROOT="/private/evidence"' \\
  'GILBIC_CREDENTIAL_SMTP_PASSWORD="smtp-secret"' > legacy.env
preserve_operator_environment legacy.env operator.env
cp operator.env expected.env
printf '%s\n' 'SPINA_EMPLOYEE_OWNER_USER_ID="replacement"' > legacy.env
preserve_operator_environment legacy.env operator.env
cmp expected.env operator.env
! grep -q 'old-secret' operator.env
grep -q 'owner-id' operator.env
grep -q 'smtp-secret' operator.env
""",
    )
    assert result.returncode == 0, result.stderr
    assert "secret" not in result.stdout + result.stderr


def test_activation_failure_restores_runtime_portal_config_and_service(
    tmp_path: Path,
) -> None:
    result = _bash(
        tmp_path,
        """
mkdir -p old/dist candidate/dist backup
printf old-runtime > old/runtime.env
printf old-unit > service
printf old-caddy > caddy
printf candidate-unit > candidate/spina-api.service
printf candidate-caddy > candidate/Caddyfile
ln -s old current
ln -s old/dist portal
snapshot_deployment backup current portal service caddy
systemctl() { printf '%s\n' "$*" >> service-calls; }
ACTIVATION_BACKUP=backup
DEPLOYMENT_PATHS=(current portal service caddy)
ACTIVATED=false
ACTIVATION_STARTED=true
trap deployment_exit EXIT
activate_deployment candidate current portal service caddy
test "$(readlink current)" = candidate
exit 23
""",
    )
    assert result.returncode == 1, result.stderr
    assert "SPINA_DEPLOY_ROLLBACK" in result.stderr
    verification = _bash(
        tmp_path,
        """
test "$(readlink current)" = old
test "$(readlink portal)" = old/dist
test "$(cat current/runtime.env)" = old-runtime
test "$(cat service)" = old-unit
test "$(cat caddy)" = old-caddy
grep -q 'restart spina-api' service-calls
grep -q 'reload caddy' service-calls
""",
    )
    assert verification.returncode == 0, verification.stderr


def test_accepted_candidate_is_retained_by_exit_trap(tmp_path: Path) -> None:
    result = _bash(
        tmp_path,
        """
mkdir -p candidate/dist backup
printf candidate-unit > candidate/spina-api.service
printf candidate-caddy > candidate/Caddyfile
snapshot_deployment backup current portal service caddy
systemctl() { printf '%s\n' "$*" >> service-calls; }
ACTIVATION_BACKUP=backup
DEPLOYMENT_PATHS=(current portal service caddy)
ACTIVATED=false
ACTIVATION_STARTED=true
trap deployment_exit EXIT
activate_deployment candidate current portal service caddy
ACTIVATED=true
""",
    )
    assert result.returncode == 0, result.stderr
    assert "ROLLBACK" not in result.stderr
    assert (tmp_path / "service").read_text(encoding="utf-8") == "candidate-unit"
    assert "stop spina-api" not in (tmp_path / "service-calls").read_text(
        encoding="utf-8"
    )


def test_failed_first_activation_stops_candidate_and_removes_new_paths(
    tmp_path: Path,
) -> None:
    result = _bash(
        tmp_path,
        """
mkdir -p candidate/dist backup
printf candidate-unit > candidate/spina-api.service
printf candidate-caddy > candidate/Caddyfile
snapshot_deployment backup current portal service caddy
systemctl() { printf '%s\n' "$*" >> service-calls; }
activate_deployment candidate current portal service caddy
rollback_deployment backup current portal service caddy
test ! -e current && test ! -L current
test ! -e portal && test ! -L portal
test ! -e service
test ! -e caddy
grep -q 'disable --now spina-api' service-calls
""",
    )
    assert result.returncode == 0, result.stderr

"""Exercise backup ordering and failure recovery with real private archives."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "ops/digitalocean/backup.sh"


def run_backup(tmp_path: Path, failure: str = ""):
    bash = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"
    if not Path(bash).exists():
        pytest.skip("Bash required")
    assert SCRIPT.exists(), "Operational backup lifecycle is missing"
    fixture = r"""
set -eu
mkdir -p state private config repo
printf 'SYNTHETIC PRIVATE EVIDENCE' > private/proof.pdf
printf 'SYNTHETIC PRIVATE CONFIG' > config/operator.env
export SPINA_BACKUP_STATE="$PWD/state"
export SPINA_BACKUP_PRIVATE_ROOT="$PWD/private"
export SPINA_BACKUP_CONFIG_ROOT="$PWD/config"
export SPINA_BACKUP_HOST=synthetic
export SPINA_BACKUP_ENABLED=yes
export RESTIC_REPOSITORY="$PWD/repo"
export RESTIC_PASSWORD_FILE="$PWD/password"
printf synthetic > "$RESTIC_PASSWORD_FILE"
export PGHOST=127.0.0.1 PGPORT=49190 PGDATABASE=synthetic PGUSER=postgres
export SPINA_BACKUP_KEEP_DAILY=7 SPINA_BACKUP_KEEP_WEEKLY=4 SPINA_BACKUP_KEEP_MONTHLY=3
export SPINA_BACKUP_RETENTION_ENABLED=no
export SPINA_BACKUP_SERVICE=spina-api
export SPINA_BACKUP_LOCK="$PWD/lock"
flock() { :; }
systemctl() {
  printf '%s\n' "systemctl $*" >> "$PWD/calls"
  if [[ "$1" == is-active && "${2:-}" == --quiet ]]; then return 0; fi
}
pg_dump() {
  printf 'dump\n' >> "$PWD/calls"
  [[ "$FAILURE" != dump ]] || { printf 'secret connection failure' >&2; return 1; }
  printf 'SYNTHETIC DUMP' > "${@: -1}"
}
pg_restore() { printf 'toc\n' >> "$PWD/calls"; }
restic() {
  printf 'restic %s\n' "$*" >> "$FIXTURE/calls"
  if [[ "$FAILURE" == repository && "$1" == snapshots ]]; then return 1; fi
  if [[ "$FAILURE" == restic && "$1" == backup ]]; then printf 'secret repository failure' >&2; return 1; fi
  if [[ "$FAILURE" == check && "$1" == check ]]; then return 1; fi
  if [[ "$1" == backup ]]; then
    cp database.dump private-evidence.tar configuration.tar SHA256SUMS "$FIXTURE/repo/"
    printf '{"message_type":"summary","snapshot_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}\n'
  fi
}
export -f flock systemctl pg_dump pg_restore restic
export FIXTURE="$PWD"
"""
    source = SCRIPT.read_text(encoding="utf-8")
    harness = tmp_path / "run.sh"
    harness.write_text(fixture + "\n" + source, encoding="utf-8")
    result = subprocess.run(
        [bash, str(harness)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "FAILURE": failure},
        timeout=20,
        check=False,
    )
    calls = (tmp_path / "calls").read_text() if (tmp_path / "calls").exists() else ""
    return result, calls


def test_dump_private_files_and_configuration_share_verified_snapshot(tmp_path):
    result, calls = run_backup(tmp_path)
    assert result.returncode == 0, result.stderr
    assert (
        calls.index("systemctl stop")
        < calls.index("dump")
        < calls.index("systemctl start")
    )
    assert calls.index("systemctl start") < calls.index("restic backup")
    assert calls.index("restic backup") < calls.index("restic check")
    assert "forget" not in calls
    assert (tmp_path / "state/last-success").exists()
    assert not list((tmp_path / "state").glob("run.*"))
    assert {p.name for p in (tmp_path / "repo").iterdir()} == {
        "database.dump",
        "private-evidence.tar",
        "configuration.tar",
        "SHA256SUMS",
    }


@pytest.mark.parametrize("failure", ["dump", "restic", "check"])
def test_failed_capture_or_upload_restarts_service_and_never_marks_success(
    tmp_path, failure
):
    result, calls = run_backup(tmp_path, failure)
    assert result.returncode != 0
    assert "systemctl start spina-api" in calls
    assert not (tmp_path / "state/last-success").exists()
    assert not list((tmp_path / "state").glob("run.*"))
    assert "secret" not in result.stdout + result.stderr


def test_repository_failure_never_pauses_api(tmp_path):
    result, calls = run_backup(tmp_path, "repository")
    assert result.returncode != 0
    assert "systemctl stop" not in calls
    assert not (tmp_path / "state/last-success").exists()

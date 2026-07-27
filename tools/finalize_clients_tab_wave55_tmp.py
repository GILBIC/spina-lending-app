from __future__ import annotations

import subprocess
from pathlib import Path

BRANCH = "agent/high-volume-wave-55-clean"
TEMP_PATHS = [
    Path("tools/extract_clients_tab_wave55_tmp.py"),
    Path("tools/fix_clients_tab_wave55_hash_tmp.py"),
    Path("tools/finalize_clients_tab_wave55_tmp.py"),
    Path(".github/workflows/plan-high-volume-wave-55.yml"),
    Path("docs/wave-55-candidate-report.md"),
    Path("artifacts/wave-55-candidates.json"),
    Path("artifacts/wave-55-extraction.json"),
]


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(args), flush=True)
    return subprocess.run(args, check=check, text=True)


for path in TEMP_PATHS:
    try:
        path.unlink()
        print(f"removed {path}", flush=True)
    except FileNotFoundError:
        pass

run("git", "status", "--short")
run("git", "config", "user.name", "github-actions[bot]")
run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
run("git", "add", "-A")
run("git", "status", "--short")
if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
    raise SystemExit("Wave 55 finalizer found no staged changes")
run("git", "commit", "-m", "Extract Clients tab presentation Wave 55")
run("git", "push", "origin", f"HEAD:{BRANCH}")

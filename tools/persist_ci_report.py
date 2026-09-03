from __future__ import annotations
import argparse, json, re, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_LANE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_DEFAULT_ROOT = Path(r"C:\SPINA_CI_REPORTS")

def _validated_sha(value: str) -> str:
    value = value.strip().lower()
    if not _SHA_RE.fullmatch(value):
        raise ValueError("commit SHA must be exactly 40 hexadecimal characters")
    return value

def _validated_lane(value: str) -> str:
    value = value.strip().lower()
    if not _LANE_RE.fullmatch(value):
        raise ValueError("lane must use lowercase letters, digits, and hyphens")
    return value

def _prune_old_commits(root: Path, keep: int) -> None:
    if keep <= 0:
        return
    items = [p for p in root.iterdir() if p.is_dir() and _SHA_RE.fullmatch(p.name)]
    items.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for stale in items[keep:]:
        try:
            shutil.rmtree(stale)
        except OSError as exc:
            print(f"warning: could not prune {stale}: {exc}", file=sys.stderr)

def persist_report(source: Path, root: Path, commit_sha: str, lane: str,
                   run_id: str, workflow_name: str, keep: int) -> Path:
    commit_sha = _validated_sha(commit_sha)
    lane = _validated_lane(lane)
    root.mkdir(parents=True, exist_ok=True)
    commit_dir = root / commit_sha
    destination = commit_dir / lane
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    source_present = source.exists()
    if source_present:
        if source.is_dir():
            for item in source.iterdir():
                target = destination / item.name
                if item.is_dir():
                    shutil.copytree(item, target)
                else:
                    shutil.copy2(item, target)
        else:
            shutil.copy2(source, destination / source.name)
    metadata = {
        "commit_sha": commit_sha, "lane": lane, "run_id": str(run_id),
        "workflow_name": workflow_name,
        "persisted_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(source), "source_present": source_present,
    }
    (destination / "_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    commit_dir.touch()
    _prune_old_commits(root, keep)
    return destination

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--workflow-name", required=True)
    parser.add_argument("--root", default=str(_DEFAULT_ROOT))
    parser.add_argument("--keep", type=int, default=50)
    args = parser.parse_args()
    try:
        dest = persist_report(Path(args.source), Path(args.root), args.commit_sha,
                              args.lane, args.run_id, args.workflow_name, args.keep)
    except (OSError, ValueError) as exc:
        print(f"SPINA CI report persistence failed: {exc}", file=sys.stderr)
        return 2
    print(f"SPINA_CI_REPORT_PATH={dest}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _get_json(path: str, token: str) -> object:
    request = Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "spina-ci-contract-inspection",
            "X-GitHub-Api-Version": "2026-03-10",
        },
    )
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def _pull_fact(source: str, pull: dict[str, Any]) -> dict[str, object]:
    head = pull.get("head") if isinstance(pull.get("head"), dict) else {}
    base = pull.get("base") if isinstance(pull.get("base"), dict) else {}
    user = pull.get("user") if isinstance(pull.get("user"), dict) else {}
    head_repo = head.get("repo") if isinstance(head.get("repo"), dict) else {}
    base_repo = base.get("repo") if isinstance(base.get("repo"), dict) else {}
    return {
        "source": source,
        "number": pull.get("number"),
        "state": pull.get("state"),
        "merged": pull.get("merged"),
        "merged_at": pull.get("merged_at"),
        "merge_commit_sha": pull.get("merge_commit_sha"),
        "user": user.get("login"),
        "head_ref": head.get("ref"),
        "head_repo": head_repo.get("full_name"),
        "base_ref": base.get("ref"),
        "base_repo": base_repo.get("full_name"),
    }


def main() -> int:
    repository = os.environ["REPOSITORY"]
    merge_sha = os.environ["MERGE_SHA"]
    validated_head_sha = os.environ["VALIDATED_HEAD_SHA"]
    token = os.environ["GITHUB_TOKEN"]

    associated = _get_json(
        f"/repos/{repository}/commits/{merge_sha}/pulls",
        token,
    )
    closed_query = urlencode(
        {
            "state": "closed",
            "base": "main",
            "sort": "updated",
            "direction": "desc",
            "per_page": 100,
        }
    )
    closed = _get_json(f"/repos/{repository}/pulls?{closed_query}", token)
    detail = _get_json(f"/repos/{repository}/pulls/287", token)
    run_query = urlencode(
        {
            "event": "pull_request",
            "head_sha": validated_head_sha,
            "status": "success",
            "per_page": 10,
        }
    )
    runs = _get_json(
        f"/repos/{repository}/actions/workflows/spina-ci.yml/runs?{run_query}",
        token,
    )
    if not isinstance(associated, list) or not isinstance(closed, list):
        raise TypeError("pull-request inspection responses were not lists")
    if not isinstance(detail, dict) or not isinstance(runs, dict):
        raise TypeError("detail or workflow-run inspection response was invalid")

    print(f"associated_count={len(associated)}")
    for pull in associated[:3]:
        print(json.dumps(_pull_fact("associated", pull), sort_keys=True))
    print(f"closed_count={len(closed)}")
    for pull in closed[:3]:
        print(json.dumps(_pull_fact("closed", pull), sort_keys=True))
    print(json.dumps(_pull_fact("detail", detail), sort_keys=True))

    workflow_runs = runs.get("workflow_runs", [])
    if not isinstance(workflow_runs, list):
        raise TypeError("workflow-run inspection list was invalid")
    print(f"workflow_run_count={len(workflow_runs)}")
    for run in workflow_runs[:3]:
        actor = run.get("actor") if isinstance(run.get("actor"), dict) else {}
        head_repository = (
            run.get("head_repository")
            if isinstance(run.get("head_repository"), dict)
            else {}
        )
        pull_requests = run.get("pull_requests", [])
        print(
            json.dumps(
                {
                    "source": "workflow_run",
                    "id": run.get("id"),
                    "event": run.get("event"),
                    "status": run.get("status"),
                    "conclusion": run.get("conclusion"),
                    "head_sha": run.get("head_sha"),
                    "head_branch": run.get("head_branch"),
                    "actor": actor.get("login"),
                    "head_repository": head_repository.get("full_name"),
                    "pull_requests": [
                        pull.get("number")
                        for pull in pull_requests
                        if isinstance(pull, dict)
                    ],
                },
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

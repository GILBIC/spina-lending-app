from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


API_VERSION = "2026-03-10"
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class ValidationReuseDecision:
    reuse_validation: bool
    reason: str
    pull_request_number: int | None = None
    validated_head_sha: str | None = None
    workflow_run_id: int | None = None


JsonFetcher = Callable[[str, str], object]


def _matching_merged_owner_pulls(
    payload: object,
    *,
    repository: str,
    owner: str,
    base_ref: str,
    commit_sha: str,
) -> list[dict[str, Any]] | None:
    if not isinstance(payload, list):
        return None

    candidates: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        head = item.get("head")
        base = item.get("base")
        user = item.get("user")
        if not isinstance(head, dict) or not isinstance(base, dict) or not isinstance(user, dict):
            continue
        head_repo = head.get("repo")
        base_repo = base.get("repo")
        if not isinstance(head_repo, dict) or not isinstance(base_repo, dict):
            continue
        if (
            item.get("state") == "closed"
            and item.get("merged_at")
            and str(item.get("merge_commit_sha", "")).lower() == commit_sha
            and base.get("ref") == base_ref
            and base_repo.get("full_name") == repository
            and head_repo.get("full_name") == repository
            and user.get("login") == owner
        ):
            candidates.append(item)
    return candidates


def _commit_tree_sha(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    tree = payload.get("tree")
    if not isinstance(tree, dict):
        return None
    tree_sha = str(tree.get("sha", "")).lower()
    return tree_sha if SHA_PATTERN.fullmatch(tree_sha) else None


def _github_json(url: str, token: str) -> object:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "spina-ci-validation-reuse",
            "X-GitHub-Api-Version": API_VERSION,
        },
    )
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def decide_validation_reuse(
    *,
    repository: str,
    commit_sha: str,
    workflow_file: str,
    base_ref: str,
    token: str,
    api_url: str = "https://api.github.com",
    fetch_json: JsonFetcher = _github_json,
) -> ValidationReuseDecision:
    """Prove that a main commit came from an exact successful owner PR run.

    Any missing, ambiguous, or inconsistent evidence fails closed so the push
    executes the full backend and Flutter validation suite.
    """

    if repository.count("/") != 1:
        return ValidationReuseDecision(False, "repository must be owner/name")
    owner, repo_name = repository.split("/", 1)
    normalized_sha = commit_sha.lower()
    if not SHA_PATTERN.fullmatch(normalized_sha):
        return ValidationReuseDecision(False, "commit SHA is not a full 40-character SHA")
    if not workflow_file or not base_ref or not token:
        return ValidationReuseDecision(False, "required GitHub validation context is missing")

    encoded_repo = f"{quote(owner, safe='')}/{quote(repo_name, safe='')}"
    pulls_url = (
        f"{api_url.rstrip('/')}/repos/{encoded_repo}/commits/"
        f"{quote(normalized_sha, safe='')}/pulls"
    )
    pulls_payload = fetch_json(pulls_url, token)
    candidates = _matching_merged_owner_pulls(
        pulls_payload,
        repository=repository,
        owner=owner,
        base_ref=base_ref,
        commit_sha=normalized_sha,
    )
    if candidates is None:
        return ValidationReuseDecision(False, "associated pull-request response was invalid")

    # GitHub can start the push workflow before the commit-associated PR index
    # exposes a just-completed squash merge. Fall back to the newest closed PR
    # records and retain the same exact merge-SHA, owner, repository, and base
    # predicates. Missing or ambiguous fallback evidence still fails closed.
    if not candidates:
        closed_pulls_query = urlencode(
            {
                "state": "closed",
                "base": base_ref,
                "sort": "updated",
                "direction": "desc",
                "per_page": 100,
            }
        )
        closed_pulls_url = (
            f"{api_url.rstrip('/')}/repos/{encoded_repo}/pulls?{closed_pulls_query}"
        )
        candidates = _matching_merged_owner_pulls(
            fetch_json(closed_pulls_url, token),
            repository=repository,
            owner=owner,
            base_ref=base_ref,
            commit_sha=normalized_sha,
        )
        if candidates is None:
            return ValidationReuseDecision(False, "closed pull-request response was invalid")

    if len(candidates) != 1:
        return ValidationReuseDecision(
            False,
            "main commit is not tied to exactly one merged owner pull request",
        )

    pull_request = candidates[0]
    pull_request_number = pull_request.get("number")
    head = pull_request["head"]
    head_sha = str(head.get("sha", "")).lower()
    head_ref = head.get("ref")
    if not isinstance(pull_request_number, int) or not SHA_PATTERN.fullmatch(head_sha):
        return ValidationReuseDecision(False, "merged pull request head metadata was invalid")

    main_commit_url = (
        f"{api_url.rstrip('/')}/repos/{encoded_repo}/git/commits/"
        f"{quote(normalized_sha, safe='')}"
    )
    head_commit_url = (
        f"{api_url.rstrip('/')}/repos/{encoded_repo}/git/commits/"
        f"{quote(head_sha, safe='')}"
    )
    main_tree_sha = _commit_tree_sha(fetch_json(main_commit_url, token))
    head_tree_sha = _commit_tree_sha(fetch_json(head_commit_url, token))
    if main_tree_sha is None or head_tree_sha is None:
        return ValidationReuseDecision(
            False,
            "merged or validated-head commit tree metadata was invalid",
            pull_request_number=pull_request_number,
            validated_head_sha=head_sha,
        )
    if main_tree_sha != head_tree_sha:
        return ValidationReuseDecision(
            False,
            "merged commit tree differs from the validated pull-request head tree",
            pull_request_number=pull_request_number,
            validated_head_sha=head_sha,
        )

    query = urlencode(
        {
            "event": "pull_request",
            "head_sha": head_sha,
            "status": "success",
            "per_page": 100,
        }
    )
    runs_url = (
        f"{api_url.rstrip('/')}/repos/{encoded_repo}/actions/workflows/"
        f"{quote(workflow_file, safe='')}/runs?{query}"
    )
    runs_payload = fetch_json(runs_url, token)
    if not isinstance(runs_payload, dict):
        return ValidationReuseDecision(False, "workflow-run response was invalid")
    workflow_runs = runs_payload.get("workflow_runs")
    if not isinstance(workflow_runs, list):
        return ValidationReuseDecision(False, "workflow-run list was invalid")

    matching_runs: list[dict[str, Any]] = []
    for run in workflow_runs:
        if not isinstance(run, dict):
            continue
        run_pull_requests = run.get("pull_requests")
        actor = run.get("actor")
        if not isinstance(run_pull_requests, list) or not isinstance(actor, dict):
            continue
        run_pr_numbers = {
            candidate.get("number")
            for candidate in run_pull_requests
            if isinstance(candidate, dict)
        }
        if (
            run.get("event") == "pull_request"
            and run.get("status") == "completed"
            and run.get("conclusion") == "success"
            and str(run.get("head_sha", "")).lower() == head_sha
            and run.get("head_branch") == head_ref
            and pull_request_number in run_pr_numbers
            and actor.get("login") == owner
        ):
            matching_runs.append(run)

    if not matching_runs:
        return ValidationReuseDecision(
            False,
            "no exact successful owner pull-request validation was found",
            pull_request_number=pull_request_number,
            validated_head_sha=head_sha,
        )

    latest_run = max(
        matching_runs,
        key=lambda run: (int(run.get("run_number") or 0), int(run.get("id") or 0)),
    )
    run_id = latest_run.get("id")
    if not isinstance(run_id, int):
        return ValidationReuseDecision(False, "successful workflow run ID was invalid")

    return ValidationReuseDecision(
        True,
        "exact merged PR head already passed the full unified validation",
        pull_request_number=pull_request_number,
        validated_head_sha=head_sha,
        workflow_run_id=run_id,
    )


def _write_github_outputs(path: Path, decision: ValidationReuseDecision) -> None:
    values = {
        "reuse_validation": "true" if decision.reuse_validation else "false",
        "validated_pr_number": str(decision.pull_request_number or ""),
        "validated_head_sha": decision.validated_head_sha or "",
        "validated_workflow_run_id": str(decision.workflow_run_id or ""),
    }
    with path.open("a", encoding="utf-8", newline="\n") as output:
        for key, value in values.items():
            output.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fail-closed proof that a main commit may reuse an exact successful "
            "pull-request validation."
        )
    )
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--workflow-file", required=True)
    parser.add_argument("--base-ref", default="main")
    parser.add_argument("--github-output", type=Path, required=True)
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--api-url", default=os.getenv("GITHUB_API_URL", "https://api.github.com"))
    args = parser.parse_args()

    try:
        decision = decide_validation_reuse(
            repository=args.repository,
            commit_sha=args.commit_sha,
            workflow_file=args.workflow_file,
            base_ref=args.base_ref,
            token=os.getenv(args.token_env, ""),
            api_url=args.api_url,
        )
    except Exception as exc:  # Network/API uncertainty must run the full suite.
        decision = ValidationReuseDecision(
            False,
            f"GitHub validation proof was unavailable: {type(exc).__name__}",
        )

    _write_github_outputs(args.github_output, decision)
    print(
        "PR validation reuse: "
        f"reuse={decision.reuse_validation}, reason={decision.reason}, "
        f"pr={decision.pull_request_number}, head={decision.validated_head_sha}, "
        f"run={decision.workflow_run_id}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

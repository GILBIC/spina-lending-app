from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = "GILBIC/spina-lending-app"
MAIN_SHA = "a" * 40
HEAD_SHA = "b" * 40
TREE_SHA = "c" * 40
TOOL_PATH = Path(__file__).resolve().parents[2] / "tools" / "reuse_validated_pr_ci.py"
SPEC = importlib.util.spec_from_file_location("reuse_validated_pr_ci", TOOL_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _pull_request(
    *,
    head_repo: str | None = REPOSITORY,
    head_sha: str = HEAD_SHA,
    repository_identity: str = REPOSITORY,
    user_login: str = "GILBIC",
    merge_commit_sha: str | None = None,
    merged: bool = True,
    merged_at: str | None = "2026-08-10T06:00:00Z",
    include_merge_detail: bool = True,
) -> dict[str, object]:
    pull_request: dict[str, object] = {
        "number": 286,
        "state": "closed",
        "merge_commit_sha": merge_commit_sha,
        "user": {"login": user_login},
        "head": {
            "sha": head_sha,
            "ref": "agent/focused-accounting-ci",
            "repo": {"full_name": head_repo} if head_repo else None,
        },
        "base": {
            "ref": "main",
            "repo": {"full_name": repository_identity},
        },
    }
    if include_merge_detail:
        pull_request["merged"] = merged
        pull_request["merged_at"] = merged_at
    return pull_request


def _workflow_run(
    *,
    conclusion: str = "success",
    pull_request_number: int | None = None,
    head_repository: str = REPOSITORY,
    actor_login: str = "GILBIC",
) -> dict[str, object]:
    return {
        "id": 123456,
        "run_number": 289,
        "event": "pull_request",
        "status": "completed",
        "conclusion": conclusion,
        "head_sha": HEAD_SHA,
        "head_branch": "agent/focused-accounting-ci",
        "actor": {"login": actor_login},
        "head_repository": {"full_name": head_repository},
        "pull_requests": (
            [{"number": pull_request_number}]
            if pull_request_number is not None
            else []
        ),
    }


class ValidationReuseDecisionTests(unittest.TestCase):
    def _decide(
        self,
        *,
        pulls: object,
        workflow_runs: object,
        pull_detail: object | None = None,
        main_tree_sha: str | None = TREE_SHA,
        head_tree_sha: str | None = TREE_SHA,
    ) -> object:
        def fetch_json(url: str, token: str) -> object:
            self.assertEqual(token, "token")
            if url.endswith("/pulls"):
                return pulls
            if url.endswith("/pulls/286"):
                return _pull_request() if pull_detail is None else pull_detail
            if f"/git/commits/{MAIN_SHA}" in url:
                return {"tree": {"sha": main_tree_sha}} if main_tree_sha else {}
            if f"/git/commits/{HEAD_SHA}" in url:
                return {"tree": {"sha": head_tree_sha}} if head_tree_sha else {}
            self.assertIn("/actions/workflows/spina-ci.yml/runs?", url)
            self.assertIn(f"head_sha={HEAD_SHA}", url)
            self.assertIn("event=pull_request", url)
            self.assertIn("status=success", url)
            return {"workflow_runs": workflow_runs}

        return MODULE.decide_validation_reuse(
            repository=REPOSITORY,
            commit_sha=MAIN_SHA,
            workflow_file="spina-ci.yml",
            base_ref="main",
            token="token",
            fetch_json=fetch_json,
            association_attempts=1,
            association_retry_seconds=0,
            sleep=lambda _: None,
        )

    def test_exact_successful_owner_pr_reuses_full_validation(self) -> None:
        decision = self._decide(
            pulls=[_pull_request(include_merge_detail=False)],
            workflow_runs=[_workflow_run()],
        )

        self.assertTrue(decision.reuse_validation)
        self.assertEqual(decision.pull_request_number, 286)
        self.assertEqual(decision.validated_head_sha, HEAD_SHA)
        self.assertEqual(decision.workflow_run_id, 123456)

    def test_direct_push_fails_closed_to_full_validation(self) -> None:
        decision = self._decide(pulls=[], workflow_runs=[])

        self.assertFalse(decision.reuse_validation)
        self.assertIn("not tied", decision.reason)

    def test_invalid_commit_association_response_fails_closed(self) -> None:
        decision = self._decide(
            pulls={"invalid": True},
            workflow_runs=[_workflow_run()],
        )

        self.assertFalse(decision.reuse_validation)
        self.assertIn("associated pull-request response was invalid", decision.reason)

    def test_identity_matching_is_case_insensitive(self) -> None:
        decision = self._decide(
            pulls=[
                _pull_request(
                    repository_identity="gilbic/spina-lending-app",
                    user_login="gilbic",
                )
            ],
            workflow_runs=[
                _workflow_run(
                    head_repository="gilbic/spina-lending-app",
                    actor_login="gilbic",
                )
            ],
        )

        self.assertTrue(decision.reuse_validation)

    def test_missing_pr_head_repo_uses_successful_run_repository_proof(self) -> None:
        decision = self._decide(
            pulls=[_pull_request(head_repo=None)],
            pull_detail=_pull_request(head_repo=None),
            workflow_runs=[_workflow_run()],
        )

        self.assertTrue(decision.reuse_validation)

    def test_failed_pr_run_fails_closed_to_full_validation(self) -> None:
        decision = self._decide(
            pulls=[_pull_request()],
            workflow_runs=[_workflow_run(conclusion="failure")],
        )

        self.assertFalse(decision.reuse_validation)
        self.assertEqual(decision.pull_request_number, 286)

    def test_unmerged_pull_request_detail_fails_closed(self) -> None:
        decision = self._decide(
            pulls=[_pull_request(include_merge_detail=False)],
            pull_detail=_pull_request(merged=False, merged_at=None),
            workflow_runs=[_workflow_run()],
        )

        self.assertFalse(decision.reuse_validation)
        self.assertIn("not tied", decision.reason)

    def test_invalid_pull_request_detail_fails_closed(self) -> None:
        decision = self._decide(
            pulls=[_pull_request(include_merge_detail=False)],
            pull_detail={"invalid": True},
            workflow_runs=[_workflow_run()],
        )

        self.assertFalse(decision.reuse_validation)
        self.assertIn("detail response was invalid", decision.reason)

    def test_pull_request_summary_detail_disagreement_fails_closed(self) -> None:
        decision = self._decide(
            pulls=[_pull_request(head_sha="d" * 40, include_merge_detail=False)],
            pull_detail=_pull_request(),
            workflow_runs=[_workflow_run()],
        )

        self.assertFalse(decision.reuse_validation)
        self.assertIn("summary and detail disagreed", decision.reason)

    def test_different_merged_tree_fails_closed_to_full_validation(self) -> None:
        decision = self._decide(
            pulls=[_pull_request()],
            workflow_runs=[_workflow_run()],
            head_tree_sha="d" * 40,
        )

        self.assertFalse(decision.reuse_validation)
        self.assertIn("tree differs", decision.reason)
        self.assertEqual(decision.pull_request_number, 286)
        self.assertEqual(decision.validated_head_sha, HEAD_SHA)

    def test_missing_commit_tree_metadata_fails_closed_to_full_validation(self) -> None:
        decision = self._decide(
            pulls=[_pull_request()],
            workflow_runs=[_workflow_run()],
            main_tree_sha=None,
        )

        self.assertFalse(decision.reuse_validation)
        self.assertIn("tree metadata was invalid", decision.reason)

    def test_successful_run_for_another_pr_is_not_reused(self) -> None:
        decision = self._decide(
            pulls=[_pull_request()],
            workflow_runs=[_workflow_run(pull_request_number=999)],
        )

        self.assertFalse(decision.reuse_validation)

    def test_fork_pr_is_not_reused(self) -> None:
        decision = self._decide(
            pulls=[_pull_request(head_repo="someone/fork")],
            pull_detail=_pull_request(head_repo="someone/fork"),
            workflow_runs=[_workflow_run(head_repository="someone/fork")],
        )

        self.assertFalse(decision.reuse_validation)

    def test_commit_association_is_retried_before_failing_closed(self) -> None:
        associated_responses = iter([[], [_pull_request()]])
        sleeps: list[float] = []

        def fetch_json(url: str, token: str) -> object:
            self.assertEqual(token, "token")
            if url.endswith("/pulls"):
                return next(associated_responses)
            if url.endswith("/pulls/286"):
                return _pull_request()
            if f"/git/commits/{MAIN_SHA}" in url:
                return {"tree": {"sha": TREE_SHA}}
            if f"/git/commits/{HEAD_SHA}" in url:
                return {"tree": {"sha": TREE_SHA}}
            return {"workflow_runs": [_workflow_run()]}

        decision = MODULE.decide_validation_reuse(
            repository=REPOSITORY,
            commit_sha=MAIN_SHA,
            workflow_file="spina-ci.yml",
            base_ref="main",
            token="token",
            fetch_json=fetch_json,
            association_attempts=2,
            association_retry_seconds=3,
            sleep=sleeps.append,
        )

        self.assertTrue(decision.reuse_validation)
        self.assertEqual(sleeps, [3])

    def test_github_outputs_are_explicit_for_reuse_and_fallback(self) -> None:
        output_path = Path(__file__).with_suffix(".outputs.tmp")
        try:
            MODULE._write_github_outputs(
                output_path,
                MODULE.ValidationReuseDecision(False, "fallback"),
            )
            self.assertEqual(
                output_path.read_text(encoding="utf-8").splitlines(),
                [
                    "reuse_validation=false",
                    "validated_pr_number=",
                    "validated_head_sha=",
                    "validated_workflow_run_id=",
                ],
            )
        finally:
            output_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

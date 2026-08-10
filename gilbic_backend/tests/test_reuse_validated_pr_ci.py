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


def _pull_request(*, head_repo: str = REPOSITORY) -> dict[str, object]:
    return {
        "number": 286,
        "state": "closed",
        "merged_at": "2026-08-10T06:00:00Z",
        "merge_commit_sha": MAIN_SHA,
        "user": {"login": "GILBIC"},
        "head": {
            "sha": HEAD_SHA,
            "ref": "agent/focused-accounting-ci",
            "repo": {"full_name": head_repo},
        },
        "base": {
            "ref": "main",
            "repo": {"full_name": REPOSITORY},
        },
    }


def _workflow_run(
    *,
    conclusion: str = "success",
    pull_request_number: int = 286,
) -> dict[str, object]:
    return {
        "id": 123456,
        "run_number": 289,
        "event": "pull_request",
        "status": "completed",
        "conclusion": conclusion,
        "head_sha": HEAD_SHA,
        "head_branch": "agent/focused-accounting-ci",
        "actor": {"login": "GILBIC"},
        "pull_requests": [{"number": pull_request_number}],
    }


class ValidationReuseDecisionTests(unittest.TestCase):
    def _decide(
        self,
        *,
        pulls: object,
        workflow_runs: object,
        main_tree_sha: str | None = TREE_SHA,
        head_tree_sha: str | None = TREE_SHA,
    ) -> object:
        def fetch_json(url: str, token: str) -> object:
            self.assertEqual(token, "token")
            if url.endswith("/pulls"):
                return pulls
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
        )

    def test_exact_successful_owner_pr_reuses_full_validation(self) -> None:
        decision = self._decide(
            pulls=[_pull_request()],
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

    def test_failed_pr_run_fails_closed_to_full_validation(self) -> None:
        decision = self._decide(
            pulls=[_pull_request()],
            workflow_runs=[_workflow_run(conclusion="failure")],
        )

        self.assertFalse(decision.reuse_validation)
        self.assertEqual(decision.pull_request_number, 286)

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
            workflow_runs=[_workflow_run()],
        )

        self.assertFalse(decision.reuse_validation)

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

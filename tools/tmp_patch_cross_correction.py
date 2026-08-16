from __future__ import annotations

import base64
import json
import os
import urllib.parse
import urllib.request

REPO = "GILBIC/spina-lending-app"
BRANCH = "mobile/ca4-collector-ui"
WORKFLOW_PATH = ".github/workflows/zz_tmp_cross_correction_patch.yml"
HELPER_PATH = "tools/tmp_patch_cross_correction.py"


def _request_json(method: str, url: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    headers = {
        "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "spina-cross-correction-patch",
    }
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request) as response:
        body = response.read()
    return json.loads(body) if body else {}


def _url(path: str, *, ref: bool = False) -> str:
    encoded = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
    base = f"https://api.github.com/repos/{REPO}/contents/{encoded}"
    if ref:
        return f"{base}?ref={urllib.parse.quote(BRANCH, safe='')}"
    return base


def _load(path: str) -> tuple[str, str]:
    meta = _request_json("GET", _url(path, ref=True))
    return base64.b64decode(str(meta["content"])).decode("utf-8"), str(meta["sha"])


def _save(path: str, text: str, sha: str, message: str) -> None:
    _request_json(
        "PUT",
        _url(path),
        {
            "message": message,
            "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            "sha": sha,
            "branch": BRANCH,
        },
    )


def _delete(path: str, message: str) -> None:
    try:
        meta = _request_json("GET", _url(path, ref=True))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return
        raise
    _request_json(
        "DELETE",
        _url(path),
        {"message": message, "sha": str(meta["sha"]), "branch": BRANCH},
    )


def _replace_once(text: str, old: str, new: str, name: str) -> str:
    if old in text:
        count = text.count(old)
        if count != 1:
            raise RuntimeError(f"{name}: expected one match, found {count}")
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise RuntimeError(f"{name}: target not found")


def _patch_correction_repository() -> None:
    path = "gilbic_backend/src/gilbic_backend/collection_correction_repository.py"
    text, sha = _load(path)
    text = _replace_once(
        text,
        "from .database import open_connection\n",
        "from .collection_correction_authority import (\n"
        "    collector_may_correct_unremitted,\n"
        "    correction_revision_is_current,\n"
        ")\n"
        "from .database import open_connection\n",
        "correction authority import",
    )
    text = _replace_once(
        text,
        "        reason: str,\n    ) -> CollectionCorrectionRecord:\n",
        "        reason: str,\n        expected_route_revision: str,\n    ) -> CollectionCorrectionRecord:\n",
        "repository signature",
    )
    text = _replace_once(
        text,
        """                    if transaction[\"collector_user_id\"] != actor_user_id:\n                        raise CollectionCorrectionForbidden(\n                            \"Only the collector who recorded this entry may correct it.\"\n                        )\n""",
        """                    if not collector_may_correct_unremitted(\n                        actor_user_id=actor_user_id,\n                        recorder_user_id=transaction[\"collector_user_id\"],\n                        assigned_collector_user_id=transaction.get(\n                            \"assigned_collector_user_id\"\n                        ),\n                        collection_origin=str(\n                            transaction.get(\"collection_origin\") or \"\"\n                        ),\n                    ):\n                        raise CollectionCorrectionForbidden(\n                            \"Only the original collector or assigned collector may correct this unlocked cross-area entry.\"\n                        )\n""",
        "cross-collector authority",
    )
    text = _replace_once(
        text,
        """                    if transaction[\"is_locked\"] or transaction[\"remittance_id\"] is not None:\n                        raise CollectionCorrectionLocked(\n                            \"This entry is already included in a remittance and cannot be edited.\"\n                        )\n\n                    details = (\n""",
        """                    if transaction[\"is_locked\"] or transaction[\"remittance_id\"] is not None:\n                        raise CollectionCorrectionLocked(\n                            \"This entry is already included in a remittance and cannot be edited.\"\n                        )\n                    if not correction_revision_is_current(\n                        expected_route_revision=expected_route_revision,\n                        loan_id=transaction[\"loan_id\"],\n                        state_version=int(transaction[\"state_version\"]),\n                    ):\n                        raise CollectionCorrectionConflict(\n                            \"This collection changed after you opened it. Refresh before correcting it.\"\n                        )\n\n                    details = (\n""",
        "stale route revision guard",
    )
    _save(path, text, sha, "Backend: allow assigned owner to correct unlocked cross-area receipt")


def _patch_route_repository() -> None:
    path = "gilbic_backend/src/gilbic_backend/collector_route_repository.py"
    text, sha = _load(path)
    text = _replace_once(
        text,
        """                        today.collector_user_id as today_collector_user_id,\n                        coalesce(today.is_locked, false) as today_is_locked,\n""",
        """                        today.collector_user_id as today_collector_user_id,\n                        today.assigned_collector_user_id as today_assigned_collector_user_id,\n                        coalesce(today.collection_origin, '') as today_collection_origin,\n                        coalesce(today.is_locked, false) as today_is_locked,\n""",
        "route outer authority fields",
    )
    text = _replace_once(
        text,
        """                            t.collector_user_id,\n                            t.is_locked,\n""",
        """                            t.collector_user_id,\n                            t.assigned_collector_user_id,\n                            t.collection_origin,\n                            t.is_locked,\n""",
        "route lateral authority fields",
    )
    text = _replace_once(
        text,
        """                    can_edit_today=(\n                        row[\"today_transaction_id\"] is not None\n                        and row[\"today_collector_user_id\"] == collector_user_id\n                        and not bool(row[\"today_is_locked\"])\n                    ),\n""",
        """                    can_edit_today=(\n                        row[\"today_transaction_id\"] is not None\n                        and not bool(row[\"today_is_locked\"])\n                        and (\n                            row[\"today_collector_user_id\"] == collector_user_id\n                            or (\n                                str(row[\"today_collection_origin\"] or \"\")\n                                == \"cross_collector\"\n                                and row[\"today_assigned_collector_user_id\"]\n                                == collector_user_id\n                            )\n                        )\n                    ),\n""",
        "route assigned owner edit flag",
    )
    _save(path, text, sha, "Backend: expose assigned-owner cross-area correction access")


def _patch_mobile_route_page() -> None:
    path = "gilbic_mobile/lib/src/features/collector/collector_route_page.dart"
    text, sha = _load(path)
    text = _replace_once(
        text,
        "return 'Only the collector who recorded this entry may edit it before remittance.';",
        "return 'Only the original collector or assigned collector may edit this unlocked entry before remittance.';",
        "route correction guidance",
    )
    _save(path, text, sha, "Mobile: explain shared cross-area edit authority")


def _patch_correction_page() -> None:
    path = "gilbic_mobile/lib/src/features/collector/collection_correction_page.dart"
    text, sha = _load(path)
    text = _replace_once(
        text,
        "'Only the collector who recorded this unlocked entry may edit it.';",
        "'Only the original collector or assigned collector may edit this unlocked entry.';",
        "correction page authority guidance",
    )
    text = _replace_once(
        text,
        """      note: _noteController.text,\n      reason: _reasonController.text,\n    );\n""",
        """      note: _noteController.text,\n      reason: _reasonController.text,\n      expectedRouteRevision: widget.entry.routeRevision ?? '',\n    );\n""",
        "correction draft revision",
    )
    _save(path, text, sha, "Mobile: fail stale collection corrections closed")


def _patch_api_tests() -> None:
    path = "gilbic_backend/tests/test_collection_correction_api.py"
    text, sha = _load(path)
    first = '            "reason": "Wrong date tapped",\n'
    text = _replace_once(
        text,
        first,
        first + '            "expected_route_revision": f"loan:{LOAN_ID}:v1",\n',
        "API success revision",
    )
    second = '            "reason": "Wrong amount",\n'
    text = _replace_once(
        text,
        second,
        second + '            "expected_route_revision": f"loan:{LOAN_ID}:v1",\n',
        "API locked revision",
    )
    text = _replace_once(
        text,
        '    assert corrections.request["reason"] == "Wrong date tapped"\n',
        '    assert corrections.request["reason"] == "Wrong date tapped"\n'
        '    assert corrections.request["expected_route_revision"] == f"loan:{LOAN_ID}:v1"\n',
        "API revision forwarding assertion",
    )
    _save(path, text, sha, "Test: require correction route revision")


def _patch_contract_test() -> None:
    path = "gilbic_backend/tests/test_contract_collection_posting.py"
    text, sha = _load(path)
    text = _replace_once(
        text,
        """            note=\"\",\n            reason=\"wrong amount\",\n        )\n""",
        """            note=\"\",\n            reason=\"wrong amount\",\n            expected_route_revision=f\"loan:{LOAN_ID}:v1\",\n        )\n""",
        "contract correction revision",
    )
    _save(path, text, sha, "Test: preserve contract correction revision guard")


def main() -> None:
    _patch_correction_repository()
    _patch_route_repository()
    _patch_mobile_route_page()
    _patch_correction_page()
    _patch_api_tests()
    _patch_contract_test()
    _delete(WORKFLOW_PATH, "CI: remove temporary cross-correction workflow")
    _delete(HELPER_PATH, "CI: remove temporary cross-correction helper")


if __name__ == "__main__":
    main()

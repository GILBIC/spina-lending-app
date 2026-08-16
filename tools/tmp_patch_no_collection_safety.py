from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

REPO = "GILBIC/spina-lending-app"
BRANCH = "mobile/ca4-collector-ui"
WORKFLOW_PATH = ".github/workflows/zz_tmp_no_collection_safety.yml"
HELPER_PATH = "tools/tmp_patch_no_collection_safety.py"


def request_json(method: str, url: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    headers = {
        "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "spina-no-collection-safety",
    }
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request) as response:
        body = response.read()
    return json.loads(body) if body else {}


def content_url(path: str, *, ref: bool = False) -> str:
    encoded = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
    url = f"https://api.github.com/repos/{REPO}/contents/{encoded}"
    return f"{url}?ref={urllib.parse.quote(BRANCH, safe='')}" if ref else url


def load(path: str) -> tuple[str, str]:
    meta = request_json("GET", content_url(path, ref=True))
    return base64.b64decode(str(meta["content"])).decode("utf-8"), str(meta["sha"])


def save(path: str, text: str, sha: str, message: str) -> None:
    request_json(
        "PUT",
        content_url(path),
        {
            "message": message,
            "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            "sha": sha,
            "branch": BRANCH,
        },
    )


def delete(path: str, message: str) -> None:
    try:
        meta = request_json("GET", content_url(path, ref=True))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return
        raise
    request_json(
        "DELETE",
        content_url(path),
        {"message": message, "sha": str(meta["sha"]), "branch": BRANCH},
    )


def replace_once(text: str, old: str, new: str, name: str) -> str:
    if old in text:
        count = text.count(old)
        if count != 1:
            raise RuntimeError(f"{name}: expected one match, found {count}")
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise RuntimeError(f"{name}: target not found")


def patch_route_query() -> None:
    path = "gilbic_backend/src/gilbic_backend/collector_route_repository.py"
    text, sha = load(path)
    text = text.replace("balance.due_date", "balance.effective_due_date")
    if "balance.due_date" in text:
        raise RuntimeError("Collector route still references balance.due_date")
    save(path, text, sha, "Backend: fix Collector effective due-date query")


def patch_contract_posting() -> None:
    path = "gilbic_backend/src/gilbic_backend/contract_collection_posting.py"
    text, sha = load(path)
    text = text.replace('row["due_date"]', 'row["effective_due_date"]')
    if 'row["due_date"]' in text:
        raise RuntimeError("Contract posting still reads due_date after selecting effective_due_date")
    save(path, text, sha, "Backend: read operational due dates in contract posting")


def patch_management_repository() -> None:
    path = "gilbic_backend/src/gilbic_backend/management_no_collection_repository.py"
    text, sha = load(path)

    text = replace_once(
        text,
        "        requested = tuple(selections)\n",
        "        requested = tuple(sorted(selections, key=lambda item: str(item.loan_id)))\n",
        "deterministic multi-loan lock order",
    )

    reverse_marker = '''                if original["status"] != "active" or original["registration_id"] is None:\n                    raise ManagementNoCollectionConflict(\n                        "Only the current verified active schedule can be adjusted."\n                    )\n\n                state_version = self._lock_operational_state(\n'''
    reverse_replacement = '''                if original["status"] != "active" or original["registration_id"] is None:\n                    raise ManagementNoCollectionConflict(\n                        "Only the current verified active schedule can be adjusted."\n                    )\n                self._lock_loan(cursor, loan_id=original["loan_id"])\n\n                state_version = self._lock_operational_state(\n'''
    text = replace_once(text, reverse_marker, reverse_replacement, "reversal loan lock")

    reverse_version_marker = '''                self._set_operational_version(\n                    cursor,\n                    schedule_id=original["schedule_id"],\n                    expected_version=state_version,\n                    resulting_version=resulting_version,\n                    actor_user_id=actor_user_id,\n                )\n\n                return NoCollectionAdjustmentRecord(\n'''
    reverse_version_replacement = '''                self._set_operational_version(\n                    cursor,\n                    schedule_id=original["schedule_id"],\n                    expected_version=state_version,\n                    resulting_version=resulting_version,\n                    actor_user_id=actor_user_id,\n                )\n                self._invalidate_mobile_route_revision(\n                    cursor,\n                    loan_id=original["loan_id"],\n                )\n\n                return NoCollectionAdjustmentRecord(\n'''
    text = replace_once(
        text,
        reverse_version_marker,
        reverse_version_replacement,
        "reversal route invalidation",
    )

    declare_marker = '''            if schedule["registration_id"] is None:\n                raise ManagementNoCollectionConflict(\n                    "No Collection requires a verified registered contractual schedule."\n                )\n\n            state_version = self._lock_operational_state(\n'''
    declare_replacement = '''            if schedule["registration_id"] is None:\n                raise ManagementNoCollectionConflict(\n                    "No Collection requires a verified registered contractual schedule."\n                )\n            self._lock_loan(cursor, loan_id=selection.loan_id)\n\n            state_version = self._lock_operational_state(\n'''
    text = replace_once(text, declare_marker, declare_replacement, "declaration loan lock")

    declare_version_marker = '''            self._set_operational_version(\n                cursor,\n                schedule_id=schedule["schedule_id"],\n                expected_version=state_version,\n                resulting_version=resulting_version,\n                actor_user_id=actor_user_id,\n            )\n\n            return NoCollectionAdjustmentRecord(\n'''
    declare_version_replacement = '''            self._set_operational_version(\n                cursor,\n                schedule_id=schedule["schedule_id"],\n                expected_version=state_version,\n                resulting_version=resulting_version,\n                actor_user_id=actor_user_id,\n            )\n            self._invalidate_mobile_route_revision(\n                cursor,\n                loan_id=selection.loan_id,\n            )\n\n            return NoCollectionAdjustmentRecord(\n'''
    text = replace_once(
        text,
        declare_version_marker,
        declare_version_replacement,
        "declaration route invalidation",
    )

    helper_marker = '''    @staticmethod\n    def _lock_operational_state(cursor: Any, *, schedule_id: UUID) -> int:\n'''
    helper_replacement = '''    @staticmethod\n    def _lock_loan(cursor: Any, *, loan_id: UUID) -> None:\n        cursor.execute(\n            "select id from lending.loans where id = %s for update",\n            (loan_id,),\n        )\n        if cursor.fetchone() is None:\n            raise ManagementNoCollectionNotFound(\n                "The selected loan no longer exists."\n            )\n\n    @staticmethod\n    def _invalidate_mobile_route_revision(cursor: Any, *, loan_id: UUID) -> None:\n        cursor.execute(\n            """\n            update lending.loan_collection_state\n            set state_version = state_version + 1,\n                updated_at = now()\n            where loan_id = %s\n            """,\n            (loan_id,),\n        )\n\n    @staticmethod\n    def _lock_operational_state(cursor: Any, *, schedule_id: UUID) -> int:\n'''
    text = replace_once(text, helper_marker, helper_replacement, "repository safety helpers")

    save(
        path,
        text,
        sha,
        "Backend: serialize No Collection with payments and invalidate stale routes",
    )


def main() -> None:
    patch_route_query()
    patch_contract_posting()
    patch_management_repository()
    delete(WORKFLOW_PATH, "CI: remove temporary No Collection safety workflow")
    delete(HELPER_PATH, "CI: remove temporary No Collection safety helper")


if __name__ == "__main__":
    main()

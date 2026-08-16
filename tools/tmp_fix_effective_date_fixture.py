from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

REPO = "GILBIC/spina-lending-app"
BRANCH = "mobile/ca4-collector-ui"
TEST_PATH = "gilbic_backend/tests/test_contract_collection_posting.py"
REPOSITORY_PATH = "gilbic_backend/src/gilbic_backend/management_no_collection_repository.py"
WORKFLOW_PATH = ".github/workflows/zz_tmp_effective_date_fixture_cleanup.yml"
HELPER_PATH = "tools/tmp_fix_effective_date_fixture.py"


def request_json(method: str, url: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    headers = {
        "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "spina-effective-date-fixture-cleanup",
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


def save(path: str, content: str, sha: str, message: str) -> None:
    request_json(
        "PUT",
        content_url(path),
        {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
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
        if text.count(old) != 1:
            raise RuntimeError(f"{name}: expected exactly one match")
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise RuntimeError(f"{name}: target not found")


def patch_effective_date_fixture() -> None:
    text, sha = load(TEST_PATH)
    old0 = '            "due_date": selected[0],'
    old1 = '            "due_date": selected[1],'
    new0 = '            "effective_due_date": selected[0],'
    new1 = '            "effective_due_date": selected[1],'
    original = text
    text = text.replace(old0, new0).replace(old1, new1)
    if old0 in text or old1 in text:
        raise RuntimeError("Stale due_date fixture remains after patch")
    if text != original:
        save(
            TEST_PATH,
            text,
            sha,
            "Test: align contract ADV fixture with effective collection dates",
        )


def patch_no_collection_lock_order() -> None:
    text, sha = load(REPOSITORY_PATH)
    original = text

    reverse_open = '''        with open_connection() as connection:\n            with connection.cursor(row_factory=dict_row) as cursor:\n                cursor.execute(\n                    """\n                    select\n                        adjustment.id,\n                        adjustment.loan_id,\n'''
    reverse_locked = '''        with open_connection() as connection:\n            with connection.cursor(row_factory=dict_row) as cursor:\n                cursor.execute(\n                    """\n                    select loan_id\n                    from lending.loan_schedule_adjustments\n                    where id = %s\n                      and adjustment_type = 'no_collection'\n                    """,\n                    (adjustment_id,),\n                )\n                target = cursor.fetchone()\n                if target is None:\n                    raise ManagementNoCollectionNotFound(\n                        "The No Collection adjustment was not found."\n                    )\n                self._lock_loan(cursor, loan_id=target["loan_id"])\n\n                cursor.execute(\n                    """\n                    select\n                        adjustment.id,\n                        adjustment.loan_id,\n'''
    text = replace_once(text, reverse_open, reverse_locked, "reversal loan-first lock")

    reverse_late_lock = '''                if original["status"] != "active" or original["registration_id"] is None:\n                    raise ManagementNoCollectionConflict(\n                        "Only the current verified active schedule can be adjusted."\n                    )\n                self._lock_loan(cursor, loan_id=original["loan_id"])\n\n                state_version = self._lock_operational_state(\n'''
    reverse_no_late_lock = '''                if original["status"] != "active" or original["registration_id"] is None:\n                    raise ManagementNoCollectionConflict(\n                        "Only the current verified active schedule can be adjusted."\n                    )\n                if original["loan_id"] != target["loan_id"]:\n                    raise ManagementNoCollectionConflict(\n                        "The No Collection adjustment changed while it was being locked."\n                    )\n\n                state_version = self._lock_operational_state(\n'''
    text = replace_once(
        text,
        reverse_late_lock,
        reverse_no_late_lock,
        "remove reversal late loan lock",
    )

    declare_open = '''    ) -> NoCollectionAdjustmentRecord:\n        with connection.cursor(row_factory=dict_row) as cursor:\n            cursor.execute(\n                """\n                select\n                    schedule.id as schedule_id,\n'''
    declare_locked = '''    ) -> NoCollectionAdjustmentRecord:\n        with connection.cursor(row_factory=dict_row) as cursor:\n            self._lock_loan(cursor, loan_id=selection.loan_id)\n            cursor.execute(\n                """\n                select\n                    schedule.id as schedule_id,\n'''
    text = replace_once(text, declare_open, declare_locked, "declaration loan-first lock")

    declare_late_lock = '''            if schedule["registration_id"] is None:\n                raise ManagementNoCollectionConflict(\n                    "No Collection requires a verified registered contractual schedule."\n                )\n            self._lock_loan(cursor, loan_id=selection.loan_id)\n\n            state_version = self._lock_operational_state(\n'''
    declare_no_late_lock = '''            if schedule["registration_id"] is None:\n                raise ManagementNoCollectionConflict(\n                    "No Collection requires a verified registered contractual schedule."\n                )\n\n            state_version = self._lock_operational_state(\n'''
    text = replace_once(
        text,
        declare_late_lock,
        declare_no_late_lock,
        "remove declaration late loan lock",
    )

    if text != original:
        save(
            REPOSITORY_PATH,
            text,
            sha,
            "Backend: lock loan before No Collection schedule rows",
        )


def main() -> None:
    patch_effective_date_fixture()
    patch_no_collection_lock_order()
    delete(WORKFLOW_PATH, "CI: remove temporary effective-date fixture workflow")
    delete(HELPER_PATH, "CI: remove temporary effective-date fixture helper")


if __name__ == "__main__":
    main()

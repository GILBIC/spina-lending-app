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


def main() -> None:
    text, sha = load(TEST_PATH)
    old0 = '            "due_date": selected[0],'
    old1 = '            "due_date": selected[1],'
    new0 = '            "effective_due_date": selected[0],'
    new1 = '            "effective_due_date": selected[1],'
    if old0 in text or old1 in text:
        text = text.replace(old0, new0).replace(old1, new1)
        save(
            TEST_PATH,
            text,
            sha,
            "Test: align contract ADV fixture with effective collection dates",
        )
    if old0 in text or old1 in text:
        raise RuntimeError("Stale due_date fixture remains after patch")

    delete(WORKFLOW_PATH, "CI: remove temporary effective-date fixture workflow")
    delete(HELPER_PATH, "CI: remove temporary effective-date fixture helper")


if __name__ == "__main__":
    main()

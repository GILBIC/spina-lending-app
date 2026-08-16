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


def request_json(method: str, url: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    headers = {
        "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "spina-cross-correction-finish",
    }
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as response:
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


def replace_once(text: str, old: str, new: str, name: str) -> str:
    if old in text:
        if text.count(old) != 1:
            raise RuntimeError(f"{name}: ambiguous target")
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise RuntimeError(f"{name}: target not found")


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


def patch_correction_page() -> None:
    path = "gilbic_mobile/lib/src/features/collector/collection_correction_page.dart"
    text, sha = load(path)
    text = replace_once(
        text,
        "'Only the collector who recorded this unlocked entry may edit it.';",
        "'Only the original collector or assigned collector may edit this unlocked entry.';",
        "authority guidance",
    )
    text = replace_once(
        text,
        """      note: _noteController.text,\n      reason: _reasonController.text,\n    );\n""",
        """      note: _noteController.text,\n      reason: _reasonController.text,\n      expectedRouteRevision: widget.entry.routeRevision ?? '',\n    );\n""",
        "draft route revision",
    )
    save(path, text, sha, "Mobile: fail stale collection corrections closed")


def patch_api_test() -> None:
    path = "gilbic_backend/tests/test_collection_correction_api.py"
    text, sha = load(path)
    old = '            "reason": "Wrong date tapped",\n'
    text = replace_once(
        text,
        old,
        old + '            "expected_route_revision": f"loan:{LOAN_ID}:v1",\n',
        "success request revision",
    )
    old = '            "reason": "Wrong amount",\n'
    text = replace_once(
        text,
        old,
        old + '            "expected_route_revision": f"loan:{LOAN_ID}:v1",\n',
        "locked request revision",
    )
    text = replace_once(
        text,
        '    assert corrections.request["reason"] == "Wrong date tapped"\n',
        '    assert corrections.request["reason"] == "Wrong date tapped"\n'
        '    assert corrections.request["expected_route_revision"] == f"loan:{LOAN_ID}:v1"\n',
        "forwarded revision assertion",
    )
    save(path, text, sha, "Test: require correction route revision")


def patch_contract_test() -> None:
    path = "gilbic_backend/tests/test_contract_collection_posting.py"
    text, sha = load(path)
    text = replace_once(
        text,
        """            note=\"\",\n            reason=\"wrong amount\",\n        )\n""",
        """            note=\"\",\n            reason=\"wrong amount\",\n            expected_route_revision=f\"loan:{LOAN_ID}:v1\",\n        )\n""",
        "contract revision guard",
    )
    save(path, text, sha, "Test: preserve contract correction revision guard")


def main() -> None:
    patch_correction_page()
    patch_api_test()
    patch_contract_test()
    delete(WORKFLOW_PATH, "CI: remove temporary cross-correction workflow")
    delete(HELPER_PATH, "CI: remove temporary cross-correction helper")


if __name__ == "__main__":
    main()

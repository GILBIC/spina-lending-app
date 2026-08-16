from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

REPO = "GILBIC/spina-lending-app"
BRANCH = "mobile/ca4-collector-ui"
WORKFLOW_PATH = ".github/workflows/zz_tmp_flutter_test_alignment.yml"
HELPER_PATH = "tools/tmp_align_collector_flutter_tests.py"


def request_json(method: str, url: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    headers = {
        "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "spina-collector-test-alignment",
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
        if text.count(old) != 1:
            raise RuntimeError(f"{name}: expected one match, found {text.count(old)}")
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise RuntimeError(f"{name}: target not found")


def patch_app_widget_test() -> None:
    path = "gilbic_mobile/test/app_widget_test.dart"
    text, sha = load(path)
    original = text
    text = text.replace(
        "find.text('Recorded by: Collector Two')",
        "find.text('Latest receipt recorded by: Collector Two')",
    )
    text = text.replace(
        "find.text('Entry note: Paid at the route')",
        "find.text('Latest receipt note: Paid at the route')",
    )
    if "Recorded by: Collector Two" in text or "Entry note: Paid at the route" in text:
        raise RuntimeError("Legacy expanded Collector audit labels remain in app_widget_test")
    if text != original:
        save(path, text, sha, "Test: align expanded Collector audit labels")


def patch_no_auto_retry_test() -> None:
    path = "gilbic_mobile/test/collection_no_auto_retry_test.dart"
    text, sha = load(path)
    original = text
    confirm_sequence = """    await tester.tap(find.byKey(const Key('confirm-collection-entry')));\n    await tester.pumpAndSettle();\n"""
    text = text.replace(confirm_sequence, "")
    if "confirm-collection-entry" in text:
        raise RuntimeError("Collector no-auto-retry test still expects removed confirmation")
    first_submit = """    await tester.tap(find.byKey(const Key('submit-collection-entry')));\n    await tester.pumpAndSettle();\n\n    expect(repository.calls, 1);\n"""
    first_submit_with_assertion = """    await tester.tap(find.byKey(const Key('submit-collection-entry')));\n    await tester.pumpAndSettle();\n\n    expect(find.byKey(const Key('confirm-collection-entry')), findsNothing);\n    expect(repository.calls, 1);\n"""
    text = replace_once(
        text,
        first_submit,
        first_submit_with_assertion,
        "direct submit no-confirm assertion",
    )
    if text != original:
        save(path, text, sha, "Test: retry direct Collector Pay without confirmation")


def patch_route_reason_dedup() -> None:
    path = "gilbic_mobile/lib/src/features/collector/collector_route_page.dart"
    text, sha = load(path)
    original = text
    old = """        else if (!entry.processedToday)\n          Text(\n            detailsBlockedReason!,\n            style: Theme.of(context).textTheme.bodySmall,\n          ),\n"""
    new = """        else if (!entry.processedToday &&\n            detailsBlockedReason != blockedReason)\n          Text(\n            detailsBlockedReason!,\n            style: Theme.of(context).textTheme.bodySmall,\n          ),\n"""
    text = replace_once(text, old, new, "blocked reason dedupe")
    if text != original:
        save(path, text, sha, "Mobile: avoid duplicate Collector blocked guidance")


def main() -> None:
    patch_app_widget_test()
    patch_no_auto_retry_test()
    patch_route_reason_dedup()
    delete(WORKFLOW_PATH, "CI: remove temporary Collector test alignment workflow")
    delete(HELPER_PATH, "CI: remove temporary Collector test alignment helper")


if __name__ == "__main__":
    main()

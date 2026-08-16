from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

REPO = "GILBIC/spina-lending-app"
BRANCH = "mobile/ca4-collector-ui"
WORKFLOW_PATH = ".github/workflows/zz_tmp_no_collection_mobile_integration.yml"
HELPER_PATH = "tools/tmp_patch_no_collection_mobile_integration.py"


def request_json(method: str, url: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    headers = {
        "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "spina-no-collection-mobile",
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


def patch_dashboard() -> None:
    path = "gilbic_mobile/lib/src/features/dashboard/role_dashboard.dart"
    text, sha = load(path)
    text = replace_once(
        text,
        "import 'package:gilbic_mobile/src/features/management/management_loan_operations_page.dart';\n",
        "import 'package:gilbic_mobile/src/features/management/management_loan_operations_page.dart';\n"
        "import 'package:gilbic_mobile/src/features/management/management_no_collection_page.dart';\n",
        "dashboard import",
    )

    action_marker = '''    if (session.role == AppRole.management &&\n        action == 'management-loan-operations') {\n      _push(\n        context,\n        ManagementLoanOperationsPage(\n          session: session,\n          deviceIdentityProvider: deviceIdentityProvider,\n        ),\n      );\n      return;\n    }\n'''
    action_replacement = action_marker + '''    if (session.role == AppRole.management &&\n        action == 'management-no-collection') {\n      _push(\n        context,\n        ManagementNoCollectionPage(\n          session: session,\n          deviceIdentityProvider: deviceIdentityProvider,\n        ),\n      );\n      return;\n    }\n'''
    text = replace_once(text, action_marker, action_replacement, "dashboard action")

    module_marker = '''        _DashboardModule(\n          'Loan Operations',\n          'Monitor collections, remittances, corrections, and voids',\n          Icons.insights,\n          action: 'management-loan-operations',\n        ),\n'''
    module_replacement = module_marker + '''        _DashboardModule(\n          'No Collection',\n          'Move one loan schedule to the next collection dates with audit',\n          Icons.event_busy_outlined,\n          action: 'management-no-collection',\n          requiredPermissions: <String>['lending.no_collection.manage'],\n        ),\n'''
    text = replace_once(text, module_marker, module_replacement, "dashboard module")
    save(path, text, sha, "Mobile: add Management No Collection dashboard action")


def patch_contract_error_label() -> None:
    path = "gilbic_backend/src/gilbic_backend/contract_collection_posting.py"
    text, sha = load(path)
    old = "f\"Contract date {row['due_date']} is already fully paid.\""
    new = "f\"Contract date {row['effective_due_date']} is already fully paid.\""
    text = replace_once(text, old, new, "effective due-date error label")
    save(path, text, sha, "Backend: fix No Collection effective date error label")


def main() -> None:
    patch_dashboard()
    patch_contract_error_label()
    delete(WORKFLOW_PATH, "CI: remove temporary No Collection mobile workflow")
    delete(HELPER_PATH, "CI: remove temporary No Collection mobile helper")


if __name__ == "__main__":
    main()

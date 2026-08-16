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
        "User-Agent": "spina-no-collection-cleanup",
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


def collapse_duplicates(text: str, block: str) -> str:
    while block + block in text:
        text = text.replace(block + block, block)
    return text


def patch_dashboard() -> None:
    path = "gilbic_mobile/lib/src/features/dashboard/role_dashboard.dart"
    text, sha = load(path)
    original = text

    import_line = (
        "import 'package:gilbic_mobile/src/features/management/"
        "management_no_collection_page.dart';\n"
    )
    text = collapse_duplicates(text, import_line)

    action_block = '''    if (session.role == AppRole.management &&\n        action == 'management-no-collection') {\n      _push(\n        context,\n        ManagementNoCollectionPage(\n          session: session,\n          deviceIdentityProvider: deviceIdentityProvider,\n        ),\n      );\n      return;\n    }\n'''
    text = collapse_duplicates(text, action_block)

    module_block = '''        _DashboardModule(\n          'No Collection',\n          'Move one loan schedule to the next collection dates with audit',\n          Icons.event_busy_outlined,\n          action: 'management-no-collection',\n          requiredPermissions: <String>['lending.no_collection.manage'],\n        ),\n'''
    text = collapse_duplicates(text, module_block)

    if text.count(import_line) != 1:
        raise RuntimeError("Management No Collection dashboard import is not unique")
    if text.count(action_block) != 1:
        raise RuntimeError("Management No Collection dashboard action is not unique")
    if text.count(module_block) != 1:
        raise RuntimeError("Management No Collection dashboard module is not unique")

    if text != original:
        save(path, text, sha, "Mobile: dedupe Management No Collection dashboard wiring")


def patch_no_collection_page() -> None:
    path = "gilbic_mobile/lib/src/features/management/management_no_collection_page.dart"
    text, sha = load(path)
    original = text
    replacements = {
        "List<ManagementLoan> _searchResults = const <ManagementLoan>[];":
            "List<ManagementLoanItem> _searchResults = const <ManagementLoanItem>[];",
        "ManagementLoan? _selectedLoan;": "ManagementLoanItem? _selectedLoan;",
        "_searchResults = const <ManagementLoan>[];":
            "_searchResults = const <ManagementLoanItem>[];",
        ".where((loan) => loan.status.toLowerCase() == 'active')":
            ".where((loan) => loan.loanStatus.toLowerCase() == 'active')",
        "              loan.area,\n              loan.loanType,":
            "              loan.clientArea ?? '',\n              loan.loanTypeName,",
        "Future<void> _selectLoan(ManagementLoan loan) async {":
            "Future<void> _selectLoan(ManagementLoanItem loan) async {",
        "'${loan.loanNumber} • ${loan.loanType} • ${loan.area}',":
            "'${loan.loanNumber} • ${loan.loanTypeName} • ${loan.clientArea ?? ''}',",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    required = (
        "List<ManagementLoanItem> _searchResults",
        "ManagementLoanItem? _selectedLoan",
        "loan.loanStatus.toLowerCase() == 'active'",
        "Future<void> _selectLoan(ManagementLoanItem loan)",
    )
    if not all(item in text for item in required):
        raise RuntimeError("Management No Collection page is not aligned with the loan model")
    if text != original:
        save(path, text, sha, "Mobile: align No Collection screen with Management loan model")


def patch_contract_error_label() -> None:
    path = "gilbic_backend/src/gilbic_backend/contract_collection_posting.py"
    text, sha = load(path)
    original = text
    text = text.replace("row['due_date']", "row['effective_due_date']")
    if "row['due_date']" in text:
        raise RuntimeError("Contract posting still reads removed due_date field")
    if text != original:
        save(path, text, sha, "Backend: use effective date in ADV fully-covered error")


def main() -> None:
    patch_dashboard()
    patch_no_collection_page()
    patch_contract_error_label()
    delete(WORKFLOW_PATH, "CI: remove temporary No Collection integration workflow")
    delete(HELPER_PATH, "CI: remove temporary No Collection integration helper")


if __name__ == "__main__":
    main()

# Single-trigger cleanup marker.

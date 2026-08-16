from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

REPO = "GILBIC/spina-lending-app"
BRANCH = "mobile/ca4-collector-ui"
WORKFLOW_PATH = ".github/workflows/zz_tmp_no_collection_integration.yml"
HELPER_PATH = "tools/tmp_patch_no_collection_integration.py"


def request_json(method: str, url: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    headers = {
        "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "spina-no-collection-integration",
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


def patch_main() -> None:
    path = "gilbic_backend/src/gilbic_backend/main.py"
    text, sha = load(path)
    text = replace_once(
        text,
        "from .management_operations_api import create_management_operations_router\n",
        "from .management_operations_api import create_management_operations_router\n"
        "from .management_no_collection_api import create_management_no_collection_router\n",
        "main import",
    )
    text = replace_once(
        text,
        "    app.include_router(create_management_operations_router())\n",
        "    app.include_router(create_management_operations_router())\n"
        "    app.include_router(create_management_no_collection_router())\n",
        "main router",
    )
    save(path, text, sha, "Backend: register Management No Collection API")


def patch_route_repository() -> None:
    path = "gilbic_backend/src/gilbic_backend/collector_route_repository.py"
    text, sha = load(path)
    old_today = """                        from lending.loan_contract_installments installment
                        left join lateral (
                            select coalesce(sum(allocation.amount_applied) filter (
                                where transaction.is_voided = false
                            ), 0)::numeric(18,2) as allocated_amount
                            from lending.loan_installment_payment_allocations allocation
                            join lending.collection_transactions transaction
                              on transaction.id = allocation.transaction_id
                            where allocation.installment_id = installment.id
                        ) applied on true
                        where installment.schedule_id = assessment.schedule_id
                          and installment.due_date = %s
"""
    new_today = old_today.replace(
        "from lending.loan_contract_installments installment",
        "from lending.loan_contract_installments_operational installment",
    ).replace("installment.due_date = %s", "installment.effective_due_date = %s")
    text = replace_once(text, old_today, new_today, "route today effective date")

    old_next = """                            select
                                installment.id,
                                installment.due_date,
                                greatest(
                                    installment.contractual_amount
                                    - coalesce(sum(allocation.amount_applied) filter (
                                        where transaction.is_voided = false
                                    ), 0),
                                    0
                                )::numeric(18,2) as remaining_amount
                            from lending.loan_contract_installments installment
                            left join lending.loan_installment_payment_allocations allocation
                              on allocation.installment_id = installment.id
                            left join lending.collection_transactions transaction
                              on transaction.id = allocation.transaction_id
                            where installment.schedule_id = assessment.schedule_id
                            group by
                                installment.id,
                                installment.due_date,
                                installment.contractual_amount
"""
    new_next = old_next.replace(
        "installment.due_date",
        "installment.effective_due_date",
    ).replace(
        "from lending.loan_contract_installments installment",
        "from lending.loan_contract_installments_operational installment",
    )
    text = replace_once(text, old_next, new_next, "route next effective date")
    save(path, text, sha, "Backend: make Collector route honor No Collection dates")


def patch_schedule_service() -> None:
    path = "gilbic_backend/src/gilbic_backend/contract_schedule_service.py"
    text, sha = load(path)
    replacements = (
        ("join lending.loan_contract_installments installment", "join lending.loan_contract_installments_operational installment"),
        ("from lending.loan_contract_installments installment", "from lending.loan_contract_installments_operational installment"),
        ("installment.due_date", "installment.effective_due_date"),
    )
    for old, new in replacements:
        if old in text:
            text = text.replace(old, new)
    if "lending.loan_contract_installments installment" in text or "installment.due_date" in text:
        raise RuntimeError("schedule service still contains operational due_date references")
    save(path, text, sha, "Backend: allocate contract cash by effective collection dates")


def patch_contract_posting() -> None:
    path = "gilbic_backend/src/gilbic_backend/contract_collection_posting.py"
    text, sha = load(path)
    text = text.replace(
        "from lending.loan_contract_installments installment",
        "from lending.loan_contract_installments_operational installment",
    )
    text = text.replace(
        "join lending.loan_contract_installments installment",
        "join lending.loan_contract_installments_operational installment",
    )
    text = text.replace("installment.due_date", "installment.effective_due_date")
    if "lending.loan_contract_installments installment" in text or "installment.due_date" in text:
        raise RuntimeError("contract posting still contains operational due_date references")
    save(path, text, sha, "Backend: post contract collections against effective dates")


def main() -> None:
    patch_main()
    patch_route_repository()
    patch_schedule_service()
    patch_contract_posting()
    delete(WORKFLOW_PATH, "CI: remove temporary No Collection integration workflow")
    delete(HELPER_PATH, "CI: remove temporary No Collection integration helper")


if __name__ == "__main__":
    main()

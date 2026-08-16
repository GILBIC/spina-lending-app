from __future__ import annotations

import base64
import json
import os
import urllib.parse
import urllib.request

REPO = "GILBIC/spina-lending-app"
BRANCH = "mobile/ca4-collector-ui"
ROUTE_PATH = "gilbic_mobile/lib/src/features/collector/collector_route_page.dart"


def _request_json(method: str, url: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    token = os.environ["GH_TOKEN"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "spina-ca4-patch",
    }
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request) as response:
        body = response.read()
    return json.loads(body) if body else {}


def _content_meta(path: str) -> dict[str, object]:
    encoded_path = "/".join(
        urllib.parse.quote(part, safe="") for part in path.split("/")
    )
    ref = urllib.parse.quote(BRANCH, safe="")
    return _request_json(
        "GET",
        f"https://api.github.com/repos/{REPO}/contents/{encoded_path}?ref={ref}",
    )


def _replace_once(text: str, old: str, new: str, *, name: str) -> str:
    if old in text:
        count = text.count(old)
        if count != 1:
            raise RuntimeError(f"{name} target is ambiguous: {count} matches")
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise RuntimeError(f"{name} target was not found")


def main() -> None:
    meta = _content_meta(ROUTE_PATH)
    text = base64.b64decode(str(meta["content"])).decode("utf-8")

    text = _replace_once(
        text,
        "status == null || status == 429 || (status != null && status >= 500);",
        "status == null || status == 429 || status >= 500;",
        name="analyzer fix",
    )

    text = _replace_once(
        text,
        """      if (entry.processedToday && entry.todayAmount > 0)\n        'Latest receipt: ${_moneyCompact(entry.todayAmount)}',""",
        """      if (entry.todayReceipts.isEmpty &&\n          entry.processedToday &&\n          entry.todayAmount > 0)\n        'Latest receipt: ${_moneyCompact(entry.todayAmount)}',""",
        name="latest amount fallback",
    )
    text = _replace_once(
        text,
        """      if (entry.processedToday && entry.todayCollectorName.isNotEmpty)\n        'Latest receipt recorded by: ${entry.todayCollectorName}',""",
        """      if (entry.todayReceipts.isEmpty &&\n          entry.processedToday &&\n          entry.todayCollectorName.isNotEmpty)\n        'Latest receipt recorded by: ${entry.todayCollectorName}',""",
        name="latest collector fallback",
    )
    text = _replace_once(
        text,
        """      if (entry.processedToday && entry.todayIsLocked)\n        'Latest receipt remittance status: Locked',""",
        """      if (entry.todayReceipts.isEmpty &&\n          entry.processedToday &&\n          entry.todayIsLocked)\n        'Latest receipt remittance status: Locked',""",
        name="latest lock fallback",
    )
    text = _replace_once(
        text,
        """      if (entry.processedToday && entry.todayNote.isNotEmpty)\n        'Latest receipt note: ${entry.todayNote}',""",
        """      if (entry.todayReceipts.isEmpty &&\n          entry.processedToday &&\n          entry.todayNote.isNotEmpty)\n        'Latest receipt note: ${entry.todayNote}',""",
        name="latest note fallback",
    )

    text = _replace_once(
        text,
        """        for (var index = 0; index < lines.length; index++) ...[\n          if (index > 0) const SizedBox(height: 3),\n          Text(lines[index], style: Theme.of(context).textTheme.bodySmall),\n        ],\n        const SizedBox(height: 8),""",
        """        for (var index = 0; index < lines.length; index++) ...[\n          if (index > 0) const SizedBox(height: 3),\n          Text(lines[index], style: Theme.of(context).textTheme.bodySmall),\n        ],\n        if (entry.todayReceipts.isNotEmpty) ...[\n          const SizedBox(height: 8),\n          _TodayReceipts(receipts: entry.todayReceipts),\n        ],\n        const SizedBox(height: 8),""",
        name="receipt list insertion",
    )

    receipt_widget = r'''class _TodayReceipts extends StatelessWidget {
  const _TodayReceipts({required this.receipts});

  final List<CollectorRouteReceipt> receipts;

  @override
  Widget build(BuildContext context) {
    final total = receipts.fold<double>(
      0,
      (sum, receipt) => sum + receipt.amount,
    );
    return Column(
      key: const Key('today-receipts'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          "Today's receipts • ${receipts.length} • ${_moneyCompact(total)}",
          style: Theme.of(context).textTheme.labelMedium?.copyWith(
                fontWeight: FontWeight.w800,
              ),
        ),
        const SizedBox(height: 5),
        for (final receipt in receipts) ...[
          Container(
            key: Key('today-receipt-${receipt.transactionId}'),
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Receipt ${receipt.receiptNumber} • '
                  '${_moneyCompact(receipt.amount)} • '
                  '${receipt.collectorName}'
                  '${receipt.isLocked ? ' • Locked' : ''}',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                ),
                if (receipt.coveredDates.isNotEmpty)
                  Text(
                    'Covered: ${receipt.coveredDates.map(_date).join(', ')}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                if (receipt.note.isNotEmpty)
                  Text(
                    'Note: ${receipt.note}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

String _shortLoanName(String value) {'''
    text = _replace_once(
        text,
        "String _shortLoanName(String value) {",
        receipt_widget,
        name="receipt widget insertion",
    )

    payload = {
        "message": "Mobile: show every same-day Collector receipt",
        "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
        "sha": meta["sha"],
        "branch": BRANCH,
    }
    encoded_route = "/".join(
        urllib.parse.quote(part, safe="") for part in ROUTE_PATH.split("/")
    )
    result = _request_json(
        "PUT",
        f"https://api.github.com/repos/{REPO}/contents/{encoded_route}",
        payload,
    )
    commit = result.get("commit")
    if isinstance(commit, dict):
        print(f"updated route UI at {commit.get('sha', '')}")


if __name__ == "__main__":
    main()

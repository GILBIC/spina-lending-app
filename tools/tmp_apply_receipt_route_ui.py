from __future__ import annotations

from pathlib import Path


ROUTE_REPO = Path('gilbic_backend/src/gilbic_backend/collector_route_repository.py')
ROUTE_API = Path('gilbic_backend/src/gilbic_backend/collector_route_api.py')
ROUTE_PAGE = Path('gilbic_mobile/lib/src/features/collector/collector_route_page.dart')
ROUTE_MODEL = Path('gilbic_mobile/lib/src/core/collector/collector_route.dart')
BACKEND_TEST = Path('gilbic_backend/tests/test_collector_route_receipt_application.py')
MOBILE_TEST = Path('gilbic_mobile/test/collector_route_receipt_application_test.dart')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old in text:
        if text.count(old) != 1:
            raise RuntimeError(f'{label}: expected exactly one match, got {text.count(old)}')
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise RuntimeError(f'{label}: target not found')


def patch_backend_route_repository() -> None:
    text = ROUTE_REPO.read_text(encoding='utf-8')
    text = replace_once(
        text,
        '''    is_locked: bool\n    note: str = ""\n''',
        '''    is_locked: bool\n    applied_amount: Decimal | None = None\n    unallocated_amount: Decimal = Decimal("0.00")\n    allocation_state: str = "fully_allocated"\n    note: str = ""\n''',
        'receipt dataclass application fields',
    )
    text = replace_once(
        text,
        '''        receipts.append(\n            CollectorRouteReceiptRecord(\n                transaction_id=UUID(str(transaction_id)),\n                receipt_number=receipt_number,\n                amount=Decimal(str(raw.get("amount") or 0)).quantize(MONEY),\n                entry_type=str(raw.get("entry_type") or "payment"),\n                collector_user_id=UUID(str(collector_user_id)),\n                collector_name=str(raw.get("collector_name") or "Collector"),\n                is_locked=bool(raw.get("is_locked")),\n                note=str(raw.get("note") or ""),\n''',
        '''        amount = Decimal(str(raw.get("amount") or 0)).quantize(MONEY)\n        raw_applied = raw.get("applied_amount")\n        applied_amount = (\n            amount\n            if raw_applied is None\n            else Decimal(str(raw_applied)).quantize(MONEY)\n        )\n        receipts.append(\n            CollectorRouteReceiptRecord(\n                transaction_id=UUID(str(transaction_id)),\n                receipt_number=receipt_number,\n                amount=amount,\n                entry_type=str(raw.get("entry_type") or "payment"),\n                collector_user_id=UUID(str(collector_user_id)),\n                collector_name=str(raw.get("collector_name") or "Collector"),\n                is_locked=bool(raw.get("is_locked")),\n                applied_amount=applied_amount,\n                unallocated_amount=Decimal(\n                    str(raw.get("unallocated_amount") or 0)\n                ).quantize(MONEY),\n                allocation_state=str(\n                    raw.get("allocation_state") or "fully_allocated"\n                ),\n                note=str(raw.get("note") or ""),\n''',
        'receipt parser application fields',
    )
    text = replace_once(
        text,
        '''                                        'amount', receipt.amount,\n                                        'entry_type', receipt.entry_type,\n''',
        '''                                        'amount', receipt.amount,\n                                        'applied_amount', receipt.applied_amount,\n                                        'unallocated_amount', receipt.unallocated_amount,\n                                        'allocation_state', receipt.allocation_state,\n                                        'entry_type', receipt.entry_type,\n''',
        'receipt JSON application fields',
    )
    ROUTE_REPO.write_text(text, encoding='utf-8')


def patch_backend_route_api() -> None:
    text = ROUTE_API.read_text(encoding='utf-8')
    text = replace_once(
        text,
        '''        "amount": str(receipt.amount),\n        "entry_type": receipt.entry_type,\n''',
        '''        "amount": str(receipt.amount),\n        "applied_amount": str(\n            receipt.amount\n            if receipt.applied_amount is None\n            else receipt.applied_amount\n        ),\n        "unallocated_amount": str(receipt.unallocated_amount),\n        "allocation_state": receipt.allocation_state,\n        "entry_type": receipt.entry_type,\n''',
        'receipt API application fields',
    )
    ROUTE_API.write_text(text, encoding='utf-8')


def patch_mobile_route_model() -> None:
    text = ROUTE_MODEL.read_text(encoding='utf-8')
    text = replace_once(
        text,
        '''    required this.isLocked,\n    this.note = '',\n''',
        '''    required this.isLocked,\n    this.appliedAmount,\n    this.unallocatedAmount = 0,\n    this.allocationState = 'fully_allocated',\n    this.note = '',\n''',
        'receipt constructor application fields',
    )
    text = replace_once(
        text,
        '''  final bool isLocked;\n  final String note;\n''',
        '''  final bool isLocked;\n  final double? appliedAmount;\n  final double unallocatedAmount;\n  final String allocationState;\n  final String note;\n\n  double get applied => appliedAmount ?? amount;\n\n  bool get needsReview =>\n      unallocatedAmount > 0.005 ||\n      allocationState == 'unallocated' ||\n      allocationState == 'partially_allocated';\n''',
        'receipt model application fields',
    )
    text = replace_once(
        text,
        '''      'amount': amount,\n      'entry_type': entryType,\n''',
        '''      'amount': amount,\n      'applied_amount': applied,\n      'unallocated_amount': unallocatedAmount,\n      'allocation_state': allocationState,\n      'entry_type': entryType,\n''',
        'receipt toJson application fields',
    )
    text = replace_once(
        text,
        '''      amount: firstNumber(<Object?>[data['amount']])?.toDouble() ?? 0,\n      entryType: firstNonEmptyString(<Object?>[data['entry_type']]) ?? 'payment',\n''',
        '''      amount: firstNumber(<Object?>[data['amount']])?.toDouble() ?? 0,\n      appliedAmount: firstNumber(<Object?>[data['applied_amount']])?.toDouble(),\n      unallocatedAmount:\n          firstNumber(<Object?>[data['unallocated_amount']])?.toDouble() ?? 0,\n      allocationState: firstNonEmptyString(<Object?>[\n            data['allocation_state'],\n          ]) ??\n          'fully_allocated',\n      entryType: firstNonEmptyString(<Object?>[data['entry_type']]) ?? 'payment',\n''',
        'receipt payload application fields',
    )
    text = replace_once(
        text,
        '''  final List<DateTime> todayCoveredDates;\n  final List<CollectorRouteReceipt> todayReceipts;\n\n  Map<String, Object?> toJson() {\n''',
        '''  final List<DateTime> todayCoveredDates;\n  final List<CollectorRouteReceipt> todayReceipts;\n\n  double get todayCashTotal {\n    if (todayReceipts.isNotEmpty) {\n      return todayReceipts.fold<double>(\n        0,\n        (total, receipt) => total + receipt.amount,\n      );\n    }\n    return processedToday ? todayAmount : 0;\n  }\n\n  double get todayAppliedTotal {\n    if (todayReceipts.isNotEmpty) {\n      return todayReceipts.fold<double>(\n        0,\n        (total, receipt) => total + receipt.applied,\n      );\n    }\n    final type = todayEntryType.trim().toLowerCase();\n    if (processedToday && (type == 'payment' || type == 'advance')) {\n      return todayAmount;\n    }\n    return 0;\n  }\n\n  double get todayUnallocatedTotal => todayReceipts.fold<double>(\n        0,\n        (total, receipt) => total + receipt.unallocatedAmount,\n      );\n\n  double get scheduledRemainingToday {\n    if (contractCollectionReady) {\n      if (contractTodayScheduledAmount <= 0) {\n        return 0;\n      }\n      return contractTodayUnpaidAmount > 0 ? contractTodayUnpaidAmount : 0;\n    }\n    final remaining = dailyAmount - todayAppliedTotal;\n    return remaining > 0 ? remaining : 0;\n  }\n\n  bool get hasReceiptApplicationReview => todayUnallocatedTotal > 0.005;\n\n  Map<String, Object?> toJson() {\n''',
        'entry receipt aggregate getters',
    )
    ROUTE_MODEL.write_text(text, encoding='utf-8')


def patch_route_page() -> None:
    text = ROUTE_PAGE.read_text(encoding='utf-8')
    text = replace_once(
        text,
        '''    if (entry.processedToday) {\n      return "Today's collection has already been recorded.";\n    }\n    return null;\n  }\n\n  String? _detailsBlockedReason(\n''',
        '''    if (entry.scheduledRemainingToday <= 0) {\n      return "Today's scheduled amount is already satisfied. Expand this loan only for another real receipt, Voluntary extra, ADV, notes, or correction details.";\n    }\n    return null;\n  }\n\n  String? _detailsBlockedReason(\n''',
        'non-contract partial direct Pay',
    )
    text = replace_once(
        text,
        '''    final canAddPartialContractReceipt = entry.contractCollectionReady &&\n        entry.contractTodayUnpaidAmount > 0;\n    if (entry.processedToday && !canAddPartialContractReceipt) {\n      return "Today's scheduled payment is already recorded. Use Edit for a correction before remittance.";\n    }\n    return null;\n  }\n\n  double _normalDueAmount(CollectorRouteEntry entry) {\n    if (entry.contractCollectionReady &&\n        entry.contractTodayUnpaidAmount > 0) {\n      return entry.contractTodayUnpaidAmount;\n    }\n    return entry.dailyAmount;\n  }\n''',
        '''    // A second genuine physical receipt is still recordable from the\n    // expanded details flow. The server preserves cash that cannot be applied as\n    // Unallocated / Needs review instead of silently creating ADV.\n    return null;\n  }\n\n  double _normalDueAmount(CollectorRouteEntry entry) {\n    if (entry.contractCollectionReady &&\n        entry.contractTodayUnpaidAmount > 0) {\n      return entry.contractTodayUnpaidAmount;\n    }\n    return entry.scheduledRemainingToday;\n  }\n''',
        'details and direct amount receipt-first semantics',
    )

    receipt_start = text.index('class _TodayReceipts extends StatelessWidget {')
    receipt_end = text.index('String _shortLoanName(String value) {', receipt_start)
    receipt_widget = '''class _TodayReceipts extends StatelessWidget {\n  const _TodayReceipts({required this.receipts});\n\n  final List<CollectorRouteReceipt> receipts;\n\n  @override\n  Widget build(BuildContext context) {\n    final cashTotal = receipts.fold<double>(\n      0,\n      (sum, receipt) => sum + receipt.amount,\n    );\n    final appliedTotal = receipts.fold<double>(\n      0,\n      (sum, receipt) => sum + receipt.applied,\n    );\n    final unallocatedTotal = receipts.fold<double>(\n      0,\n      (sum, receipt) => sum + receipt.unallocatedAmount,\n    );\n    return Column(\n      key: const Key('today-receipts'),\n      crossAxisAlignment: CrossAxisAlignment.start,\n      children: [\n        Text(\n          unallocatedTotal > 0.005\n              ? "Today's receipts • ${receipts.length} • Cash ${_moneyCompact(cashTotal)} • Applied ${_moneyCompact(appliedTotal)} • Unallocated ${_moneyCompact(unallocatedTotal)} • NEEDS REVIEW"\n              : "Today's receipts • ${receipts.length} • ${_moneyCompact(cashTotal)}",\n          style: Theme.of(context).textTheme.labelMedium?.copyWith(\n                fontWeight: FontWeight.w800,\n              ),\n        ),\n        const SizedBox(height: 5),\n        for (final receipt in receipts) ...[\n          Container(\n            key: Key('today-receipt-${receipt.transactionId}'),\n            width: double.infinity,\n            padding: const EdgeInsets.symmetric(vertical: 4),\n            child: Column(\n              crossAxisAlignment: CrossAxisAlignment.start,\n              children: [\n                Text(\n                  'Receipt ${receipt.receiptNumber} • Cash ${_moneyCompact(receipt.amount)} • ${receipt.collectorName}'\n                  '${receipt.isLocked ? ' • Locked' : ''}',\n                  style: Theme.of(context).textTheme.bodySmall?.copyWith(\n                        fontWeight: FontWeight.w700,\n                      ),\n                ),\n                if ((receipt.applied - receipt.amount).abs() > 0.005 ||\n                    receipt.needsReview)\n                  Text(\n                    receipt.unallocatedAmount > 0.005\n                        ? 'Applied ${_moneyCompact(receipt.applied)} • Unallocated ${_moneyCompact(receipt.unallocatedAmount)} • NEEDS REVIEW'\n                        : 'Applied ${_moneyCompact(receipt.applied)}',\n                    style: Theme.of(context).textTheme.labelSmall?.copyWith(\n                          fontWeight: FontWeight.w800,\n                          color: receipt.needsReview\n                              ? Theme.of(context).colorScheme.error\n                              : null,\n                        ),\n                  ),\n                if (receipt.coveredDates.isNotEmpty)\n                  Text(\n                    'Covered: ${receipt.coveredDates.map(_date).join(', ')}',\n                    style: Theme.of(context).textTheme.bodySmall,\n                  ),\n                if (receipt.note.isNotEmpty)\n                  Text(\n                    'Note: ${receipt.note}',\n                    style: Theme.of(context).textTheme.bodySmall,\n                  ),\n              ],\n            ),\n          ),\n        ],\n      ],\n    );\n  }\n}\n\n'''
    text = text[:receipt_start] + receipt_widget + text[receipt_end:]

    short_start = text.index('String _shortStatus(CollectorRouteEntry entry) {')
    short_end = text.index('String _actionLabel(', short_start)
    short_status = '''String _shortStatus(CollectorRouteEntry entry) {\n  final hasMoneyToday = entry.todayCashTotal > 0.005;\n  if (hasMoneyToday && entry.scheduledRemainingToday > 0.005) {\n    return 'Lacking';\n  }\n  if (entry.todayUnallocatedTotal > 0.005) {\n    return 'Review';\n  }\n  if (entry.contractCollectionReady &&\n      entry.contractTodayScheduledAmount > 0) {\n    if (entry.contractTodayUnpaidAmount > 0) {\n      return entry.processedToday ? 'Lacking' : 'Pending';\n    }\n    return entry.processedToday ? 'Paid' : 'Covered';\n  }\n  if (entry.processedToday) {\n    if (entry.todayIsLocked) {\n      return 'Remitted';\n    }\n    return switch (entry.todayEntryType.trim().toLowerCase()) {\n      'pass' => 'Unable',\n      'advance' => 'Covered',\n      _ => 'Paid',\n    };\n  }\n  if (_isSevenBySevenLoan(entry.loanType) &&\n      !entry.sevenBySevenMobileEnabled) {\n    return 'Desktop';\n  }\n  return entry.status;\n}\n\n'''
    text = text[:short_start] + short_status + text[short_end:]
    ROUTE_PAGE.write_text(text, encoding='utf-8')


def write_backend_test() -> None:
    BACKEND_TEST.write_text(
        '''from __future__ import annotations\n\nfrom datetime import datetime, timezone\nfrom decimal import Decimal\nfrom uuid import UUID\n\nfrom gilbic_backend.collector_route_api import _receipt_payload\nfrom gilbic_backend.collector_route_repository import (\n    CollectorRouteReceiptRecord,\n    _receipt_records,\n)\n\n\ndef test_route_receipt_preserves_cash_application_and_unallocated_review_state() -> None:\n    transaction_id = UUID("11111111-1111-4111-8111-111111111111")\n    collector_id = UUID("22222222-2222-4222-8222-222222222222")\n    rows = _receipt_records(\n        [\n            {\n                "transaction_id": str(transaction_id),\n                "receipt_number": "GBC-20260816-00000001",\n                "amount": "200.00",\n                "applied_amount": "100.00",\n                "unallocated_amount": "100.00",\n                "allocation_state": "partially_allocated",\n                "entry_type": "payment",\n                "collector_user_id": str(collector_id),\n                "collector_name": "Collector One",\n                "is_locked": False,\n                "accepted_at": "2026-08-16T04:00:00+00:00",\n            }\n        ]\n    )\n\n    assert len(rows) == 1\n    receipt = rows[0]\n    assert receipt.amount == Decimal("200.00")\n    assert receipt.applied_amount == Decimal("100.00")\n    assert receipt.unallocated_amount == Decimal("100.00")\n    assert receipt.allocation_state == "partially_allocated"\n\n    payload = _receipt_payload(receipt)\n    assert payload["amount"] == "200.00"\n    assert payload["applied_amount"] == "100.00"\n    assert payload["unallocated_amount"] == "100.00"\n    assert payload["allocation_state"] == "partially_allocated"\n\n\ndef test_old_receipt_payload_falls_back_to_cash_as_applied() -> None:\n    transaction_id = UUID("33333333-3333-4333-8333-333333333333")\n    collector_id = UUID("44444444-4444-4444-8444-444444444444")\n    receipt = CollectorRouteReceiptRecord(\n        transaction_id=transaction_id,\n        receipt_number="GBC-OLD",\n        amount=Decimal("90.00"),\n        entry_type="payment",\n        collector_user_id=collector_id,\n        collector_name="Collector One",\n        is_locked=False,\n        accepted_at=datetime(2026, 8, 16, 4, 0, tzinfo=timezone.utc),\n    )\n\n    payload = _receipt_payload(receipt)\n    assert payload["applied_amount"] == "90.00"\n    assert payload["unallocated_amount"] == "0.00"\n''',
        encoding='utf-8',
    )


def write_mobile_test() -> None:
    MOBILE_TEST.write_text(
        '''import 'package:flutter_test/flutter_test.dart';\nimport 'package:gilbic_mobile/src/core/collector/collector_route.dart';\n\nMap<String, Object?> baseEntry({\n  required double dailyAmount,\n  required List<Map<String, Object?>> receipts,\n}) {\n  return <String, Object?>{\n    'route_entry_id': 'loan-1',\n    'client_id': 'client-1',\n    'loan_id': 'loan-1',\n    'client_name': 'Ana Client',\n    'area': 'Cardona',\n    'loan_type': 'Regular',\n    'daily_amount': dailyAmount,\n    'remaining_balance': 5000,\n    'status': 'Recorded today',\n    'pass_count': 0,\n    'processed_today': true,\n    'today_entry_type': 'payment',\n    'today_amount': receipts.isEmpty ? 0 : receipts.last['amount'],\n    'today_receipts': receipts,\n  };\n}\n\nMap<String, Object?> receipt({\n  required String id,\n  required double cash,\n  required double applied,\n  required double unallocated,\n}) {\n  return <String, Object?>{\n    'transaction_id': id,\n    'receipt_number': 'GBC-$id',\n    'amount': cash,\n    'applied_amount': applied,\n    'unallocated_amount': unallocated,\n    'allocation_state': unallocated <= 0\n        ? 'fully_allocated'\n        : applied <= 0\n            ? 'unallocated'\n            : 'partially_allocated',\n    'entry_type': 'payment',\n    'collector_user_id': 'collector-1',\n    'collector_name': 'Collector One',\n    'is_locked': false,\n  };\n}\n\nvoid main() {\n  test('two partial receipts leave only the actual lacking amount', () {\n    final entry = CollectorRouteEntry.fromPayload(\n      baseEntry(\n        dailyAmount: 200,\n        receipts: <Map<String, Object?>>[\n          receipt(id: 'one', cash: 100, applied: 100, unallocated: 0),\n          receipt(id: 'two', cash: 50, applied: 50, unallocated: 0),\n        ],\n      ),\n    )!;\n\n    expect(entry.todayCashTotal, 150);\n    expect(entry.todayAppliedTotal, 150);\n    expect(entry.todayUnallocatedTotal, 0);\n    expect(entry.scheduledRemainingToday, 50);\n    expect(entry.hasReceiptApplicationReview, isFalse);\n  });\n\n  test('second receipt after obligation is paid remains cash and unallocated', () {\n    final entry = CollectorRouteEntry.fromPayload(\n      baseEntry(\n        dailyAmount: 100,\n        receipts: <Map<String, Object?>>[\n          receipt(id: 'one', cash: 100, applied: 100, unallocated: 0),\n          receipt(id: 'two', cash: 100, applied: 0, unallocated: 100),\n        ],\n      ),\n    )!;\n\n    expect(entry.todayCashTotal, 200);\n    expect(entry.todayAppliedTotal, 100);\n    expect(entry.todayUnallocatedTotal, 100);\n    expect(entry.scheduledRemainingToday, 0);\n    expect(entry.hasReceiptApplicationReview, isTrue);\n    expect(entry.todayReceipts.last.needsReview, isTrue);\n  });\n\n  test('legacy receipt without application fields falls back to fully applied cash', () {\n    final entry = CollectorRouteEntry.fromPayload(\n      baseEntry(\n        dailyAmount: 100,\n        receipts: <Map<String, Object?>>[\n          <String, Object?>{\n            'transaction_id': 'legacy',\n            'receipt_number': 'GBC-LEGACY',\n            'amount': 100,\n            'entry_type': 'payment',\n            'collector_user_id': 'collector-1',\n            'collector_name': 'Collector One',\n            'is_locked': false,\n          },\n        ],\n      ),\n    )!;\n\n    expect(entry.todayAppliedTotal, 100);\n    expect(entry.scheduledRemainingToday, 0);\n  });\n}\n''',
        encoding='utf-8',
    )


def main() -> None:
    patch_backend_route_repository()
    patch_backend_route_api()
    patch_mobile_route_model()
    patch_route_page()
    write_backend_test()
    write_mobile_test()


if __name__ == '__main__':
    main()

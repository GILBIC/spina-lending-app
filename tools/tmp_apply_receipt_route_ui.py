from __future__ import annotations

from pathlib import Path
import runpy


ROOT = Path('.')
OLD_HELPER = Path('tools/tmp_apply_synthetic_route_ui.py')
ROUTE_REPO = Path('gilbic_backend/src/gilbic_backend/collector_route_repository.py')
ROUTE_API = Path('gilbic_backend/src/gilbic_backend/collector_route_api.py')
ROUTE_PAGE = Path('gilbic_mobile/lib/src/features/collector/collector_route_page.dart')
ROUTE_MODEL = Path('gilbic_mobile/lib/src/core/collector/collector_route.dart')
LEDGER = Path('gilbic_mobile/lib/src/features/collector/collector_client_ledger.dart')
BACKEND_TEST = Path('gilbic_backend/tests/test_collector_route_receipt_application.py')
MOBILE_TEST = Path('gilbic_mobile/test/collector_route_receipt_application_test.dart')
SELF = Path('tools/tmp_apply_receipt_route_ui.py')
WORKFLOW = Path('.github/workflows/zz_tmp_apply_receipt_route_ui_cloud.yml')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old in text:
        if text.count(old) != 1:
            raise RuntimeError(f'{label}: expected exactly one match, got {text.count(old)}')
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise RuntimeError(f'{label}: target not found')


def integrate_compact_route_ui() -> None:
    # Reuse the already-reviewed deterministic integration helper if it is still
    # present. It also removes its own stale self-hosted workflow/helper files.
    if OLD_HELPER.exists():
        runpy.run_path(str(OLD_HELPER), run_name='__main__')


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
    old_direct_tail = '''    if (entry.processedToday) {\n      return "Today's collection has already been recorded.";\n    }\n    return null;\n  }\n\n  String? _detailsBlockedReason(\n'''
    new_direct_tail = '''    if (entry.scheduledRemainingToday <= 0) {\n      return "Today's scheduled amount is already satisfied. Expand this loan only for another real receipt, Voluntary extra, ADV, notes, or correction details.";\n    }\n    return null;\n  }\n\n  String? _detailsBlockedReason(\n'''
    text = replace_once(text, old_direct_tail, new_direct_tail, 'non-contract partial direct Pay')
    text = replace_once(
        text,
        '''    final canAddPartialContractReceipt = entry.contractCollectionReady &&\n        entry.contractTodayUnpaidAmount > 0;\n    if (entry.processedToday && !canAddPartialContractReceipt) {\n      return "Today's scheduled payment is already recorded. Use Edit for a correction before remittance.";\n    }\n    return null;\n  }\n\n  double _normalDueAmount(CollectorRouteEntry entry) {\n    if (entry.contractCollectionReady &&\n        entry.contractTodayUnpaidAmount > 0) {\n      return entry.contractTodayUnpaidAmount;\n    }\n    return entry.dailyAmount;\n  }\n''',
        '''    // Details remain available after a scheduled amount is satisfied so a\n    // genuinely separate physical receipt can still be recorded. The server\n    // preserves any amount that cannot be applied as Unallocated / Needs review.\n    return null;\n  }\n\n  double _normalDueAmount(CollectorRouteEntry entry) {\n    if (entry.contractCollectionReady &&\n        entry.contractTodayUnpaidAmount > 0) {\n      return entry.contractTodayUnpaidAmount;\n    }\n    return entry.scheduledRemainingToday;\n  }\n''',
        'details and direct amount receipt-first semantics',
    )
    ROUTE_PAGE.write_text(text, encoding='utf-8')


def patch_compact_ledger() -> None:
    text = LEDGER.read_text(encoding='utf-8')
    text = replace_once(
        text,
        '''                  detailsBuilder(client.loans[index]),\n''',
        '''                  detailsBuilder(client.loans[index]),\n                  if (client.loans[index].todayReceipts.isNotEmpty) ...[\n                    const SizedBox(height: 9),\n                    _TodayReceiptSummary(entry: client.loans[index]),\n                  ],\n''',
        'expanded receipt summary',
    )
    marker = '''class _CombinedPayNotice extends StatelessWidget {\n'''
    receipt_widget = '''class _TodayReceiptSummary extends StatelessWidget {\n  const _TodayReceiptSummary({required this.entry});\n\n  final CollectorRouteEntry entry;\n\n  @override\n  Widget build(BuildContext context) {\n    final unallocated = entry.todayUnallocatedTotal;\n    final status = entry.scheduledRemainingToday > 0.005\n        ? 'Lacking ${_moneyShort(entry.scheduledRemainingToday)}'\n        : 'Paid';\n    return Container(\n      width: double.infinity,\n      padding: const EdgeInsets.all(9),\n      decoration: BoxDecoration(\n        color: Colors.white,\n        borderRadius: BorderRadius.circular(10),\n        border: Border.all(color: SpinaTheme.line),\n      ),\n      child: Column(\n        crossAxisAlignment: CrossAxisAlignment.start,\n        children: [\n          Text(\n            unallocated > 0.005\n                ? '$status • Unallocated ${_moneyShort(unallocated)} • Needs review'\n                : status,\n            style: Theme.of(context).textTheme.labelMedium?.copyWith(\n                  fontWeight: FontWeight.w900,\n                ),\n          ),\n          const SizedBox(height: 5),\n          for (final receipt in entry.todayReceipts) ...[\n            Text(\n              '${receipt.receiptNumber} • Cash ${_moneyShort(receipt.amount)} • ${receipt.collectorName}',\n              style: Theme.of(context).textTheme.bodySmall?.copyWith(\n                    fontWeight: FontWeight.w700,\n                  ),\n            ),\n            if ((receipt.applied - receipt.amount).abs() > 0.005 ||\n                receipt.needsReview)\n              Padding(\n                padding: const EdgeInsets.only(top: 2, bottom: 3),\n                child: Text(\n                  receipt.unallocatedAmount > 0.005\n                      ? 'Applied ${_moneyShort(receipt.applied)} • Unallocated ${_moneyShort(receipt.unallocatedAmount)} • NEEDS REVIEW'\n                      : 'Applied ${_moneyShort(receipt.applied)}',\n                  style: Theme.of(context).textTheme.labelSmall?.copyWith(\n                        color: receipt.needsReview\n                            ? SpinaTheme.brandPinkDark\n                            : null,\n                        fontWeight: FontWeight.w800,\n                      ),\n                ),\n              ),\n          ],\n        ],\n      ),\n    );\n  }\n}\n\n'''
    if receipt_widget not in text:
        if marker not in text:
            raise RuntimeError('receipt widget insertion marker not found')
        text = text.replace(marker, receipt_widget + marker, 1)

    old_blocked = '''  if (entry.processedToday) {\n    if (entry.contractCollectionReady && entry.contractTodayUnpaidAmount > 0) {\n      return 'Lacking';\n    }\n    return 'Paid';\n  }\n'''
    new_blocked = '''  if (entry.processedToday || entry.todayReceipts.isNotEmpty) {\n    if (entry.scheduledRemainingToday > 0.005) {\n      return 'Lacking';\n    }\n    if (entry.todayUnallocatedTotal > 0.005) {\n      return 'Review';\n    }\n    return 'Paid';\n  }\n'''
    text = replace_once(text, old_blocked, new_blocked, 'blocked receipt status label')

    start = text.index('List<String> _statusChips(CollectorRouteClientGroup client) {')
    end = text.index('bool _todaySatisfied(CollectorRouteEntry entry) {', start)
    new_status = '''List<String> _statusChips(CollectorRouteClientGroup client) {\n  final chips = <String>[];\n  final loans = client.loans;\n  final hasPass = loans.any(\n    (entry) => entry.todayEntryType.trim().toLowerCase() == 'pass',\n  );\n  final hasReceiptActivity = loans.any(\n    (entry) =>\n        entry.todayReceipts.isNotEmpty ||\n        entry.todayCashTotal > 0.005 ||\n        entry.processedToday,\n  );\n  final hasLacking = loans.any(\n    (entry) =>\n        entry.scheduledRemainingToday > 0.005 &&\n        (entry.todayCashTotal > 0.005 ||\n            (entry.processedToday &&\n                entry.todayEntryType.trim().toLowerCase() != 'pass')),\n  );\n  final unallocated = loans.fold<double>(\n    0,\n    (total, entry) => total + entry.todayUnallocatedTotal,\n  );\n  final hasAdvance = loans.any(\n    (entry) => entry.todayEntryType.trim().toLowerCase() == 'advance' ||\n        entry.advanceUntil != null,\n  );\n  final allComplete =\n      hasReceiptActivity && loans.isNotEmpty && loans.every(_todaySatisfied);\n  final anyLocked = loans.any((entry) => entry.todayIsLocked);\n  final desktop7x7 = loans.any(\n    (entry) => _isSevenBySeven(entry.loanType) && !entry.sevenBySevenMobileEnabled,\n  );\n  final missed = loans.fold<int>(\n    0,\n    (highest, entry) => entry.passCount > highest ? entry.passCount : highest,\n  );\n  final textBlob = loans\n      .expand((entry) => <String>[entry.status, entry.note, entry.todayNote])\n      .join(' ')\n      .toLowerCase();\n\n  if (hasLacking) {\n    chips.add('LACKING');\n  } else if (allComplete) {\n    chips.add(anyLocked ? 'REMITTED' : 'COLLECTED');\n  } else if (hasPass) {\n    chips.add('UNABLE');\n  } else if (hasReceiptActivity) {\n    chips.add('PARTIAL');\n  } else {\n    chips.add('NOT COLLECTED');\n  }\n\n  if (unallocated > 0.005) {\n    chips.add('UNALLOCATED ${_moneyShort(unallocated)}');\n    chips.add('NEEDS REVIEW');\n  }\n  if (missed > 0) {\n    if (!allComplete && !hasPass) {\n      chips.add('CATCH-UP');\n    }\n    chips.add('MISSED $missed');\n  }\n  if (hasAdvance) {\n    chips.add('ADV');\n  }\n  if (textBlob.contains('gcash')) {\n    chips.add('GCASH');\n  }\n  if (desktop7x7) {\n    chips.add('7x7 DESK');\n  }\n  return chips;\n}\n\n'''
    text = text[:start] + new_status + text[end:]
    text = replace_once(
        text,
        '''bool _todaySatisfied(CollectorRouteEntry entry) {\n  if (entry.contractCollectionReady && entry.contractTodayScheduledAmount > 0) {\n    return entry.contractTodayUnpaidAmount <= 0;\n  }\n  return entry.processedToday;\n}\n''',
        '''bool _todaySatisfied(CollectorRouteEntry entry) {\n  return entry.scheduledRemainingToday <= 0.005;\n}\n''',
        'today satisfied receipt application',
    )
    text = replace_once(
        text,
        '''double _unpaidToday(CollectorRouteEntry entry) {\n  if (entry.contractCollectionReady && entry.contractTodayScheduledAmount > 0) {\n    return entry.contractTodayUnpaidAmount > 0\n        ? entry.contractTodayUnpaidAmount\n        : 0;\n  }\n  return entry.processedToday ? 0 : entry.dailyAmount;\n}\n''',
        '''double _unpaidToday(CollectorRouteEntry entry) {\n  return entry.scheduledRemainingToday;\n}\n''',
        'today unpaid receipt application',
    )
    LEDGER.write_text(text, encoding='utf-8')


def write_backend_test() -> None:
    BACKEND_TEST.write_text(
        '''from __future__ import annotations\n\nfrom datetime import datetime, timezone\nfrom decimal import Decimal\nfrom uuid import UUID\n\nfrom gilbic_backend.collector_route_api import _receipt_payload\nfrom gilbic_backend.collector_route_repository import (\n    CollectorRouteReceiptRecord,\n    _receipt_records,\n)\n\n\ndef test_route_receipt_preserves_cash_application_and_unallocated_review_state() -> None:\n    transaction_id = UUID("11111111-1111-4111-8111-111111111111")\n    collector_id = UUID("22222222-2222-4222-8222-222222222222")\n    rows = _receipt_records(\n        [\n            {\n                "transaction_id": str(transaction_id),\n                "receipt_number": "GBC-20260816-00000001",\n                "amount": "200.00",\n                "applied_amount": "100.00",\n                "unallocated_amount": "100.00",\n                "allocation_state": "partially_allocated",\n                "entry_type": "payment",\n                "collector_user_id": str(collector_id),\n                "collector_name": "Collector One",\n                "is_locked": False,\n                "accepted_at": "2026-08-16T04:00:00+00:00",\n            }\n        ]\n    )\n\n    assert len(rows) == 1\n    receipt = rows[0]\n    assert receipt.amount == Decimal("200.00")\n    assert receipt.applied_amount == Decimal("100.00")\n    assert receipt.unallocated_amount == Decimal("100.00")\n    assert receipt.allocation_state == "partially_allocated"\n\n    payload = _receipt_payload(receipt)\n    assert payload["amount"] == "200.00"\n    assert payload["applied_amount"] == "100.00"\n    assert payload["unallocated_amount"] == "100.00"\n    assert payload["allocation_state"] == "partially_allocated"\n\n\ndef test_old_receipt_payload_falls_back_to_cash_as_applied() -> None:\n    transaction_id = UUID("33333333-3333-4333-8333-333333333333")\n    collector_id = UUID("44444444-4444-4444-8444-444444444444")\n    receipt = CollectorRouteReceiptRecord(\n        transaction_id=transaction_id,\n        receipt_number="GBC-OLD",\n        amount=Decimal("90.00"),\n        entry_type="payment",\n        collector_user_id=collector_id,\n        collector_name="Collector One",\n        is_locked=False,\n        accepted_at=datetime(2026, 8, 16, 4, 0, tzinfo=timezone.utc),\n    )\n\n    payload = _receipt_payload(receipt)\n    assert payload["applied_amount"] == "90.00"\n    assert payload["unallocated_amount"] == "0.00"\n''',
        encoding='utf-8',
    )


def write_mobile_test() -> None:
    MOBILE_TEST.write_text(
        '''import 'package:flutter_test/flutter_test.dart';\nimport 'package:gilbic_mobile/src/core/collector/collector_route.dart';\n\nMap<String, Object?> baseEntry({\n  required double dailyAmount,\n  required List<Map<String, Object?>> receipts,\n  bool processedToday = true,\n}) {\n  return <String, Object?>{\n    'route_entry_id': 'loan-1',\n    'client_id': 'client-1',\n    'loan_id': 'loan-1',\n    'client_name': 'Ana Client',\n    'area': 'Cardona',\n    'loan_type': 'Regular',\n    'daily_amount': dailyAmount,\n    'remaining_balance': 5000,\n    'status': 'Recorded today',\n    'pass_count': 0,\n    'processed_today': processedToday,\n    'today_entry_type': 'payment',\n    'today_amount': receipts.isEmpty ? 0 : receipts.last['amount'],\n    'today_receipts': receipts,\n  };\n}\n\nMap<String, Object?> receipt({\n  required String id,\n  required double cash,\n  required double applied,\n  required double unallocated,\n}) {\n  return <String, Object?>{\n    'transaction_id': id,\n    'receipt_number': 'GBC-$id',\n    'amount': cash,\n    'applied_amount': applied,\n    'unallocated_amount': unallocated,\n    'allocation_state': unallocated <= 0\n        ? 'fully_allocated'\n        : applied <= 0\n            ? 'unallocated'\n            : 'partially_allocated',\n    'entry_type': 'payment',\n    'collector_user_id': 'collector-1',\n    'collector_name': 'Collector One',\n    'is_locked': false,\n  };\n}\n\nvoid main() {\n  test('two partial receipts aggregate cash and leave only the actual lacking amount', () {\n    final entry = CollectorRouteEntry.fromPayload(\n      baseEntry(\n        dailyAmount: 200,\n        receipts: <Map<String, Object?>>[\n          receipt(id: 'one', cash: 100, applied: 100, unallocated: 0),\n          receipt(id: 'two', cash: 50, applied: 50, unallocated: 0),\n        ],\n      ),\n    )!;\n\n    expect(entry.todayCashTotal, 150);\n    expect(entry.todayAppliedTotal, 150);\n    expect(entry.todayUnallocatedTotal, 0);\n    expect(entry.scheduledRemainingToday, 50);\n    expect(entry.hasReceiptApplicationReview, isFalse);\n  });\n\n  test('second real receipt after obligation is paid remains cash but is unallocated', () {\n    final entry = CollectorRouteEntry.fromPayload(\n      baseEntry(\n        dailyAmount: 100,\n        receipts: <Map<String, Object?>>[\n          receipt(id: 'one', cash: 100, applied: 100, unallocated: 0),\n          receipt(id: 'two', cash: 100, applied: 0, unallocated: 100),\n        ],\n      ),\n    )!;\n\n    expect(entry.todayCashTotal, 200);\n    expect(entry.todayAppliedTotal, 100);\n    expect(entry.todayUnallocatedTotal, 100);\n    expect(entry.scheduledRemainingToday, 0);\n    expect(entry.hasReceiptApplicationReview, isTrue);\n    expect(entry.todayReceipts.last.needsReview, isTrue);\n  });\n\n  test('legacy receipt without application fields falls back to fully applied cash', () {\n    final entry = CollectorRouteEntry.fromPayload(\n      baseEntry(\n        dailyAmount: 100,\n        receipts: <Map<String, Object?>>[\n          <String, Object?>{\n            'transaction_id': 'legacy',\n            'receipt_number': 'GBC-LEGACY',\n            'amount': 100,\n            'entry_type': 'payment',\n            'collector_user_id': 'collector-1',\n            'collector_name': 'Collector One',\n            'is_locked': false,\n          },\n        ],\n      ),\n    )!;\n\n    expect(entry.todayAppliedTotal, 100);\n    expect(entry.scheduledRemainingToday, 0);\n  });\n}\n''',
        encoding='utf-8',
    )


def cleanup() -> None:
    if WORKFLOW.exists():
        WORKFLOW.unlink()
    if SELF.exists():
        SELF.unlink()


def main() -> None:
    integrate_compact_route_ui()
    patch_backend_route_repository()
    patch_backend_route_api()
    patch_mobile_route_model()
    patch_route_page()
    patch_compact_ledger()
    write_backend_test()
    write_mobile_test()
    cleanup()


if __name__ == '__main__':
    main()

from pathlib import Path

ROUTE_PATH = Path('gilbic_mobile/lib/src/features/collector/collector_route_page.dart')
TEST_PATH = Path('gilbic_mobile/test/collector_route_collection_gate_test.dart')
WORKFLOW_PATH = Path('.github/workflows/zz_tmp_apply_synthetic_route_ui.yml')
SELF_PATH = Path('tools/tmp_apply_synthetic_route_ui.py')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old in text:
        if text.count(old) != 1:
            raise RuntimeError(f'{label}: expected exactly one match, found {text.count(old)}')
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise RuntimeError(f'{label}: target not found')


def patch_route() -> None:
    text = ROUTE_PATH.read_text(encoding='utf-8')
    text = replace_once(
        text,
        "import 'package:gilbic_mobile/src/features/collector/collection_correction_page.dart';\n",
        "import 'package:gilbic_mobile/src/features/collector/collection_correction_page.dart';\n"
        "import 'package:gilbic_mobile/src/features/collector/collector_client_ledger.dart';\n",
        'route import',
    )

    old_section = '''              _AreaLedgerSection(\n                group: group,\n                expandedClients: _expandedClients,\n                blockedReasonFor: (entry) =>\n                    _directPayBlockedReason(loaded, entry),\n                detailsBlockedReasonFor: (entry) =>\n                    _detailsBlockedReason(loaded, entry),\n                correctionBlockedReasonFor: (entry) =>\n                    _correctionBlockedReason(loaded, entry),\n                payingLoanIds: _payingLoanIds,\n                pendingDirectLoanIds: _pendingDirectDrafts.keys.toSet(),\n                onToggleClient: _toggleClient,\n                onRecord: (entry) => _payNow(loaded, entry),\n                onDetails: (entry) => _openCollectionDetails(loaded, entry),\n                onEdit: (entry) => _openCorrection(loaded, entry),\n              ),\n'''
    new_section = '''              CollectorClientLedgerSection(\n                group: group,\n                expandedClients: _expandedClients,\n                directPayBlockedReasonFor: (entry) =>\n                    _directPayBlockedReason(loaded, entry),\n                payingLoanIds: _payingLoanIds,\n                pendingDirectLoanIds: _pendingDirectDrafts.keys.toSet(),\n                onToggleClient: _toggleClient,\n                onRecord: (entry) => _payNow(loaded, entry),\n                detailsBuilder: (entry) => _LoanDetails(\n                  entry: entry,\n                  blockedReason: _directPayBlockedReason(loaded, entry),\n                  detailsBlockedReason: _detailsBlockedReason(loaded, entry),\n                  correctionBlockedReason:\n                      _correctionBlockedReason(loaded, entry),\n                  onDetails: () => _openCollectionDetails(loaded, entry),\n                  onEdit: () => _openCorrection(loaded, entry),\n                ),\n              ),\n'''
    text = replace_once(text, old_section, new_section, 'route ledger section')

    old_footer = (
        "Tap Pay for the normal scheduled amount. Expand a client only for another amount, notes, exact covered dates, unable-to-pay, recorder details, or Edit. Offline routes remain view-only."
    )
    new_footer = (
        "One client row shows Regular, 7x7 and today together. Tap Pay for one directly payable amount; expand only for special details, receipts, dates, notes or Edit. Regular + 7x7 combined Pay stays fail-closed until the atomic server allocator is available. Offline routes remain view-only."
    )
    text = replace_once(text, old_footer, new_footer, 'route footer')

    start_marker = 'class _AreaLedgerSection extends StatelessWidget {'
    end_marker = 'class _LoanDetails extends StatelessWidget {'
    if start_marker in text:
        start = text.index(start_marker)
        end = text.index(end_marker, start)
        text = text[:start] + text[end:]

    for helper_start, helper_end in [
        ('String _shortLoanName(String value) {', 'String _todayResultLabel(String value) {'),
    ]:
        if helper_start in text:
            start = text.index(helper_start)
            end = text.index(helper_end, start)
            text = text[:start] + text[end:]

    ROUTE_PATH.write_text(text, encoding='utf-8')


def patch_tests() -> None:
    text = TEST_PATH.read_text(encoding='utf-8')
    text = text.replace("expect(find.text('Lacking'), findsOneWidget);", "expect(find.text('LACKING'), findsOneWidget);")
    TEST_PATH.write_text(text, encoding='utf-8')


def main() -> None:
    patch_route()
    patch_tests()
    if WORKFLOW_PATH.exists():
        WORKFLOW_PATH.unlink()
    if SELF_PATH.exists():
        SELF_PATH.unlink()


if __name__ == '__main__':
    main()

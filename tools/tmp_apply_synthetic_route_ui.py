from pathlib import Path

ROUTE_PATH = Path('gilbic_mobile/lib/src/features/collector/collector_route_page.dart')
FIELD_HOME_PATH = Path('gilbic_mobile/lib/src/features/collector/collector_field_home_page.dart')
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


def remove_between(text: str, start_marker: str, end_marker: str, label: str) -> str:
    if start_marker not in text:
        return text
    start = text.index(start_marker)
    try:
        end = text.index(end_marker, start)
    except ValueError as exc:
        raise RuntimeError(f'{label}: end marker not found') from exc
    return text[:start] + text[end:]


def patch_route() -> None:
    text = ROUTE_PATH.read_text(encoding='utf-8')
    text = replace_once(
        text,
        "import 'package:gilbic_mobile/src/features/collector/collection_correction_page.dart';\n",
        "import 'package:gilbic_mobile/src/features/collector/collection_correction_page.dart';\n"
        "import 'package:gilbic_mobile/src/features/collector/collector_client_ledger.dart';\n"
        "import 'package:gilbic_mobile/src/features/collector/collector_route_header_cards.dart';\n",
        'route imports',
    )
    text = replace_once(
        text,
        "        title: const Text('Daily Route'),",
        "        title: const Text('Daily Collection'),",
        'route title',
    )

    old_summary = '''          _CompactRouteSummary(\n            result: loaded,\n            route: route,\n            clientCount: clientCount,\n          ),\n'''
    new_summary = '''          CollectorRouteHeaderCard(\n            result: loaded,\n            route: route,\n            clientCount: clientCount,\n          ),\n          const SizedBox(height: 8),\n          CollectorAreaArrangementCard(areas: route.areas),\n'''
    text = replace_once(text, old_summary, new_summary, 'route summary')

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

    text = remove_between(
        text,
        'class _CompactRouteSummary extends StatelessWidget {',
        'class _AreaLedgerSection extends StatelessWidget {',
        'old compact summary',
    )
    text = remove_between(
        text,
        'class _AreaLedgerSection extends StatelessWidget {',
        'class _LoanDetails extends StatelessWidget {',
        'old per-loan ledger',
    )
    text = remove_between(
        text,
        'String _shortLoanName(String value) {',
        'String _todayResultLabel(String value) {',
        'old per-loan helpers',
    )

    ROUTE_PATH.write_text(text, encoding='utf-8')


def patch_field_home() -> None:
    text = FIELD_HOME_PATH.read_text(encoding='utf-8')
    text = replace_once(
        text,
        "Daily Route and Master Review stay your main field screens.",
        "Daily Collection and Master Review stay your main field screens.",
        'more sheet wording',
    )

    synthetic_tile = '''                if (kDebugMode)\n                  _CollectorToolTile(\n                    key: const Key('collector-more-ca4-review'),\n                    icon: Icons.fact_check_outlined,\n                    title: 'CA4 synthetic field review',\n                    subtitle:\n                        'Review sample catch-up, notes, GCash and split states',\n                    onTap: () {\n                      Navigator.pop(sheetContext);\n                      _open(const CollectorSyntheticReviewPage());\n                    },\n                  ),\n'''
    other_area_tile = '''                _CollectorToolTile(\n                  key: const Key('collector-more-other-area'),\n                  icon: Icons.person_search_outlined,\n                  title: 'Other area',\n                  subtitle: 'Receive a real payment for a client outside your route',\n                  onTap: () {\n                    Navigator.pop(sheetContext);\n                    _openOtherArea();\n                  },\n                ),\n'''
    text = replace_once(
        text,
        synthetic_tile,
        synthetic_tile + other_area_tile,
        'move Other area into More',
    )

    old_switch = '''          switch (index) {\n            case 0:\n              break;\n            case 1:\n              _openMasterReview();\n            case 2:\n              _openOtherArea();\n            case 3:\n              _openRemittance();\n            case 4:\n              _openMore();\n          }\n'''
    new_switch = '''          switch (index) {\n            case 0:\n              break;\n            case 1:\n              _openMasterReview();\n            case 2:\n              _openRemittance();\n            case 3:\n              _openMore();\n          }\n'''
    text = replace_once(text, old_switch, new_switch, 'four-tab Collector nav switch')

    old_destinations = '''          NavigationDestination(\n            key: Key('collector-master-review-tab'),\n            icon: Icon(Icons.fact_check_outlined),\n            selectedIcon: Icon(Icons.fact_check_rounded),\n            label: 'Review',\n          ),\n          NavigationDestination(\n            icon: Icon(Icons.person_search_outlined),\n            selectedIcon: Icon(Icons.person_search_rounded),\n            label: 'Other area',\n          ),\n          NavigationDestination(\n            icon: Icon(Icons.account_balance_outlined),\n            selectedIcon: Icon(Icons.account_balance_rounded),\n            label: 'Remit',\n          ),\n'''
    new_destinations = '''          NavigationDestination(\n            key: Key('collector-master-review-tab'),\n            icon: Icon(Icons.fact_check_outlined),\n            selectedIcon: Icon(Icons.fact_check_rounded),\n            label: 'Master review',\n          ),\n          NavigationDestination(\n            icon: Icon(Icons.account_balance_outlined),\n            selectedIcon: Icon(Icons.account_balance_rounded),\n            label: 'Remit',\n          ),\n'''
    text = replace_once(
        text,
        old_destinations,
        new_destinations,
        'four-tab Collector nav destinations',
    )

    FIELD_HOME_PATH.write_text(text, encoding='utf-8')


def patch_tests() -> None:
    text = TEST_PATH.read_text(encoding='utf-8')
    text = text.replace(
        "expect(find.text('Lacking'), findsOneWidget);",
        "expect(find.text('LACKING'), findsOneWidget);",
    )
    TEST_PATH.write_text(text, encoding='utf-8')


def main() -> None:
    patch_route()
    patch_field_home()
    patch_tests()
    if WORKFLOW_PATH.exists():
        WORKFLOW_PATH.unlink()
    if SELF_PATH.exists():
        SELF_PATH.unlink()


if __name__ == '__main__':
    main()

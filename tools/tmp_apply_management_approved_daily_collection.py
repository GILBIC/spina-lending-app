from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
route_path = ROOT / 'gilbic_mobile/lib/src/features/collector/collector_route_page.dart'
home_path = ROOT / 'gilbic_mobile/lib/src/features/collector/collector_field_home_page.dart'
workflow_path = ROOT / '.github/workflows/zz_tmp_apply_management_approved_daily_collection.yml'
self_path = Path(__file__).resolve()

route = route_path.read_text(encoding='utf-8')

old_import = "import 'package:gilbic_mobile/src/features/collector/collection_entry_page.dart';\n"
new_import = old_import + "import 'package:gilbic_mobile/src/features/collector/collector_client_ledger.dart';\nimport 'package:gilbic_mobile/src/features/collector/collector_route_header_cards.dart';\n"
if 'collector_client_ledger.dart' not in route:
    if old_import not in route:
        raise SystemExit('route import anchor not found')
    route = route.replace(old_import, new_import, 1)

route = route.replace("title: const Text('Daily Route'),", "title: const Text('Daily Collection'),", 1)

old_summary = """          _CompactRouteSummary(\n            result: loaded,\n            route: route,\n            clientCount: clientCount,\n          ),\n"""
new_summary = """          CollectorRouteHeaderCard(\n            result: loaded,\n            route: route,\n            clientCount: clientCount,\n          ),\n          const SizedBox(height: 8),\n          CollectorAreaArrangementCard(\n            areas: areaGroups.map((group) => group.area).toList(),\n          ),\n"""
if old_summary not in route:
    raise SystemExit('summary invocation anchor not found')
route = route.replace(old_summary, new_summary, 1)

old_area = """              _AreaLedgerSection(\n                group: group,\n                expandedClients: _expandedClients,\n                blockedReasonFor: (entry) =>\n                    _directPayBlockedReason(loaded, entry),\n                detailsBlockedReasonFor: (entry) =>\n                    _detailsBlockedReason(loaded, entry),\n                correctionBlockedReasonFor: (entry) =>\n                    _correctionBlockedReason(loaded, entry),\n                payingLoanIds: _payingLoanIds,\n                pendingDirectLoanIds: _pendingDirectDrafts.keys.toSet(),\n                onToggleClient: _toggleClient,\n                onRecord: (entry) => _payNow(loaded, entry),\n                onDetails: (entry) => _openCollectionDetails(loaded, entry),\n                onEdit: (entry) => _openCorrection(loaded, entry),\n              ),\n"""
new_area = """              CollectorClientLedgerSection(\n                group: group,\n                expandedClients: _expandedClients,\n                directPayBlockedReasonFor: (entry) =>\n                    _directPayBlockedReason(loaded, entry),\n                payingLoanIds: _payingLoanIds,\n                pendingDirectLoanIds: _pendingDirectDrafts.keys.toSet(),\n                onToggleClient: _toggleClient,\n                onRecord: (entry) => _payNow(loaded, entry),\n                detailsBuilder: (entry) => _LoanDetails(\n                  entry: entry,\n                  blockedReason: _directPayBlockedReason(loaded, entry),\n                  detailsBlockedReason: _detailsBlockedReason(loaded, entry),\n                  correctionBlockedReason: _correctionBlockedReason(loaded, entry),\n                  onDetails: () => _openCollectionDetails(loaded, entry),\n                  onEdit: () => _openCorrection(loaded, entry),\n                ),\n              ),\n"""
if old_area not in route:
    raise SystemExit('area invocation anchor not found')
route = route.replace(old_area, new_area, 1)

old_footer = "Tap Pay for the normal scheduled amount. Expand a client only for another amount, notes, exact covered dates, unable-to-pay, recorder details, or Edit. Offline routes remain view-only."
new_footer = "One client stays on one Daily Collection row. TODAY keeps one-tap Pay when exactly one loan is safely payable. If Regular + 7x7 both need payment, Review fails closed until SPINA can allocate the combined cash atomically on the server. Expand only for notes, receipts, covered dates/ADV, voluntary extra, correction or other exceptions. Offline routes remain view-only."
if old_footer not in route:
    raise SystemExit('footer anchor not found')
route = route.replace(old_footer, new_footer, 1)

# Remove the obsolete compact summary + separate-loan ledger widgets while preserving
# _LoanDetails and its receipt/audit UI for expanded exceptions.
route, count = re.subn(
    r"\nclass _CompactRouteSummary extends StatelessWidget \{.*?\nclass _LoanDetails extends StatelessWidget \{",
    "\nclass _LoanDetails extends StatelessWidget {",
    route,
    count=1,
    flags=re.S,
)
if count != 1:
    raise SystemExit(f'obsolete ledger class removal count={count}')

# Remove helpers used only by the deleted separate-loan ledger/summary.
for pattern in [
    r"\nString _shortLoanName\(String value\) \{.*?\n\}\n",
    r"\nString _shortStatus\(CollectorRouteEntry entry\) \{.*?\n\}\n",
    r"\nString _actionLabel\(.*?\n\}\n",
    r"\nString _time\(DateTime value\) \{.*?\n\}\n",
    r"\nString _money\(double value\) \{.*?\n\}\n",
]:
    route, removed = re.subn(pattern, "\n", route, count=1, flags=re.S)
    if removed != 1:
        raise SystemExit(f'expected obsolete helper not removed: {pattern}')

route_path.write_text(route, encoding='utf-8')

home = home_path.read_text(encoding='utf-8')
home = home.replace(
    'The familiar ledger stays the primary screen after sign-in. Master Review is\n/// a first-class field action so a Collector can check every assigned area before\n/// leaving the route. Secondary tools remain behind compact navigation.',
    'The Management-approved Daily Collection ledger is the primary screen after sign-in.\n/// Master Review is a first-class field action; secondary tools remain behind More.',
    1,
)
home = home.replace(
    "'Daily Route and Master Review stay your main field screens.'",
    "'Daily Collection and Master Review stay your main field screens.'",
    1,
)

anchor = """                if (kDebugMode)\n                  _CollectorToolTile(\n                    key: const Key('collector-more-ca4-review'),\n                    icon: Icons.fact_check_outlined,\n                    title: 'CA4 synthetic field review',\n                    subtitle:\n                        'Review sample catch-up, notes, GCash and split states',\n                    onTap: () {\n                      Navigator.pop(sheetContext);\n                      _open(const CollectorSyntheticReviewPage());\n                    },\n                  ),\n"""
insert = anchor + """                _CollectorToolTile(\n                  key: const Key('collector-more-other-area'),\n                  icon: Icons.person_search_outlined,\n                  title: 'Other area payment',\n                  subtitle: 'Record an allowed payment outside your assigned route',\n                  onTap: () {\n                    Navigator.pop(sheetContext);\n                    _openOtherArea();\n                  },\n                ),\n"""
if anchor not in home:
    raise SystemExit('More sheet anchor not found')
home = home.replace(anchor, insert, 1)

old_switch = """            case 0:\n              break;\n            case 1:\n              _openMasterReview();\n            case 2:\n              _openOtherArea();\n            case 3:\n              _openRemittance();\n            case 4:\n              _openMore();\n"""
new_switch = """            case 0:\n              break;\n            case 1:\n              _openMasterReview();\n            case 2:\n              _openRemittance();\n            case 3:\n              _openMore();\n"""
if old_switch not in home:
    raise SystemExit('navigation switch anchor not found')
home = home.replace(old_switch, new_switch, 1)

old_destinations = """          NavigationDestination(\n            key: Key('collector-master-review-tab'),\n            icon: Icon(Icons.fact_check_outlined),\n            selectedIcon: Icon(Icons.fact_check_rounded),\n            label: 'Review',\n          ),\n          NavigationDestination(\n            icon: Icon(Icons.person_search_outlined),\n            selectedIcon: Icon(Icons.person_search_rounded),\n            label: 'Other area',\n          ),\n          NavigationDestination(\n            icon: Icon(Icons.account_balance_outlined),\n            selectedIcon: Icon(Icons.account_balance_rounded),\n            label: 'Remit',\n          ),\n"""
new_destinations = """          NavigationDestination(\n            key: Key('collector-master-review-tab'),\n            icon: Icon(Icons.fact_check_outlined),\n            selectedIcon: Icon(Icons.fact_check_rounded),\n            label: 'Master review',\n          ),\n          NavigationDestination(\n            icon: Icon(Icons.account_balance_outlined),\n            selectedIcon: Icon(Icons.account_balance_rounded),\n            label: 'Remit',\n          ),\n"""
if old_destinations not in home:
    raise SystemExit('navigation destination anchor not found')
home = home.replace(old_destinations, new_destinations, 1)
home_path.write_text(home, encoding='utf-8')

# Self-clean temporary integration machinery so the product commit contains only
# the real source changes.
if self_path.exists():
    self_path.unlink()
if workflow_path.exists():
    workflow_path.unlink()

print('Applied Management-approved authenticated Daily Collection layout.')

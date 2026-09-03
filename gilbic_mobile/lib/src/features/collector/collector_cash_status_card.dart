import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/remittance/collector_cash_accountability_repository.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow_repository.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

/// Compact field-cash status shown above Daily Collection.
///
/// Daily Collection shows only the Collector's collection-cash responsibility.
/// Renewal release actions belong in Renewal Requests, while remittance states,
/// submission details and history belong in the dedicated Remit workflow.
class CollectorCashStatusCard extends StatefulWidget {
  const CollectorCashStatusCard({
    required this.session,
    required this.deviceIdentityProvider,
    required this.onOpenRemittance,
    required this.onOpenRenewals,
    required this.onOpenCashToReceive,
    required this.onOpenCashToClient,
    this.onCashReleaseAlert,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;

  /// Retained for Collector-shell compatibility. Daily Collection intentionally
  /// does not expose these workflow actions directly.
  final VoidCallback onOpenRemittance;
  final VoidCallback onOpenRenewals;
  final VoidCallback onOpenCashToReceive;
  final VoidCallback onOpenCashToClient;

  /// Called when the server reports a Management-released renewal amount still
  /// waiting for this Collector's physical receipt confirmation.
  final ValueChanged<CollectorRenewalRequest>? onCashReleaseAlert;

  @override
  State<CollectorCashStatusCard> createState() => _CollectorCashStatusCardState();
}

class _CollectorCashStatusCardState extends State<CollectorCashStatusCard> {
  final CollectorCashAccountabilityRepository _cashAccountability =
      SpinaCollectorCashAccountabilityRepository();
  final CollectorRenewalWorkflowRepository _renewals =
      SpinaCollectorRenewalWorkflowRepository();

  double _totalCollectionCashHeld = 0;
  double _assignedAreaCashHeld = 0;
  double _otherAreaCashHeld = 0;
  List<CollectorCashByAssignedCollector> _otherAreaByCollector =
      const <CollectorCashByAssignedCollector>[];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (!mounted) return;

    final canLoadCash = widget.session.hasPermission('remittance.view');
    final canLoadRenewals =
        widget.session.hasPermission('renewal.recommend.assigned');

    // A route-only Collector does not need a device identity or any cash/release
    // network request merely to render Daily Collection. Keeping this path local
    // also prevents optional cash status from delaying the primary field screen.
    if (!canLoadCash && !canLoadRenewals) {
      setState(() {
        _totalCollectionCashHeld = 0;
        _assignedAreaCashHeld = 0;
        _otherAreaCashHeld = 0;
        _otherAreaByCollector = const <CollectorCashByAssignedCollector>[];
        _loading = false;
      });
      return;
    }

    setState(() => _loading = true);

    var totalCollectionCashHeld = 0.0;
    var assignedAreaCashHeld = 0.0;
    var otherAreaCashHeld = 0.0;
    var otherAreaByCollector = const <CollectorCashByAssignedCollector>[];
    CollectorRenewalRequest? cashReleaseAlert;

    try {
      final identity = await widget.deviceIdentityProvider.load();

      if (canLoadCash) {
        try {
          final accountability = await _cashAccountability.load(
            widget.session,
            deviceId: identity.installationId,
          );
          totalCollectionCashHeld = accountability.totalCashHeld;
          assignedAreaCashHeld = accountability.assignedAreaCashHeld;
          otherAreaCashHeld = accountability.otherAreaCashHeld;
          otherAreaByCollector = accountability.otherAreaByCollector;
        } on Object {
          // Cash status must not block Daily Collection if the summary is unavailable.
        }
      }

      if (canLoadRenewals) {
        try {
          final requests = await _renewals.list(
            widget.session,
            deviceId: identity.installationId,
          );
          for (final request in requests) {
            if (request.canConfirmCashReceived) {
              cashReleaseAlert = request;
              break;
            }
          }
        } on Object {
          // A renewal endpoint failure must not block Daily Collection.
        }
      }
    } on Object {
      // Device/network status is secondary to keeping Daily Collection available.
    }

    if (!mounted) return;
    setState(() {
      _totalCollectionCashHeld = totalCollectionCashHeld;
      _assignedAreaCashHeld = assignedAreaCashHeld;
      _otherAreaCashHeld = otherAreaCashHeld;
      _otherAreaByCollector = otherAreaByCollector;
      _loading = false;
    });
    if (cashReleaseAlert != null) {
      widget.onCashReleaseAlert?.call(cashReleaseAlert);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      key: const Key('collector-cash-status-card'),
      margin: const EdgeInsets.fromLTRB(10, 8, 10, 0),
      padding: const EdgeInsets.fromLTRB(12, 10, 8, 10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: SpinaTheme.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.account_balance_wallet_outlined,
                size: 19,
                color: SpinaTheme.brandPinkDark,
              ),
              const SizedBox(width: 7),
              Expanded(
                child: Text(
                  'Field cash',
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              IconButton(
                key: const Key('collector-cash-status-refresh'),
                tooltip: 'Refresh cash status',
                visualDensity: VisualDensity.compact,
                onPressed: _loading ? null : _load,
                icon: _loading
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.refresh_rounded, size: 19),
              ),
            ],
          ),
          _PrimaryCashHeldTile(
            amount: _totalCollectionCashHeld,
            assignedAreaAmount: _assignedAreaCashHeld,
            otherAreaAmount: _otherAreaCashHeld,
            otherAreaByCollector: _otherAreaByCollector,
          ),
        ],
      ),
    );
  }
}

class _PrimaryCashHeldTile extends StatelessWidget {
  const _PrimaryCashHeldTile({
    required this.amount,
    required this.assignedAreaAmount,
    required this.otherAreaAmount,
    required this.otherAreaByCollector,
  });

  final double amount;
  final double assignedAreaAmount;
  final double otherAreaAmount;
  final List<CollectorCashByAssignedCollector> otherAreaByCollector;

  @override
  Widget build(BuildContext context) {
    return Container(
      key: const Key('collector-total-cash-held'),
      padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 10),
      decoration: BoxDecoration(
        color: SpinaTheme.brandPinkSoft,
        borderRadius: BorderRadius.circular(13),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Cash held',
                      style: Theme.of(context).textTheme.labelMedium?.copyWith(
                            color: SpinaTheme.brandPinkDark,
                            fontWeight: FontWeight.w900,
                          ),
                    ),
                    const SizedBox(height: 1),
                    Text(
                      'Collection cash still under your responsibility',
                      style: Theme.of(context).textTheme.labelSmall,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Text(
                _money(amount),
                key: const Key('collector-total-cash-held-value'),
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      color: SpinaTheme.brandPinkDark,
                      fontWeight: FontWeight.w900,
                    ),
              ),
            ],
          ),
          const SizedBox(height: 9),
          Container(height: 1, color: SpinaTheme.line),
          const SizedBox(height: 8),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: _CashHeldBreakdown(
                  key: const Key('collector-assigned-area-cash-held'),
                  title: 'My assigned areas',
                  amount: assignedAreaAmount,
                  subtitle: 'Your route cash',
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _CashHeldBreakdown(
                  key: const Key('collector-other-area-cash-held'),
                  title: 'Different collectors',
                  amount: otherAreaAmount,
                  subtitle: 'Cash from their assigned areas',
                ),
              ),
            ],
          ),
          if (otherAreaByCollector.isNotEmpty) ...[
            const SizedBox(height: 8),
            Container(height: 1, color: SpinaTheme.line),
            const SizedBox(height: 7),
            Text(
              'Different collector breakdown',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
            ),
            const SizedBox(height: 4),
            for (final item in otherAreaByCollector)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Row(
                  key: Key(
                    'collector-other-area-owner-${item.collectorUserId}',
                  ),
                  children: [
                    Expanded(
                      child: Text(
                        item.collectorName,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.labelSmall,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      _money(item.amount),
                      style: Theme.of(context).textTheme.labelMedium?.copyWith(
                            color: SpinaTheme.brandPinkDark,
                            fontWeight: FontWeight.w900,
                          ),
                    ),
                  ],
                ),
              ),
          ],
        ],
      ),
    );
  }
}

class _CashHeldBreakdown extends StatelessWidget {
  const _CashHeldBreakdown({
    required this.title,
    required this.amount,
    required this.subtitle,
    super.key,
  });

  final String title;
  final double amount;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
                fontWeight: FontWeight.w900,
              ),
        ),
        const SizedBox(height: 1),
        Text(
          _money(amount),
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                color: SpinaTheme.brandPinkDark,
                fontWeight: FontWeight.w900,
              ),
        ),
        Text(
          subtitle,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: Theme.of(context).textTheme.labelSmall?.copyWith(fontSize: 9),
        ),
      ],
    );
  }
}

String _money(double value) {
  final fixed = value.toStringAsFixed(2).split('.');
  return '₱${_groupDigits(fixed.first)}.${fixed.last}';
}

String _groupDigits(String digits) {
  final buffer = StringBuffer();
  for (var index = 0; index < digits.length; index += 1) {
    if (index > 0 && (digits.length - index) % 3 == 0) {
      buffer.write(',');
    }
    buffer.write(digits[index]);
  }
  return buffer.toString();
}

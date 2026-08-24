import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/remittance/collector_cash_accountability_repository.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow_repository.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

/// Compact field-cash status shown above Daily Collection.
///
/// Daily Collection shows only the Collector's total collection-cash
/// responsibility plus immediate loan-release field actions. Remittance states,
/// submission details and history belong exclusively to the Remit workflow.
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
  /// does not expose this action; remittance stays in the dedicated Remit tab.
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
  int _cashToReceiveCount = 0;
  double _cashToReceiveAmount = 0;
  int _cashWithCollectorCount = 0;
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
        _cashToReceiveCount = 0;
        _cashToReceiveAmount = 0;
        _cashWithCollectorCount = 0;
        _loading = false;
      });
      return;
    }

    setState(() => _loading = true);

    var totalCollectionCashHeld = 0.0;
    var assignedAreaCashHeld = 0.0;
    var otherAreaCashHeld = 0.0;
    var cashToReceiveCount = 0;
    var cashToReceiveAmount = 0.0;
    var cashWithCollectorCount = 0;
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
          final toReceive = requests
              .where((request) => request.canConfirmCashReceived)
              .toList(growable: false);
          cashWithCollectorCount = requests
              .where((request) => request.canConfirmCashGiven)
              .length;
          cashToReceiveCount = toReceive.length;
          cashToReceiveAmount = _releaseTotal(toReceive);
          if (toReceive.isNotEmpty) cashReleaseAlert = toReceive.first;
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
      _cashToReceiveCount = cashToReceiveCount;
      _cashToReceiveAmount = cashToReceiveAmount;
      _cashWithCollectorCount = cashWithCollectorCount;
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
          ),
          const SizedBox(height: 9),
          Text(
            'Loan releases',
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 4),
          Row(
            children: [
              Expanded(
                child: _CashStatusTile(
                  key: const Key('collector-cash-to-receive'),
                  title: 'Cash to receive',
                  value:
                      '$_cashToReceiveCount • ${_money(_cashToReceiveAmount)}',
                  subtitle: _cashToReceiveCount == 0
                      ? 'No Management release'
                      : 'Management releases waiting',
                  emphasized: _cashToReceiveCount > 0,
                  enabled: canRenewals(widget.session),
                  onTap: widget.onOpenCashToReceive,
                ),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: _CashStatusTile(
                  key: const Key('collector-cash-to-client'),
                  title: 'Give to client',
                  value: '$_cashWithCollectorCount',
                  subtitle: _cashWithCollectorCount == 0
                      ? 'No release in custody'
                      : 'Open handover queue',
                  emphasized: _cashWithCollectorCount > 0,
                  enabled: canRenewals(widget.session),
                  onTap: widget.onOpenCashToClient,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

bool canRenewals(UserSession session) {
  return session.hasPermission('renewal.recommend.assigned');
}

class _PrimaryCashHeldTile extends StatelessWidget {
  const _PrimaryCashHeldTile({
    required this.amount,
    required this.assignedAreaAmount,
    required this.otherAreaAmount,
  });

  final double amount;
  final double assignedAreaAmount;
  final double otherAreaAmount;

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
                  title: 'Assigned areas',
                  amount: assignedAreaAmount,
                  subtitle: 'Your route cash',
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _CashHeldBreakdown(
                  key: const Key('collector-other-area-cash-held'),
                  title: 'Other areas',
                  amount: otherAreaAmount,
                  subtitle: 'Collected for another Collector',
                ),
              ),
            ],
          ),
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

class _CashStatusTile extends StatelessWidget {
  const _CashStatusTile({
    required this.title,
    required this.value,
    required this.subtitle,
    required this.enabled,
    required this.onTap,
    this.emphasized = false,
    super.key,
  });

  final String title;
  final String value;
  final String subtitle;
  final bool emphasized;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: emphasized ? SpinaTheme.brandPinkSoft : const Color(0xFFFFFAFC),
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: enabled ? onTap : null,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
              ),
              const SizedBox(height: 2),
              Text(
                value,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      color: emphasized
                          ? SpinaTheme.brandPinkDark
                          : SpinaTheme.ink,
                      fontWeight: FontWeight.w900,
                    ),
              ),
              Text(
                subtitle,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      fontSize: 9,
                    ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

double _releaseTotal(Iterable<CollectorRenewalRequest> requests) {
  return requests.fold<double>(
    0,
    (total, request) => total + (request.netReleaseAmount ?? 0),
  );
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

import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/formatting/spina_display.dart';
import 'dart:async';

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
    this.onSignOut,
    super.key,
  });

  final UserSession session;
  final Future<void> Function()? onSignOut;
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
  State<CollectorCashStatusCard> createState() =>
      _CollectorCashStatusCardState();
}

class _CollectorCashStatusCardState extends State<CollectorCashStatusCard> {
  final CollectorCashAccountabilityRepository _cashAccountability =
      SpinaCollectorCashAccountabilityRepository();
  final CollectorRenewalWorkflowRepository _renewals =
      SpinaCollectorRenewalWorkflowRepository();

  CollectorCashAccountability? _accountability;
  bool _loading = false;
  bool _renewalAlertLoading = false;
  bool _stale = false;
  int? _failureStatus;
  int _generation = 0;
  int _privacyGeneration = 0;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(CollectorCashStatusCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.session != widget.session ||
        oldWidget.deviceIdentityProvider != widget.deviceIdentityProvider) {
      _privacyGeneration++;
      _generation++;
      _loading = false;
      _failureStatus = null;
      _accountability = null;
      _stale = false;
      unawaited(_load());
    }
  }

  Future<void> _load() async {
    if (!mounted || _loading || _readBlocked) return;
    final generation = ++_generation;
    final session = widget.session;
    _failureStatus = null;

    final canLoadCash = widget.session.hasPermission('remittance.view');
    final canLoadRenewals = widget.session.hasAnyPermission(const <String>[
      'renewal.recommend.assigned',
      'renewal.cash_custody.assigned',
    ]);

    // A route-only Collector does not need a device identity or any cash/release
    // network request merely to render Daily Collection. Keeping this path local
    // also prevents optional cash status from delaying the primary field screen.
    if (!canLoadCash && !canLoadRenewals) {
      setState(() {
        _accountability = null;
        _loading = false;
      });
      return;
    }

    setState(() {
      _loading = true;
    });

    CollectorCashAccountability? accountability;
    String? deviceId;

    try {
      final identity = await widget.deviceIdentityProvider.load();
      if (!mounted || generation != _generation) return;
      deviceId = identity.installationId;

      if (canLoadCash) {
        try {
          accountability = await _cashAccountability.load(
            session,
            deviceId: identity.installationId,
          );
        } on SpinaApiException catch (error) {
          if (generation != _generation || !mounted) return;
          _failureStatus = error.statusCode;
          if (_readBlocked) {
            _privacyGeneration++;
          }
        } on Object {
          // Cash status must not block Daily Collection if the summary is unavailable.
        }
      }
    } on Object {
      // Device/network status is secondary to keeping Daily Collection available.
    }

    if (!mounted || generation != _generation) return;
    setState(() {
      _stale =
          accountability == null && !_readBlocked && _accountability != null;
      if (accountability != null || _readBlocked) {
        _accountability = accountability;
      }
      _loading = false;
    });
    if (canLoadRenewals && deviceId != null && !_readBlocked) {
      unawaited(_loadCashReleaseAlert(deviceId));
    }
  }

  bool get _readBlocked => const {401, 403, 426}.contains(_failureStatus);

  Future<void> _loadCashReleaseAlert(String deviceId) async {
    // Cash can refresh while this optional check is pending. Keep one pending
    // renewal request per card so responses cannot race to show older alerts.
    if (!mounted || _renewalAlertLoading) return;
    _renewalAlertLoading = true;
    final generation = _privacyGeneration;
    final session = widget.session;
    try {
      final requests = await _renewals.list(session, deviceId: deviceId);
      if (!mounted || generation != _privacyGeneration) return;
      for (final request in requests) {
        if (request.canConfirmCashReceived) {
          widget.onCashReleaseAlert?.call(request);
          break;
        }
      }
    } on Object {
      // Optional renewal alerts must not block cash status or its refresh.
    } finally {
      _renewalAlertLoading = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.session.hasPermission('remittance.view')) {
      return const SizedBox.shrink();
    }
    final accountability = _accountability;
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
                  style: Theme.of(
                    context,
                  ).textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w900),
                ),
              ),
              IconButton(
                key: const Key('collector-cash-status-refresh'),
                tooltip: _failureStatus == 426
                    ? widget.onSignOut == null
                          ? 'Update required'
                          : 'Return to sign-in'
                    : _failureStatus == 401
                    ? 'Sign in again'
                    : 'Refresh cash status',
                visualDensity: VisualDensity.compact,
                onPressed: _loading || _failureStatus == 403
                    ? null
                    : _failureStatus == 401 || _failureStatus == 426
                    ? widget.onSignOut == null
                          ? null
                          : () => unawaited(widget.onSignOut!())
                    : _load,
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
          if (_loading)
            const Text('Loading cash status…')
          else if (_stale)
            const Text(
              'Last successful cash status. It has not been refreshed. Connect and refresh.',
            ),
          if (accountability != null)
            _PrimaryCashHeldTile(
              amount: accountability.totalCashHeld,
              assignedAreaAmount: accountability.assignedAreaCashHeld,
              otherAreaAmount: accountability.otherAreaCashHeld,
              otherAreaByCollector: accountability.otherAreaByCollector,
            )
          else if (!_loading)
            Text(switch (_failureStatus) {
              401 => 'Cash status unavailable. Sign in again to continue.',
              403 =>
                'Access unavailable. This account or device cannot view cash status.',
              426 =>
                'Update required. Return to sign-in and follow the SPINA update guidance before refreshing cash status.',
              _ => 'Cash status unavailable. Connect and refresh.',
            }),
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
          LayoutBuilder(
            builder: (context, constraints) {
              final labels = Column(
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
              );
              final value = Text(
                _money(amount),
                key: const Key('collector-total-cash-held-value'),
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: SpinaTheme.brandPinkDark,
                  fontWeight: FontWeight.w900,
                ),
              );
              if (constraints.maxWidth < 350 ||
                  MediaQuery.textScalerOf(context).scale(14) > 16 ||
                  _money(amount).length > 14) {
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [labels, const SizedBox(height: 4), value],
                );
              }
              return Row(
                children: [
                  Expanded(child: labels),
                  const SizedBox(width: 8),
                  value,
                ],
              );
            },
          ),
          const SizedBox(height: 9),
          Container(height: 1, color: SpinaTheme.line),
          const SizedBox(height: 8),
          LayoutBuilder(
            builder: (context, constraints) {
              final assigned = _CashHeldBreakdown(
                key: const Key('collector-assigned-area-cash-held'),
                title: 'My assigned areas',
                amount: assignedAreaAmount,
                subtitle: 'Your route cash',
              );
              final other = _CashHeldBreakdown(
                key: const Key('collector-other-area-cash-held'),
                title: 'Different collectors',
                amount: otherAreaAmount,
                subtitle: 'Cash from their assigned areas',
              );
              if (constraints.maxWidth < 350 ||
                  MediaQuery.textScalerOf(context).scale(14) > 16) {
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [assigned, const SizedBox(height: 8), other],
                );
              }
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(child: assigned),
                  const SizedBox(width: 12),
                  Expanded(child: other),
                ],
              );
            },
          ),
          if (otherAreaByCollector.isNotEmpty) ...[
            const SizedBox(height: 8),
            Container(height: 1, color: SpinaTheme.line),
            const SizedBox(height: 7),
            Text(
              'Different collector breakdown',
              style: Theme.of(
                context,
              ).textTheme.labelSmall?.copyWith(fontWeight: FontWeight.w900),
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
          style: Theme.of(
            context,
          ).textTheme.labelSmall?.copyWith(fontWeight: FontWeight.w900),
        ),
        const SizedBox(height: 1),
        Text(
          _money(amount),
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
            color: SpinaTheme.brandPinkDark,
            fontWeight: FontWeight.w900,
          ),
        ),
        Text(subtitle, style: Theme.of(context).textTheme.labelSmall),
      ],
    );
  }
}

// Legacy cash/route models are numeric; this preserves their existing display conversion.
String _money(double value) =>
    value.isFinite ? formatSpinaMoney(value.toStringAsFixed(2)) : 'Unavailable';

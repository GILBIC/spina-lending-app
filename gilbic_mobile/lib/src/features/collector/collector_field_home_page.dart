import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow.dart';
import 'package:gilbic_mobile/src/features/account/account_settings_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_cash_status_card.dart';
import 'package:gilbic_mobile/src/features/collector/collector_cash_to_client_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_cash_to_receive_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_master_review_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_remittance_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_renewal_cash_release_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_renewal_requests_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_page.dart';
import 'package:gilbic_mobile/src/features/collector/cross_collector_remittance_page.dart';
import 'package:gilbic_mobile/src/features/collector/other_area_collection_page.dart';
import 'package:gilbic_mobile/src/features/notifications/activity_notifications_page.dart';
import 'package:gilbic_mobile/src/features/notifications/remittance_notifications_page.dart';
import 'package:gilbic_mobile/src/features/offline/mobile_offline_policy_page.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

/// Collector-first shell for CA4.
///
/// Daily Collection remains the primary screen after sign-in. Cash/release
/// responsibility is surfaced above the route so handoffs are not hidden under More.
class CollectorFieldHomePage extends StatefulWidget {
  const CollectorFieldHomePage({
    required this.session,
    required this.onSignOut,
    required this.collectorRouteLoader,
    required this.paymentSubmissionRepository,
    required this.deviceIdentityProvider,
    required this.collectionDeviceSequence,
    super.key,
  });

  final UserSession session;
  final Future<void> Function() onSignOut;
  final CollectorRouteLoader collectorRouteLoader;
  final PaymentSubmissionRepository paymentSubmissionRepository;
  final DeviceIdentityProvider deviceIdentityProvider;
  final CollectionDeviceSequence collectionDeviceSequence;

  @override
  State<CollectorFieldHomePage> createState() => _CollectorFieldHomePageState();
}

class _CollectorFieldHomePageState extends State<CollectorFieldHomePage> {
  String? _lastCashReleaseAlertRequestId;
  int _cashStatusEpoch = 0;

  Future<void> _open(Widget page) async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(builder: (_) => page),
    );
  }

  void _permissionMessage(String feature) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'Your current Gilbic access does not allow $feature.',
        ),
      ),
    );
  }

  void _refreshCashStatus() {
    if (!mounted) return;
    setState(() => _cashStatusEpoch += 1);
  }

  Future<void> _openMasterReview() async {
    await _open(
      CollectorMasterReviewPage(
        session: widget.session,
        loader: widget.collectorRouteLoader,
      ),
    );
  }

  Future<void> _openOtherArea() async {
    if (!widget.session.hasPermission('collection.create')) {
      _permissionMessage('other-area payment entry');
      return;
    }
    await _open(
      OtherAreaCollectionPage(
        session: widget.session,
        paymentRepository: widget.paymentSubmissionRepository,
        deviceIdentityProvider: widget.deviceIdentityProvider,
        deviceSequence: widget.collectionDeviceSequence,
      ),
    );
  }

  Future<void> _openRenewals() async {
    if (!widget.session.hasPermission('renewal.recommend.assigned')) {
      _permissionMessage('assigned-client renewal recommendations');
      return;
    }
    await _open(
      CollectorRenewalRequestsPage(
        session: widget.session,
        deviceIdentityProvider: widget.deviceIdentityProvider,
      ),
    );
    _refreshCashStatus();
  }

  Future<void> _openCashToReceive() async {
    if (!widget.session.hasPermission('renewal.recommend.assigned')) {
      _permissionMessage('assigned-client renewal cash releases');
      return;
    }
    await _open(
      CollectorCashToReceivePage(
        session: widget.session,
        deviceIdentityProvider: widget.deviceIdentityProvider,
      ),
    );
    _refreshCashStatus();
  }

  Future<void> _openCashToClient() async {
    if (!widget.session.hasPermission('renewal.recommend.assigned')) {
      _permissionMessage('assigned-client renewal cash handovers');
      return;
    }
    await _open(
      CollectorCashToClientPage(
        session: widget.session,
        deviceIdentityProvider: widget.deviceIdentityProvider,
      ),
    );
    _refreshCashStatus();
  }

  Future<void> _openCashRelease(CollectorRenewalRequest request) async {
    ScaffoldMessenger.of(context).hideCurrentMaterialBanner();
    await _open(
      CollectorRenewalCashReleasePage(
        session: widget.session,
        deviceIdentityProvider: widget.deviceIdentityProvider,
        request: request,
      ),
    );
    _refreshCashStatus();
  }

  void _showCashReleaseAlert(CollectorRenewalRequest request) {
    if (!mounted ||
        _lastCashReleaseAlertRequestId == request.requestId ||
        !request.canConfirmCashReceived) {
      return;
    }
    _lastCashReleaseAlertRequestId = request.requestId;

    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentMaterialBanner();
    messenger.showMaterialBanner(
      MaterialBanner(
        key: Key('collector-cash-release-banner-${request.requestId}'),
        leading: const Icon(
          Icons.notifications_active_outlined,
          color: SpinaTheme.brandPinkDark,
        ),
        backgroundColor: SpinaTheme.brandPinkSoft,
        content: InkWell(
          onTap: () => _openCashRelease(request),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Text(
              'Management released ${_money(request.netReleaseAmount ?? 0)} for ${request.clientName}. Confirm receipt when you physically receive the cash.',
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
          ),
        ),
        actions: [
          TextButton(
            key: const Key('collector-cash-release-banner-view'),
            onPressed: () => _openCashRelease(request),
            child: const Text('VIEW'),
          ),
        ],
      ),
    );

    Future<void>.delayed(const Duration(seconds: 6), () {
      if (!mounted ||
          _lastCashReleaseAlertRequestId != request.requestId) {
        return;
      }
      ScaffoldMessenger.of(context).hideCurrentMaterialBanner();
    });
  }

  Future<void> _openRemittance() async {
    if (!widget.session.hasPermission('remittance.create')) {
      _permissionMessage('remittance submission');
      return;
    }
    await _open(
      CollectorRemittancePage(
        session: widget.session,
        deviceIdentityProvider: widget.deviceIdentityProvider,
      ),
    );
    _refreshCashStatus();
  }

  Future<void> _openMore() async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(18, 4, 18, 18),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Collector tools',
                  style: Theme.of(sheetContext).textTheme.titleLarge,
                ),
                const SizedBox(height: 4),
                Text(
                  'Daily Collection and Master Review stay your main field screens.',
                  style: Theme.of(sheetContext).textTheme.bodySmall,
                ),
                const SizedBox(height: 14),
                _CollectorToolTile(
                  key: const Key('collector-more-renewals'),
                  icon: Icons.autorenew_rounded,
                  title: 'Renewal requests',
                  subtitle:
                      'Recommend assigned clients and track terms, signers, cash and proof',
                  onTap: () {
                    Navigator.pop(sheetContext);
                    _openRenewals();
                  },
                ),
                _CollectorToolTile(
                  key: const Key('collector-more-other-area'),
                  icon: Icons.person_search_outlined,
                  title: 'Other area payment',
                  subtitle: 'Record an allowed payment outside your assigned route',
                  onTap: () {
                    Navigator.pop(sheetContext);
                    _openOtherArea();
                  },
                ),
                _CollectorToolTile(
                  key: const Key('collector-more-payment-updates'),
                  icon: Icons.receipt_long_outlined,
                  title: 'Payment updates',
                  subtitle: 'Other-collector posts and custody updates',
                  onTap: () {
                    Navigator.pop(sheetContext);
                    _open(
                      ActivityNotificationsPage(
                        session: widget.session,
                        deviceIdentityProvider: widget.deviceIdentityProvider,
                      ),
                    );
                  },
                ),
                if (widget.session.hasPermission('remittance.view'))
                  _CollectorToolTile(
                    key: const Key('collector-more-remittance-requests'),
                    icon: Icons.notifications_active_outlined,
                    title: 'Remittance requests',
                    subtitle: 'Review remittances sent to your route',
                    onTap: () {
                      Navigator.pop(sheetContext);
                      _open(
                        RemittanceNotificationsPage(
                          session: widget.session,
                          deviceIdentityProvider: widget.deviceIdentityProvider,
                        ),
                      );
                    },
                  ),
                if (widget.session.hasPermission('remittance.create'))
                  _CollectorToolTile(
                    key: const Key('collector-more-assigned-remittance'),
                    icon: Icons.compare_arrows_rounded,
                    title: 'Other-area remittance',
                    subtitle: 'Send other-area cash to the route owner or Management',
                    onTap: () {
                      Navigator.pop(sheetContext);
                      _open(
                        CrossCollectorRemittancePage(
                          session: widget.session,
                          deviceIdentityProvider: widget.deviceIdentityProvider,
                        ),
                      );
                    },
                  ),
                const Divider(height: 20),
                _CollectorToolTile(
                  key: const Key('collector-more-offline'),
                  icon: Icons.cloud_off_outlined,
                  title: 'Offline & sync',
                  subtitle: 'Review the read-only offline route policy',
                  onTap: () {
                    Navigator.pop(sheetContext);
                    _open(MobileOfflinePolicyPage(session: widget.session));
                  },
                ),
                _CollectorToolTile(
                  key: const Key('collector-more-profile'),
                  icon: Icons.person_outline_rounded,
                  title: 'Profile & security',
                  subtitle: 'Account, session and registered devices',
                  onTap: () {
                    Navigator.pop(sheetContext);
                    _open(
                      AccountSettingsPage(
                        session: widget.session,
                        onSignOut: widget.onSignOut,
                        deviceIdentityProvider: widget.deviceIdentityProvider,
                      ),
                    );
                  },
                ),
                _CollectorToolTile(
                  key: const Key('collector-more-sign-out'),
                  icon: Icons.logout_rounded,
                  title: 'Sign out',
                  subtitle: 'End this Gilbic session on the device',
                  destructive: true,
                  onTap: () {
                    Navigator.pop(sheetContext);
                    widget.onSignOut();
                  },
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          SafeArea(
            bottom: false,
            child: CollectorCashStatusCard(
              key: ValueKey('collector-cash-status-$_cashStatusEpoch'),
              session: widget.session,
              deviceIdentityProvider: widget.deviceIdentityProvider,
              onOpenRemittance: _openRemittance,
              onOpenRenewals: _openRenewals,
              onOpenCashToReceive: _openCashToReceive,
              onOpenCashToClient: _openCashToClient,
              onCashReleaseAlert: _showCashReleaseAlert,
            ),
          ),
          Expanded(
            child: CollectorRoutePage(
              session: widget.session,
              loader: widget.collectorRouteLoader,
              paymentRepository: widget.paymentSubmissionRepository,
              deviceIdentityProvider: widget.deviceIdentityProvider,
              deviceSequence: widget.collectionDeviceSequence,
            ),
          ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: 0,
        onDestinationSelected: (index) {
          switch (index) {
            case 0:
              break;
            case 1:
              _openMasterReview();
            case 2:
              _openRemittance();
            case 3:
              _openMore();
          }
        },
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.route_outlined),
            selectedIcon: Icon(Icons.route_rounded),
            label: 'Route',
          ),
          NavigationDestination(
            key: Key('collector-master-review-tab'),
            icon: Icon(Icons.fact_check_outlined),
            selectedIcon: Icon(Icons.fact_check_rounded),
            label: 'Master review',
          ),
          NavigationDestination(
            icon: Icon(Icons.account_balance_outlined),
            selectedIcon: Icon(Icons.account_balance_rounded),
            label: 'Remit',
          ),
          NavigationDestination(
            key: Key('collector-more-tab'),
            icon: Icon(Icons.more_horiz_rounded),
            label: 'More',
          ),
        ],
      ),
    );
  }
}

class _CollectorToolTile extends StatelessWidget {
  const _CollectorToolTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.destructive = false,
    super.key,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  final bool destructive;

  @override
  Widget build(BuildContext context) {
    final foreground = destructive
        ? Theme.of(context).colorScheme.error
        : SpinaTheme.brandPinkDark;
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 4),
      leading: Container(
        width: 42,
        height: 42,
        decoration: BoxDecoration(
          color: destructive
              ? Theme.of(context).colorScheme.errorContainer
              : SpinaTheme.brandPinkSoft,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Icon(icon, color: foreground),
      ),
      title: Text(title),
      subtitle: Text(subtitle),
      trailing: const Icon(Icons.chevron_right_rounded),
      onTap: onTap,
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

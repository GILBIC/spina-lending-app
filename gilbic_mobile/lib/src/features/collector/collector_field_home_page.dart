import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/account/account_settings_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_master_review_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_remittance_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_synthetic_review_page.dart';
import 'package:gilbic_mobile/src/features/collector/cross_collector_remittance_page.dart';
import 'package:gilbic_mobile/src/features/collector/other_area_collection_page.dart';
import 'package:gilbic_mobile/src/features/notifications/activity_notifications_page.dart';
import 'package:gilbic_mobile/src/features/notifications/remittance_notifications_page.dart';
import 'package:gilbic_mobile/src/features/offline/mobile_offline_policy_page.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

/// Collector-first shell for CA4.
///
/// The Management-approved Daily Collection ledger is the primary screen after sign-in.
/// Master Review is a first-class field action; secondary tools remain behind More.
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
  Future<void> _open(Widget page) async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(builder: (_) => page),
    );
  }

  void _permissionMessage(String feature) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'Your current SPINA access does not allow $feature.',
        ),
      ),
    );
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
                if (kDebugMode)
                  _CollectorToolTile(
                    key: const Key('collector-more-ca4-review'),
                    icon: Icons.fact_check_outlined,
                    title: 'CA4 synthetic field review',
                    subtitle:
                        'Review sample catch-up, notes, GCash and split states',
                    onTap: () {
                      Navigator.pop(sheetContext);
                      _open(const CollectorSyntheticReviewPage());
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
                    title: 'Assigned collector remittance',
                    subtitle: 'Send other-area payments to the route owner',
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
                  subtitle: 'End this SPINA session on the device',
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
      body: CollectorRoutePage(
        session: widget.session,
        loader: widget.collectorRouteLoader,
        paymentRepository: widget.paymentSubmissionRepository,
        deviceIdentityProvider: widget.deviceIdentityProvider,
        deviceSequence: widget.collectionDeviceSequence,
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

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/notifications/activity_notification_repository.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification_repository.dart';
import 'package:gilbic_mobile/src/features/notifications/activity_notifications_page.dart';
import 'package:gilbic_mobile/src/features/notifications/remittance_notifications_page.dart';

class NotificationCenterPage extends StatelessWidget {
  const NotificationCenterPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.activityRepository,
    this.remittanceRepository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ActivityNotificationRepository? activityRepository;
  final RemittanceNotificationRepository? remittanceRepository;

  void _push(BuildContext context, Widget page) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (context) => page),
    );
  }

  @override
  Widget build(BuildContext context) {
    final canViewRemittance = session.hasPermission('remittance.view');
    final canReceiveRemittance = session.hasPermission('remittance.receive');

    return Scaffold(
      appBar: AppBar(title: const Text('Notifications')),
      body: SafeArea(
        child: ListView(
          key: const Key('notification-center-page'),
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              'Updates for ${session.displayName}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 6),
            const Text(
              'Notification data is loaded for this signed-in account and registered device only.',
            ),
            const SizedBox(height: 18),
            Card(
              child: ListTile(
                key: const Key('open-activity-notifications'),
                leading: const Icon(Icons.notifications_active_outlined),
                title: const Text('Activity updates'),
                subtitle: const Text(
                  'Payments, custody changes, approvals, and other SPINA activity addressed to your account.',
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => _push(
                  context,
                  ActivityNotificationsPage(
                    session: session,
                    deviceIdentityProvider: deviceIdentityProvider,
                    repository: activityRepository,
                  ),
                ),
              ),
            ),
            if (canViewRemittance) ...[
              const SizedBox(height: 10),
              Card(
                child: ListTile(
                  key: const Key('open-remittance-notifications'),
                  leading: const Icon(Icons.account_balance_wallet_outlined),
                  title: const Text('Remittance custody'),
                  subtitle: Text(
                    canReceiveRemittance
                        ? 'Review assigned remittances and accept custody only after physical cash receipt.'
                        : 'Review assigned remittance status. Your current server permissions do not allow custody acceptance.',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => _push(
                    context,
                    RemittanceNotificationsPage(
                      session: session,
                      deviceIdentityProvider: deviceIdentityProvider,
                      repository: remittanceRepository,
                    ),
                  ),
                ),
              ),
            ],
            const SizedBox(height: 18),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.security_outlined),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        'Opening a notification never grants authority. Protected actions are rechecked by the SPINA server using your current account, device, role, and permissions.',
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

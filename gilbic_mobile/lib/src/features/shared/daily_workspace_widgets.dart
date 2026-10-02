import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/features/account/account_settings_page.dart';
import 'package:gilbic_mobile/src/features/notifications/notification_center_page.dart';
import 'package:gilbic_mobile/src/features/offline/mobile_offline_policy_page.dart';

/// Stateless read recovery; it never owns or retries a financial command.
class WorkspaceReadNotice extends StatelessWidget {
  const WorkspaceReadNotice({
    required this.message,
    required this.actionLabel,
    this.onAction,
    this.stale = false,
    super.key,
  });
  final String message;
  final String actionLabel;
  final VoidCallback? onAction;
  final bool stale;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (stale)
            const Text(
              'Showing the last successful information. It has not been refreshed.',
            ),
          Text(message),
          const SizedBox(height: 10),
          if (onAction != null)
            OutlinedButton(onPressed: onAction, child: Text(actionLabel))
          else
            Text(actionLabel, style: Theme.of(context).textTheme.titleSmall),
        ],
      ),
    ),
  );
}

/// Keeps forms and task lists readable on tablets without narrowing phones.
class WorkspaceBody extends StatelessWidget {
  const WorkspaceBody({required this.child, this.maxWidth = 960, super.key});
  final Widget child;
  final double maxWidth;

  @override
  Widget build(BuildContext context) => Align(
    alignment: Alignment.topCenter,
    child: ConstrainedBox(
      constraints: BoxConstraints(maxWidth: maxWidth),
      child: SizedBox(width: double.infinity, child: child),
    ),
  );
}

/// Secondary actions share one labelled entry point across daily workspaces.
class WorkspaceAccountMenu extends StatelessWidget {
  const WorkspaceAccountMenu({
    required this.session,
    required this.deviceIdentityProvider,
    required this.onSignOut,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final Future<void> Function() onSignOut;

  @override
  Widget build(BuildContext context) => PopupMenuButton<String>(
    tooltip: 'Account & tools',
    icon: const Icon(Icons.account_circle_outlined),
    onSelected: (value) {
      if (value == 'signOut') {
        onSignOut();
        return;
      }
      final page = switch (value) {
        'account' => AccountSettingsPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
          onSignOut: onSignOut,
        ),
        'notifications' => NotificationCenterPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
        _ => MobileOfflinePolicyPage(session: session),
      };
      Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => page));
    },
    itemBuilder: (_) => const [
      PopupMenuItem(value: 'account', child: Text('Profile & security')),
      PopupMenuItem(value: 'notifications', child: Text('Notifications')),
      PopupMenuItem(value: 'offline', child: Text('Offline & sync')),
      PopupMenuDivider(),
      PopupMenuItem(value: 'signOut', child: Text('Sign out')),
    ],
  );
}

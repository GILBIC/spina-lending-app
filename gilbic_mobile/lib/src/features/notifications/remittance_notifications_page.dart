import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification_repository.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_repository.dart';
import 'package:gilbic_mobile/src/features/remittance/remittance_history_page.dart';
import 'package:gilbic_mobile/src/features/remittance/remittance_photo_viewer_page.dart';

class RemittanceNotificationsPage extends StatefulWidget {
  const RemittanceNotificationsPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.remittanceRepository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final RemittanceNotificationRepository? repository;
  final RemittanceRepository? remittanceRepository;

  @override
  State<RemittanceNotificationsPage> createState() =>
      _RemittanceNotificationsPageState();
}

class _RemittanceNotificationsPageState
    extends State<RemittanceNotificationsPage> {
  late final RemittanceNotificationRepository _repository;
  List<RemittanceNotification> _notifications =
      const <RemittanceNotification>[];
  String? _deviceId;
  String? _errorMessage;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _repository =
        widget.repository ?? SpinaRemittanceNotificationRepository();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final notifications = await _repository.loadNotifications(
        widget.session,
        deviceId: identity.installationId,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _deviceId = identity.installationId;
        _notifications = notifications;
      });
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() {
          _errorMessage = 'Remittance notifications could not be loaded.';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _markRead(RemittanceNotification notification) async {
    final deviceId = _deviceId;
    if (deviceId == null || notification.readAt != null) {
      return;
    }
    try {
      final updated = await _repository.markRead(
        widget.session,
        deviceId: deviceId,
        notificationId: notification.notificationId,
      );
      if (mounted) {
        _replace(updated);
      }
    } on Object {
      // Reading is best-effort. Full remittance review still performs fresh
      // server-side recipient and custody checks before any financial action.
    }
  }

  Future<void> _openReview(RemittanceNotification notification) async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (context) => RemittanceHistoryPage(
          session: widget.session,
          deviceIdentityProvider: widget.deviceIdentityProvider,
          repository: widget.remittanceRepository,
          focusRemittanceId: notification.remittanceId,
        ),
      ),
    );
    if (mounted) {
      await _load();
    }
  }

  void _replace(RemittanceNotification updated) {
    setState(() {
      _notifications = _notifications
          .map(
            (item) => item.notificationId == updated.notificationId
                ? updated
                : item,
          )
          .toList(growable: false)
        ..sort((left, right) {
          if (left.isPending != right.isPending) {
            return left.isPending ? -1 : 1;
          }
          final leftDate = left.createdAt ?? DateTime.fromMillisecondsSinceEpoch(0);
          final rightDate =
              right.createdAt ?? DateTime.fromMillisecondsSinceEpoch(0);
          return rightDate.compareTo(leftDate);
        });
    });
  }

  @override
  Widget build(BuildContext context) {
    final pendingCount =
        _notifications.where((notification) => notification.isPending).length;
    final canReceiveRemittance =
        widget.session.hasPermission('remittance.receive');
    return Scaffold(
      appBar: AppBar(
        title: Text(
          pendingCount > 0
              ? 'Notifications ($pendingCount)'
              : 'Notifications',
        ),
        actions: [
          IconButton(
            tooltip: 'Refresh notifications',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: _loading && _notifications.isEmpty
            ? const Center(child: CircularProgressIndicator())
            : RefreshIndicator(
                onRefresh: _load,
                child: ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.all(14),
                  children: [
                    if (_errorMessage != null)
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Text(_errorMessage!),
                        ),
                      ),
                    if (_notifications.isEmpty)
                      const Padding(
                        padding: EdgeInsets.all(28),
                        child: Text(
                          'No remittance notifications yet.',
                          textAlign: TextAlign.center,
                        ),
                      )
                    else
                      for (final notification in _notifications)
                        _NotificationCard(
                          notification: notification,
                          session: widget.session,
                          deviceIdentityProvider: widget.deviceIdentityProvider,
                          canReceiveRemittance: canReceiveRemittance,
                          onOpened: () => _markRead(notification),
                          onReview: () => _openReview(notification),
                        ),
                  ],
                ),
              ),
      ),
    );
  }
}

class _NotificationCard extends StatelessWidget {
  const _NotificationCard({
    required this.notification,
    required this.session,
    required this.deviceIdentityProvider,
    required this.canReceiveRemittance,
    required this.onOpened,
    required this.onReview,
  });

  final RemittanceNotification notification;
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final bool canReceiveRemittance;
  final VoidCallback onOpened;
  final VoidCallback onReview;

  Future<void> _openPhoto(BuildContext context) async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (context) => RemittancePhotoViewerPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
          remittanceId: notification.remittanceId,
          remittanceNumber: notification.remittanceNumber,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final stateText = notification.isPending
        ? 'Action required — review full handover'
        : notification.isRejected
            ? 'Rejected — cash stayed with sender'
            : 'Accepted — money under your custody';
    final stateIcon = notification.isPending
        ? Icons.notifications_active
        : notification.isRejected
            ? Icons.cancel_outlined
            : Icons.verified;

    return Card(
      child: ExpansionTile(
        key: Key('notification-${notification.notificationId}'),
        onExpansionChanged: (expanded) {
          if (expanded) {
            onOpened();
          }
        },
        leading: Icon(stateIcon),
        title: Row(
          children: [
            Expanded(child: Text(notification.title)),
            if (notification.readAt == null)
              const Chip(label: Text('New')),
          ],
        ),
        subtitle: Text(
          '${notification.collectorName} • '
          '${_money(notification.totalAmount)}\n$stateText',
        ),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        children: [
          Align(
            alignment: Alignment.centerLeft,
            child: Text(notification.message),
          ),
          const SizedBox(height: 10),
          Align(
            alignment: Alignment.centerLeft,
            child: Text(
              '${notification.clientCount} clients • '
              '${notification.transactionCount} entries • '
              '${_date(notification.collectionDate)}',
            ),
          ),
          const SizedBox(height: 12),
          if (notification.hasHandoverPhoto) ...[
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                key: Key(
                  'view-handover-photo-${notification.notificationId}',
                ),
                onPressed: () => _openPhoto(context),
                icon: const Icon(Icons.photo_outlined),
                label: Text(
                  'View Handover Photo (v${notification.handoverPhotoVersion})',
                ),
              ),
            ),
            const SizedBox(height: 8),
          ] else ...[
            const Align(
              alignment: Alignment.centerLeft,
              child: Text('No handover photo was attached.'),
            ),
            const SizedBox(height: 8),
          ],
          if (notification.isRejected && notification.rejectionReason.isNotEmpty) ...[
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'Reason: ${notification.rejectionReason}',
                style: Theme.of(context).textTheme.titleSmall,
              ),
            ),
            const SizedBox(height: 8),
          ],
          if (notification.custodyMessage.trim().isNotEmpty) ...[
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                notification.custodyMessage,
                style: Theme.of(context).textTheme.titleSmall,
              ),
            ),
            const SizedBox(height: 8),
          ],
          if (notification.isPending && canReceiveRemittance)
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                key: Key(
                  'review-remittance-notification-${notification.notificationId}',
                ),
                onPressed: onReview,
                icon: const Icon(Icons.receipt_long_outlined),
                label: const Text('Review full remittance'),
              ),
            )
          else if (notification.isPending)
            const Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'View only — your current server permissions do not allow remittance acceptance.',
              ),
            )
          else
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                key: Key(
                  'open-remittance-history-${notification.notificationId}',
                ),
                onPressed: onReview,
                icon: const Icon(Icons.history),
                label: const Text('Open saved handover'),
              ),
            ),
        ],
      ),
    );
  }
}

String _date(DateTime? value) {
  if (value == null) {
    return 'Collection date unavailable';
  }
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}

String _money(double value) => '₱${value.toStringAsFixed(2)}';

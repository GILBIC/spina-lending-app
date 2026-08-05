import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification_repository.dart';
import 'package:gilbic_mobile/src/features/remittance/remittance_photo_viewer_page.dart';

class RemittanceNotificationsPage extends StatefulWidget {
  const RemittanceNotificationsPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final RemittanceNotificationRepository? repository;

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
  String? _acceptingId;
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
      // Reading the notification is best-effort. Acceptance still performs a
      // fresh server-side ownership and custody check.
    }
  }

  Future<void> _accept(RemittanceNotification notification) async {
    final deviceId = _deviceId;
    if (deviceId == null || _acceptingId != null || !notification.isPending) {
      return;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Accept Remittance?'),
        content: Text(
          'Collector: ${notification.collectorName}\n'
          'Amount: ${_money(notification.totalAmount)}\n'
          'Remittance: ${notification.remittanceNumber}\n\n'
          '${notification.hasHandoverPhoto ? 'A handover photo is attached for review.\n\n' : ''}'
          'Accept only after the cash is physically in your possession. '
          'After acceptance, the system records that this money is now under your custody.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Not received yet'),
          ),
          FilledButton(
            key: Key('accept-remittance-${notification.notificationId}'),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Accept Remittance'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) {
      return;
    }

    setState(() {
      _acceptingId = notification.notificationId;
      _errorMessage = null;
    });
    try {
      final result = await _repository.acceptRemittance(
        widget.session,
        deviceId: deviceId,
        notificationId: notification.notificationId,
      );
      if (!mounted) {
        return;
      }
      _replace(result.notification);
      await showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Remittance Accepted'),
          content: Text(
            '${result.remittanceNumber}\n'
            '${_money(notification.totalAmount)}\n\n'
            '${result.custodyMessage}',
          ),
          actions: [
            FilledButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Done'),
            ),
          ],
        ),
      );
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() {
          _errorMessage = 'The remittance could not be accepted.';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _acceptingId = null);
      }
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
                          accepting:
                              _acceptingId == notification.notificationId,
                          onOpened: () => _markRead(notification),
                          onAccept: () => _accept(notification),
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
    required this.accepting,
    required this.onOpened,
    required this.onAccept,
  });

  final RemittanceNotification notification;
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final bool accepting;
  final VoidCallback onOpened;
  final VoidCallback onAccept;

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
    return Card(
      child: ExpansionTile(
        key: Key('notification-${notification.notificationId}'),
        onExpansionChanged: (expanded) {
          if (expanded) {
            onOpened();
          }
        },
        leading: Icon(
          notification.isPending
              ? Icons.notifications_active
              : Icons.verified,
        ),
        title: Row(
          children: [
            Expanded(child: Text(notification.title)),
            if (notification.readAt == null)
              const Chip(label: Text('New')),
          ],
        ),
        subtitle: Text(
          '${notification.collectorName} • '
          '${_money(notification.totalAmount)}\n'
          '${notification.isPending ? 'Action required' : 'Accepted — money under your custody'}',
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
          if (notification.isPending)
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                key: Key(
                  'open-accept-remittance-${notification.notificationId}',
                ),
                onPressed: accepting ? null : onAccept,
                icon: accepting
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.payments_outlined),
                label: Text(
                  accepting ? 'Accepting...' : 'Accept Remittance',
                ),
              ),
            )
          else
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                notification.custodyMessage,
                style: Theme.of(context).textTheme.titleSmall,
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

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/notifications/activity_notification.dart';
import 'package:gilbic_mobile/src/core/notifications/activity_notification_repository.dart';

class ActivityNotificationsPage extends StatefulWidget {
  const ActivityNotificationsPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ActivityNotificationRepository? repository;

  @override
  State<ActivityNotificationsPage> createState() =>
      _ActivityNotificationsPageState();
}

class _ActivityNotificationsPageState
    extends State<ActivityNotificationsPage> {
  late final ActivityNotificationRepository _repository;

  List<ActivityNotification> _notifications = const <ActivityNotification>[];
  String? _deviceId;
  String? _errorMessage;
  bool _loading = true;
  final Set<String> _expanded = <String>{};
  final Set<String> _updating = <String>{};

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaActivityNotificationRepository();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final notifications = await _repository.load(
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
        setState(() => _errorMessage = 'Payment updates could not be loaded.');
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _toggle(ActivityNotification notification) async {
    setState(() {
      if (!_expanded.add(notification.id)) {
        _expanded.remove(notification.id);
      }
    });
    if (notification.isRead || _updating.contains(notification.id)) {
      return;
    }
    final deviceId = _deviceId;
    if (deviceId == null) {
      return;
    }
    setState(() => _updating.add(notification.id));
    try {
      final updated = await _repository.markRead(
        widget.session,
        deviceId: deviceId,
        notificationId: notification.id,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _notifications = _notifications
            .map((item) => item.id == updated.id ? updated : item)
            .toList(growable: false);
      });
    } on Object {
      // The update remains visible even if the read receipt cannot be saved.
    } finally {
      if (mounted) {
        setState(() => _updating.remove(notification.id));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Payment Updates'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(child: _buildBody(context)),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_loading && _notifications.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_errorMessage != null && _notifications.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.notifications_off_outlined, size: 48),
              const SizedBox(height: 12),
              Text(_errorMessage!, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: _load,
                icon: const Icon(Icons.refresh),
                label: const Text('Try again'),
              ),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
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
              padding: EdgeInsets.all(32),
              child: Text(
                'No payment updates yet.',
                textAlign: TextAlign.center,
              ),
            )
          else
            for (final notification in _notifications) ...[
              _ActivityCard(
                notification: notification,
                expanded: _expanded.contains(notification.id),
                updating: _updating.contains(notification.id),
                onTap: () => _toggle(notification),
              ),
              const SizedBox(height: 8),
            ],
        ],
      ),
    );
  }
}

class _ActivityCard extends StatelessWidget {
  const _ActivityCard({
    required this.notification,
    required this.expanded,
    required this.updating,
    required this.onTap,
  });

  final ActivityNotification notification;
  final bool expanded;
  final bool updating;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      color: notification.isRead ? null : scheme.primaryContainer,
      child: InkWell(
        key: Key('activity-notification-${notification.id}'),
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(_iconFor(notification.type)),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          notification.title,
                          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                fontWeight: notification.isRead
                                    ? FontWeight.w600
                                    : FontWeight.w900,
                              ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '${notification.senderName} • '
                          '${_dateTime(notification.createdAt)}',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                  if (updating)
                    const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  else
                    Icon(expanded ? Icons.expand_less : Icons.expand_more),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                notification.message,
                maxLines: expanded ? null : 2,
                overflow: expanded ? null : TextOverflow.ellipsis,
              ),
              if (expanded) ...[
                const Divider(height: 22),
                if (notification.receiptNumber.isNotEmpty)
                  Text('Receipt: ${notification.receiptNumber}'),
                if (notification.remittanceNumber.isNotEmpty)
                  Text('Remittance: ${notification.remittanceNumber}'),
                if (notification.amount.isNotEmpty)
                  Text('Amount: ₱${notification.amount}'),
                if (notification.custodyName.isNotEmpty)
                  Text('Cash custody: ${notification.custodyName}'),
                Text('Status: ${_statusLabel(notification.type)}'),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

IconData _iconFor(String type) {
  if (type.contains('accepted')) {
    return Icons.verified_outlined;
  }
  if (type.contains('remitted')) {
    return Icons.outbox_outlined;
  }
  return Icons.receipt_long_outlined;
}

String _statusLabel(String type) {
  if (type.contains('accepted')) {
    return 'Remittance accepted';
  }
  if (type.contains('remitted')) {
    return 'Awaiting recipient acceptance';
  }
  return 'Payment posted';
}

String _dateTime(DateTime? value) {
  if (value == null) {
    return 'Unknown time';
  }
  final local = value.toLocal();
  return '${local.year.toString().padLeft(4, '0')}-'
      '${local.month.toString().padLeft(2, '0')}-'
      '${local.day.toString().padLeft(2, '0')} '
      '${local.hour.toString().padLeft(2, '0')}:'
      '${local.minute.toString().padLeft(2, '0')}';
}

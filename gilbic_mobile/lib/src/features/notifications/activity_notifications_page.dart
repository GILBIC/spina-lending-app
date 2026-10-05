import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/notifications/activity_notification.dart';
import 'package:gilbic_mobile/src/core/notifications/activity_notification_repository.dart';
import 'package:gilbic_mobile/src/core/time/spina_business_time.dart';
import 'package:gilbic_mobile/src/features/shared/daily_workspace_widgets.dart';

class ActivityNotificationsPage extends StatefulWidget {
  const ActivityNotificationsPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.onSignOut,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ActivityNotificationRepository? repository;
  final Future<void> Function()? onSignOut;

  @override
  State<ActivityNotificationsPage> createState() =>
      _ActivityNotificationsPageState();
}

class _ActivityNotificationsPageState extends State<ActivityNotificationsPage> {
  late ActivityNotificationRepository _repository;

  List<ActivityNotification> _notifications = const <ActivityNotification>[];
  String? _deviceId;
  String? _errorMessage;
  bool _loading = false;
  bool _hasLoaded = false;
  int _generation = 0;
  int? _failureStatus;
  bool get _denied =>
      _failureStatus == 401 || _failureStatus == 403 || _failureStatus == 426;
  bool _current(int generation) => mounted && generation == _generation;
  final Set<String> _expanded = <String>{};
  final Set<String> _updating = <String>{};

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaActivityNotificationRepository();
    _load();
  }

  @override
  void didUpdateWidget(ActivityNotificationsPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.session != widget.session ||
        oldWidget.deviceIdentityProvider != widget.deviceIdentityProvider ||
        oldWidget.repository != widget.repository) {
      _generation++;
      _notifications = const [];
      _deviceId = null;
      _expanded.clear();
      _updating.clear();
      _hasLoaded = false;
      _loading = false;
      _failureStatus = null;
      _repository = widget.repository ?? SpinaActivityNotificationRepository();
      _load();
    }
  }

  @override
  void dispose() {
    _generation++;
    super.dispose();
  }

  void _failedRead(Object error, int generation) {
    if (!_current(generation)) return;
    setState(() {
      _failureStatus = error is SpinaApiException ? error.statusCode : null;
      _errorMessage = _failureStatus == 401
          ? 'Your session has expired. Sign in again to view payment updates.'
          : _failureStatus == 403
          ? 'Payment update access is unavailable. Return to Account or contact SPINA for help.'
          : _failureStatus == 426
          ? 'SPINA must be updated before these records can be used. Return to sign-in to check app access.'
          : 'Payment updates could not be loaded. Check your connection and retry.';
      if (_denied) {
        _generation++;
        _notifications = const [];
        _deviceId = null;
        _expanded.clear();
        _updating.clear();
        _hasLoaded = false;
        _loading = false;
      }
    });
  }

  Widget _readNotice() => WorkspaceReadNotice(
    message: _errorMessage!,
    stale: _hasLoaded,
    actionLabel: _failureStatus == 401
        ? 'Sign in again'
        : _failureStatus == 403
        ? 'Access unavailable'
        : _failureStatus == 426
        ? 'Return to sign-in'
        : 'Retry',
    onAction: _failureStatus == 401 || _failureStatus == 426
        ? widget.onSignOut
        : _denied || _loading
        ? null
        : _load,
  );

  Future<void> _load() async {
    if (!mounted || _loading || _denied) return;
    final generation = _generation;
    final session = widget.session;
    final repository = _repository;
    final provider = widget.deviceIdentityProvider;
    setState(() {
      _loading = true;
      _errorMessage = null;
      _failureStatus = null;
    });
    try {
      final identity = await provider.load();
      if (!_current(generation)) return;
      final notifications = await repository.load(
        session,
        deviceId: identity.installationId,
      );
      if (!_current(generation)) {
        return;
      }
      setState(() {
        _deviceId = identity.installationId;
        _notifications = notifications;
        _hasLoaded = true;
      });
    } on Object catch (error) {
      _failedRead(error, generation);
    } finally {
      if (_current(generation)) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _toggle(ActivityNotification notification) async {
    if (!mounted || _denied || !_notifications.contains(notification)) return;
    final generation = _generation;
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
      if (!_current(generation) || !_notifications.contains(notification)) {
        return;
      }
      setState(() {
        _notifications = _notifications
            .map((item) => item.id == updated.id ? updated : item)
            .toList(growable: false);
      });
    } on SpinaApiException catch (error) {
      if (error.statusCode == 401 ||
          error.statusCode == 403 ||
          error.statusCode == 426) {
        _failedRead(error, generation);
      }
    } on Object {
      // The update remains visible even if the read receipt cannot be saved.
    } finally {
      if (_current(generation)) {
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
            onPressed: _loading || _denied ? null : _load,
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
        child: Padding(padding: const EdgeInsets.all(24), child: _readNotice()),
      );
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
        children: [
          if (_errorMessage != null) _readNotice(),
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
                          style: Theme.of(context).textTheme.titleSmall
                              ?.copyWith(
                                fontWeight: notification.isRead
                                    ? FontWeight.w600
                                    : FontWeight.w900,
                              ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '${notification.senderName} • '
                          '${formatSpinaBusinessDateTime(notification.createdAt)}',
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

import 'package:gilbic_mobile/src/core/treasury/treasury_repository.dart';
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification_repository.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_repository.dart';
import 'package:gilbic_mobile/src/features/remittance/remittance_history_page.dart';
import 'package:gilbic_mobile/src/features/remittance/remittance_photo_viewer_page.dart';
import 'package:gilbic_mobile/src/features/shared/daily_workspace_widgets.dart';

class RemittanceNotificationsPage extends StatefulWidget {
  const RemittanceNotificationsPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.remittanceRepository,
    this.surplusRepository,
    this.onSignOut,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final RemittanceNotificationRepository? repository;
  final RemittanceRepository? remittanceRepository;
  final CollectorSurplusRepository? surplusRepository;
  final Future<void> Function()? onSignOut;

  @override
  State<RemittanceNotificationsPage> createState() =>
      _RemittanceNotificationsPageState();
}

class _RemittanceNotificationsPageState
    extends State<RemittanceNotificationsPage> {
  late RemittanceNotificationRepository _repository;
  List<RemittanceNotification> _notifications =
      const <RemittanceNotification>[];
  String? _deviceId;
  String? _errorMessage;
  bool _loading = false;
  bool _hasLoaded = false;
  int _generation = 0;
  int? _failureStatus;
  final Set<String> _updating = {};
  bool get _denied =>
      _failureStatus == 401 || _failureStatus == 403 || _failureStatus == 426;
  bool _current(int generation) => mounted && generation == _generation;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaRemittanceNotificationRepository();
    _load();
  }

  @override
  void didUpdateWidget(RemittanceNotificationsPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.session != widget.session ||
        oldWidget.deviceIdentityProvider != widget.deviceIdentityProvider ||
        oldWidget.repository != widget.repository) {
      _generation++;
      _notifications = const [];
      _deviceId = null;
      _updating.clear();
      _hasLoaded = false;
      _loading = false;
      _failureStatus = null;
      _repository =
          widget.repository ?? SpinaRemittanceNotificationRepository();
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
          ? 'Your session has expired. Sign in again to view remittance requests.'
          : _failureStatus == 403
          ? 'Remittance request access is unavailable. Return to Account or contact SPINA for help.'
          : _failureStatus == 426
          ? 'SPINA must be updated before these records can be used. Return to sign-in to check app access.'
          : 'Remittance requests could not be loaded. Check your connection and retry.';
      if (_denied) {
        _generation++;
        _notifications = const [];
        _deviceId = null;
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
      final notifications = await repository.loadNotifications(
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

  Future<void> _markRead(RemittanceNotification notification) async {
    if (!mounted ||
        _denied ||
        !_notifications.contains(notification) ||
        _updating.contains(notification.notificationId)) {
      return;
    }
    final generation = _generation;
    final deviceId = _deviceId;
    if (deviceId == null || notification.readAt != null) {
      return;
    }
    _updating.add(notification.notificationId);
    try {
      final updated = await _repository.markRead(
        widget.session,
        deviceId: deviceId,
        notificationId: notification.notificationId,
      );
      if (_current(generation) && _notifications.contains(notification)) {
        _replace(updated);
      }
    } on SpinaApiException catch (error) {
      if (error.statusCode == 401 ||
          error.statusCode == 403 ||
          error.statusCode == 426) {
        _failedRead(error, generation);
      }
    } on Object {
      // Reading is best-effort. Full remittance review still performs fresh
      // server-side recipient and custody checks before any financial action.
    } finally {
      if (_current(generation)) _updating.remove(notification.notificationId);
    }
  }

  Future<void> _openReview(RemittanceNotification notification) async {
    if (!mounted || _denied || !_notifications.contains(notification)) return;
    final generation = _generation;
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (context) => RemittanceHistoryPage(
          session: widget.session,
          deviceIdentityProvider: widget.deviceIdentityProvider,
          repository: widget.remittanceRepository,
          surplusRepository: widget.surplusRepository,
          focusRemittanceId: notification.remittanceId,
        ),
      ),
    );
    if (_current(generation) && !_denied) {
      await _load();
    }
  }

  void _replace(RemittanceNotification updated) {
    setState(() {
      _notifications =
          _notifications
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
              final leftDate =
                  left.createdAt ?? DateTime.fromMillisecondsSinceEpoch(0);
              final rightDate =
                  right.createdAt ?? DateTime.fromMillisecondsSinceEpoch(0);
              return rightDate.compareTo(leftDate);
            });
    });
  }

  @override
  Widget build(BuildContext context) {
    final pendingCount = _notifications
        .where((notification) => notification.isPending)
        .length;
    final canReceiveRemittance = widget.session.hasPermission(
      'remittance.receive',
    );
    return Scaffold(
      appBar: AppBar(
        title: Text(
          pendingCount > 0
              ? 'Remittance requests ($pendingCount)'
              : 'Remittance requests',
        ),
        actions: [
          IconButton(
            tooltip: 'Refresh remittance requests',
            onPressed: _loading || _denied ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: _loading && _notifications.isEmpty
            ? const Center(child: CircularProgressIndicator())
            : !_hasLoaded && _errorMessage != null
            ? Center(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: _readNotice(),
                ),
              )
            : RefreshIndicator(
                onRefresh: _load,
                child: ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.all(14),
                  children: [
                    if (_errorMessage != null) _readNotice(),
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
                          isCurrent: () =>
                              mounted &&
                              !_denied &&
                              _notifications.contains(notification),
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
    required this.isCurrent,
    required this.onOpened,
    required this.onReview,
  });

  final RemittanceNotification notification;
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final bool canReceiveRemittance;
  final bool Function() isCurrent;
  final VoidCallback onOpened;
  final VoidCallback onReview;

  Future<void> _openPhoto(BuildContext context) async {
    if (!isCurrent()) return;
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
        : notification.normalizedStatus == 'accepted'
        ? 'Accepted — money under your custody'
        : 'Status unavailable — ${notification.status}';
    final stateIcon = notification.isPending
        ? Icons.notifications_active
        : notification.isRejected
        ? Icons.cancel_outlined
        : notification.normalizedStatus == 'accepted'
        ? Icons.verified
        : Icons.info_outline;

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
            if (notification.readAt == null) const Chip(label: Text('New')),
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
                key: Key('view-handover-photo-${notification.notificationId}'),
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
          if (notification.isRejected &&
              notification.rejectionReason.isNotEmpty) ...[
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

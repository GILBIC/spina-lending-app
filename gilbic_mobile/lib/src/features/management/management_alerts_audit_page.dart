import 'dart:async';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_alerts_audit.dart';
import 'package:gilbic_mobile/src/core/management/management_alerts_audit_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ManagementAlertsAuditPage extends StatefulWidget {
  const ManagementAlertsAuditPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.onOpenDestination,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ManagementAlertsAuditRepository? repository;
  final ValueChanged<ManagementAlertsAuditNavigation>? onOpenDestination;

  @override
  State<ManagementAlertsAuditPage> createState() =>
      _ManagementAlertsAuditPageState();
}

class _ManagementAlertsAuditPageState extends State<ManagementAlertsAuditPage> {
  late final ManagementAlertsAuditRepository _repository;
  ManagementAlertsAuditSnapshot? _snapshot;
  ManagementAlertsAuditDomain? _domain;
  String? _deviceId;
  Future<String>? _deviceIdLoad;
  String? _error;
  int? _statusCode;
  bool _loading = true;
  int _generation = 0;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaManagementAlertsAuditRepository();
    unawaited(_load());
  }

  @override
  void dispose() {
    _generation += 1;
    super.dispose();
  }

  Future<String> _loadDeviceId() {
    final cached = _deviceId;
    if (cached != null) return Future<String>.value(cached);
    return _deviceIdLoad ??= _loadAndCacheDeviceId();
  }

  Future<String> _loadAndCacheDeviceId() async {
    try {
      final identity = await widget.deviceIdentityProvider.load();
      _deviceId = identity.installationId;
      return identity.installationId;
    } finally {
      _deviceIdLoad = null;
    }
  }

  Future<void> _load() async {
    final generation = ++_generation;
    setState(() {
      _loading = true;
      _error = null;
      _statusCode = null;
    });
    try {
      final deviceId = await _loadDeviceId();
      final snapshot = await _repository.loadSnapshot(
        widget.session,
        deviceId: deviceId,
      );
      if (!mounted || generation != _generation) return;
      setState(() {
        _snapshot = snapshot;
        if (_domain != null && !snapshot.visibleDomains.contains(_domain)) {
          _domain = null;
        }
      });
    } on Object catch (error) {
      if (!mounted || generation != _generation) return;
      setState(() {
        _error = error is SpinaApiException
            ? error.message
            : 'Management alerts and audit could not be loaded.';
        _statusCode = error is SpinaApiException ? error.statusCode : null;
      });
    } finally {
      if (mounted && generation == _generation) {
        setState(() => _loading = false);
      }
    }
  }

  void _open(ManagementAlertsAuditNavigation destination) {
    final callback = widget.onOpenDestination;
    if (callback != null) {
      callback(destination);
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Open this item from its owning Management workflow.'),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final snapshot = _snapshot;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Alerts & Audit'),
        actions: [
          IconButton(
            key: const Key('management-alerts-audit-refresh'),
            tooltip: 'Refresh Alerts & Audit',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: snapshot == null
            ? _InitialState(
                loading: _loading,
                error: _error,
                statusCode: _statusCode,
                onRetry: _load,
              )
            : RefreshIndicator(
                onRefresh: _load,
                child: ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(12, 12, 12, 28),
                  children: [
                    const Text(
                      'Review authorized queues and permanent audit evidence. '
                      'Complete work in the owning Management screen.',
                    ),
                    const SizedBox(height: 10),
                    Material(
                      color: Theme.of(context).colorScheme.surfaceContainerLow,
                      borderRadius: BorderRadius.circular(12),
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Text(snapshot.notice),
                      ),
                    ),
                    if (_loading) ...[
                      const SizedBox(height: 8),
                      const LinearProgressIndicator(
                        key: Key('management-alerts-audit-loading'),
                      ),
                    ],
                    if (_error != null) ...[
                      const SizedBox(height: 8),
                      Material(
                        key: const Key('management-alerts-audit-refresh-error'),
                        color: Theme.of(context).colorScheme.errorContainer,
                        borderRadius: BorderRadius.circular(12),
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Text(
                            'Refresh failed. The last successful snapshot '
                            'remains visible. $_error',
                          ),
                        ),
                      ),
                    ],
                    const SizedBox(height: 12),
                    _PaymentUpdatesRow(
                      onTap: () =>
                          _open(ManagementAlertsAuditNavigation.paymentUpdates),
                    ),
                    const SizedBox(height: 16),
                    Text(
                      'Visible activity',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 6),
                    SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Row(
                        children: [
                          ChoiceChip(
                            key: const Key('management-alert-domain-all'),
                            label: const Text('All'),
                            selected: _domain == null,
                            onSelected: (_) => setState(() => _domain = null),
                          ),
                          for (final domain in snapshot.visibleDomains) ...[
                            const SizedBox(width: 6),
                            ChoiceChip(
                              key: Key(
                                'management-alert-domain-${domain.serverValue}',
                              ),
                              label: Text(domain.label),
                              selected: _domain == domain,
                              onSelected: (_) =>
                                  setState(() => _domain = domain),
                            ),
                          ],
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),
                    _AlertSection(
                      alerts: snapshot.alerts
                          .where(
                            (alert) =>
                                _domain == null || alert.domain == _domain,
                          )
                          .toList(growable: false),
                      onOpen: _open,
                    ),
                    const SizedBox(height: 18),
                    _EventSection(
                      events: snapshot.events
                          .where(
                            (event) =>
                                _domain == null || event.domain == _domain,
                          )
                          .toList(growable: false),
                      totalCount: snapshot.eventTotalCount,
                      windowDays: snapshot.windowDays,
                      onOpen: _open,
                    ),
                    const SizedBox(height: 12),
                    Text(
                      'Updated ${_timestamp(context, snapshot.generatedAt)}',
                      style: Theme.of(context).textTheme.bodySmall,
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
      ),
    );
  }
}

class _InitialState extends StatelessWidget {
  const _InitialState({
    required this.loading,
    required this.error,
    required this.statusCode,
    required this.onRetry,
  });

  final bool loading;
  final String? error;
  final int? statusCode;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return const Center(
        child: CircularProgressIndicator(
          key: Key('management-alerts-audit-initial-loading'),
        ),
      );
    }
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(24),
      children: [
        const Icon(Icons.lock_clock_outlined, size: 44),
        const SizedBox(height: 12),
        Text(
          'Alerts & Audit access unavailable',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 8),
        Text(
          error ?? 'Management alerts and audit could not be loaded.',
          textAlign: TextAlign.center,
        ),
        if (statusCode == 401 || statusCode == 403) ...[
          const SizedBox(height: 8),
          const Text(
            'Your server session, role, device, and permissions remain '
            'authoritative.',
            textAlign: TextAlign.center,
          ),
        ],
        const SizedBox(height: 16),
        FilledButton.icon(
          key: const Key('management-alerts-audit-retry'),
          onPressed: onRetry,
          icon: const Icon(Icons.refresh),
          label: const Text('Retry'),
        ),
      ],
    );
  }
}

class _PaymentUpdatesRow extends StatelessWidget {
  const _PaymentUpdatesRow({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      child: ListTile(
        key: const Key('management-alerts-payment-updates'),
        leading: const Icon(Icons.receipt_long_outlined),
        title: const Text('Payment Updates'),
        subtitle: const Text(
          'Open the existing payment and custody notification inbox.',
        ),
        trailing: const Icon(Icons.chevron_right),
        onTap: onTap,
      ),
    );
  }
}

class _AlertSection extends StatelessWidget {
  const _AlertSection({required this.alerts, required this.onOpen});

  final List<ManagementAlert> alerts;
  final ValueChanged<ManagementAlertsAuditNavigation> onOpen;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('Needs attention', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        if (alerts.isEmpty)
          const Card(
            margin: EdgeInsets.zero,
            child: Padding(
              padding: EdgeInsets.all(14),
              child: Text('No pending items in this authorized view.'),
            ),
          )
        else
          for (final alert in alerts) ...[
            Card(
              margin: EdgeInsets.zero,
              child: ListTile(
                key: Key('management-alert-${alert.code.serverValue}'),
                leading: _CountBadge(alert: alert),
                title: Text(alert.title),
                subtitle: alert.amount == null
                    ? Text(alert.domain.label)
                    : Text('${alert.domain.label} · PHP ${alert.amount}'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => onOpen(alert.navigation),
              ),
            ),
            const SizedBox(height: 6),
          ],
      ],
    );
  }
}

class _CountBadge extends StatelessWidget {
  const _CountBadge({required this.alert});

  final ManagementAlert alert;

  @override
  Widget build(BuildContext context) {
    final colors = _severityColors(context, alert.severity);
    return Container(
      width: 44,
      height: 44,
      alignment: Alignment.center,
      padding: const EdgeInsets.symmetric(horizontal: 8),
      decoration: BoxDecoration(
        color: colors.$1,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        '${alert.count}',
        style: Theme.of(
          context,
        ).textTheme.titleMedium?.copyWith(color: colors.$2),
      ),
    );
  }
}

class _EventSection extends StatelessWidget {
  const _EventSection({
    required this.events,
    required this.totalCount,
    required this.windowDays,
    required this.onOpen,
  });

  final List<ManagementAuditEvent> events;
  final int totalCount;
  final int windowDays;
  final ValueChanged<ManagementAlertsAuditNavigation> onOpen;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Recent audit activity',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 2),
        Text(
          '$totalCount authorized event${totalCount == 1 ? '' : 's'} '
          'in the last $windowDays days',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        const SizedBox(height: 8),
        if (events.isEmpty)
          const Card(
            margin: EdgeInsets.zero,
            child: Padding(
              padding: EdgeInsets.all(14),
              child: Text('No audit events in this authorized view.'),
            ),
          )
        else
          for (final event in events) ...[
            Card(
              margin: EdgeInsets.zero,
              child: InkWell(
                key: Key('management-audit-${event.eventKey}'),
                borderRadius: BorderRadius.circular(12),
                onTap: () => onOpen(event.navigation),
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(
                        _severityIcon(event.severity),
                        color: _severityColors(context, event.severity).$2,
                        size: 20,
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              event.title,
                              style: Theme.of(context).textTheme.titleSmall,
                            ),
                            const SizedBox(height: 2),
                            Text('${event.reference} · ${event.currentState}'),
                            if (event.sourceLabel != null)
                              Text(event.sourceLabel!),
                            Text(
                              _eventPeople(event),
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                            if (event.reason != null)
                              Text(
                                'Reason: ${event.reason}',
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            Text(
                              '${_date(event.businessDate)} · '
                              '${_timestamp(context, event.occurredAt)}',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
                        ),
                      ),
                      const Icon(Icons.chevron_right, size: 20),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(height: 6),
          ],
      ],
    );
  }
}

String _eventPeople(ManagementAuditEvent event) {
  final checker = event.checkerName;
  if (checker == null || checker == event.actorName) {
    return 'Actor: ${event.actorName}';
  }
  return 'Maker: ${event.actorName} · Checker: $checker';
}

(Color, Color) _severityColors(
  BuildContext context,
  ManagementAlertsAuditSeverity severity,
) {
  final scheme = Theme.of(context).colorScheme;
  return switch (severity) {
    ManagementAlertsAuditSeverity.info => (
      scheme.primaryContainer,
      scheme.onPrimaryContainer,
    ),
    ManagementAlertsAuditSeverity.review => (
      scheme.secondaryContainer,
      scheme.onSecondaryContainer,
    ),
    ManagementAlertsAuditSeverity.attention => (
      scheme.tertiaryContainer,
      scheme.onTertiaryContainer,
    ),
    ManagementAlertsAuditSeverity.critical => (
      scheme.errorContainer,
      scheme.onErrorContainer,
    ),
  };
}

IconData _severityIcon(ManagementAlertsAuditSeverity severity) {
  return switch (severity) {
    ManagementAlertsAuditSeverity.info => Icons.info_outline,
    ManagementAlertsAuditSeverity.review => Icons.rate_review_outlined,
    ManagementAlertsAuditSeverity.attention => Icons.warning_amber_outlined,
    ManagementAlertsAuditSeverity.critical => Icons.error_outline,
  };
}

String _date(DateTime value) =>
    '${value.year.toString().padLeft(4, '0')}-'
    '${value.month.toString().padLeft(2, '0')}-'
    '${value.day.toString().padLeft(2, '0')}';

String _timestamp(BuildContext context, DateTime value) {
  final local = value.toLocal();
  final time = TimeOfDay.fromDateTime(local).format(context);
  return '${_date(local)} $time';
}

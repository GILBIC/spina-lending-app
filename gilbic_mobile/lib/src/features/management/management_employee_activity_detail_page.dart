import 'dart:async';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_employee_activity.dart';
import 'package:gilbic_mobile/src/core/management/management_employee_activity_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_general_journal_launcher_page.dart';
import 'package:gilbic_mobile/src/features/management/management_support_requests_page.dart';
import 'package:gilbic_mobile/src/features/notifications/remittance_notifications_page.dart';

class ManagementEmployeeActivityDetailPage extends StatefulWidget {
  const ManagementEmployeeActivityDetailPage({
    required this.session,
    required this.deviceId,
    required this.repository,
    required this.employeeUserId,
    required this.employeeName,
    required this.dateFrom,
    required this.dateTo,
    this.deviceIdentityProvider,
    this.onOpenGeneralJournal,
    this.onOpenSupportRequests,
    this.onOpenRemittanceReview,
    super.key,
  });

  final UserSession session;
  final String deviceId;
  final ManagementEmployeeActivityRepository repository;
  final String employeeUserId;
  final String employeeName;
  final DateTime dateFrom;
  final DateTime dateTo;
  final DeviceIdentityProvider? deviceIdentityProvider;
  final ValueChanged<String>? onOpenGeneralJournal;
  final ValueChanged<String>? onOpenSupportRequests;
  final ValueChanged<String>? onOpenRemittanceReview;

  @override
  State<ManagementEmployeeActivityDetailPage> createState() =>
      _ManagementEmployeeActivityDetailPageState();
}

class _ManagementEmployeeActivityDetailPageState
    extends State<ManagementEmployeeActivityDetailPage> {
  ManagementEmployeeActivityTimeline? _timeline;
  ManagementEmployeeActivityDomain? _domain;
  bool _loading = true;
  String? _error;
  int? _statusCode;
  int _generation = 0;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  @override
  void dispose() {
    _generation += 1;
    super.dispose();
  }

  Future<void> _load() async {
    final generation = ++_generation;
    setState(() {
      _loading = true;
      _error = null;
      _statusCode = null;
    });
    try {
      final timeline = await widget.repository.loadTimeline(
        widget.session,
        deviceId: widget.deviceId,
        employeeUserId: widget.employeeUserId,
        dateFrom: widget.dateFrom,
        dateTo: widget.dateTo,
        domain: _domain,
      );
      if (!mounted || generation != _generation) return;
      setState(() => _timeline = timeline);
    } on Object catch (error) {
      if (!mounted || generation != _generation) return;
      setState(() {
        _error = error is SpinaApiException
            ? error.message
            : 'Employee Activity details could not be loaded.';
        _statusCode = error is SpinaApiException ? error.statusCode : null;
      });
    } finally {
      if (mounted && generation == _generation) {
        setState(() => _loading = false);
      }
    }
  }

  void _openItem(ManagementEmployeeActivityItem item) {
    final navigation = item.navigationCode;
    switch (navigation) {
      case ManagementEmployeeActivityNavigationCode.generalJournals:
        if (!widget.session.hasPermission('accounting.view')) {
          return _showUnavailable();
        }
        final callback = widget.onOpenGeneralJournal;
        if (callback != null) return callback(item.recordId);
        final identity = widget.deviceIdentityProvider;
        if (identity == null) return _showUnavailable();
        return _push(
          ManagementGeneralJournalLauncherPage(
            session: widget.session,
            deviceIdentityProvider: identity,
          ),
        );
      case ManagementEmployeeActivityNavigationCode.supportRequests:
        if (!widget.session.hasPermission('support.manage')) {
          return _showUnavailable();
        }
        final callback = widget.onOpenSupportRequests;
        if (callback != null) return callback(item.recordId);
        final identity = widget.deviceIdentityProvider;
        if (identity == null) return _showUnavailable();
        return _push(
          ManagementSupportRequestsPage(
            session: widget.session,
            deviceIdentityProvider: identity,
          ),
        );
      case ManagementEmployeeActivityNavigationCode.remittanceReview:
        if (!widget.session.hasPermission('remittance.view')) {
          return _showUnavailable();
        }
        final callback = widget.onOpenRemittanceReview;
        if (callback != null) return callback(item.recordId);
        final identity = widget.deviceIdentityProvider;
        if (identity == null) return _showUnavailable();
        return _push(
          RemittanceNotificationsPage(
            session: widget.session,
            deviceIdentityProvider: identity,
          ),
        );
      case null:
        _showUnavailable();
    }
  }

  void _push(Widget page) {
    Navigator.of(
      context,
    ).push(MaterialPageRoute<void>(builder: (context) => page));
  }

  void _showUnavailable() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Detailed review is unavailable for this item.'),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final timeline = _timeline;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Employee Activity'),
        actions: [
          IconButton(
            key: const Key('employee-activity-detail-refresh'),
            tooltip: 'Refresh Employee Activity',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
            children: [
              Text(
                timeline?.employeeName ?? widget.employeeName,
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 4),
              Text(
                '${_date(widget.dateFrom)} to ${_date(widget.dateTo)} · Read-only evidence',
              ),
              if (timeline != null && timeline.availableDomains.isNotEmpty) ...[
                const SizedBox(height: 14),
                DropdownButtonFormField<ManagementEmployeeActivityDomain?>(
                  key: const Key('employee-activity-detail-domain-filter'),
                  initialValue: _domain,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'Function'),
                  items: <DropdownMenuItem<ManagementEmployeeActivityDomain?>>[
                    const DropdownMenuItem<ManagementEmployeeActivityDomain?>(
                      value: null,
                      child: Text('All authorized functions'),
                    ),
                    for (final domain in timeline.availableDomains)
                      DropdownMenuItem<ManagementEmployeeActivityDomain?>(
                        value: domain,
                        child: Text(_domainLabel(domain)),
                      ),
                  ],
                  onChanged: _loading
                      ? null
                      : (value) {
                          setState(() => _domain = value);
                          unawaited(_load());
                        },
                ),
              ],
              if (_loading) ...[
                const SizedBox(height: 14),
                const LinearProgressIndicator(),
              ],
              const SizedBox(height: 14),
              if (_error != null && timeline == null)
                _DetailError(
                  message: _error!,
                  statusCode: _statusCode,
                  onRetry: _load,
                )
              else if (timeline != null && timeline.items.isEmpty)
                const Card(
                  child: Padding(
                    padding: EdgeInsets.all(20),
                    child: Text(
                      'No permitted activity in this range.',
                      textAlign: TextAlign.center,
                    ),
                  ),
                )
              else if (timeline != null)
                for (final item in timeline.items) ...[
                  _ActivityItemCard(item: item, onTap: () => _openItem(item)),
                  const SizedBox(height: 10),
                ],
            ],
          ),
        ),
      ),
    );
  }
}

class _ActivityItemCard extends StatelessWidget {
  const _ActivityItemCard({required this.item, required this.onTap});

  final ManagementEmployeeActivityItem item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: Key('employee-activity-item-${item.recordId}'),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(_domainIcon(item.domain), size: 22),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          item.summary,
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        Text(item.displayReference),
                      ],
                    ),
                  ),
                  const SizedBox(width: 6),
                  const Icon(Icons.chevron_right),
                ],
              ),
              const SizedBox(height: 10),
              Text(
                '${_dateTime(item.occurredAt)} · ${_domainLabel(item.domain)}',
              ),
              Text(
                'State: ${_plain(item.workflowState)} · ${_statusLabel(item.status)}',
              ),
              if (item.makerName != null) Text('Maker: ${item.makerName}'),
              if (item.checkerName != null)
                Text('Checker: ${item.checkerName}'),
            ],
          ),
        ),
      ),
    );
  }
}

class _DetailError extends StatelessWidget {
  const _DetailError({
    required this.message,
    required this.statusCode,
    required this.onRetry,
  });

  final String message;
  final int? statusCode;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: Theme.of(context).colorScheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            Text(
              statusCode == 403
                  ? 'Employee Activity access unavailable'
                  : 'Employee Activity details unavailable',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Try again'),
            ),
          ],
        ),
      ),
    );
  }
}

String _domainLabel(ManagementEmployeeActivityDomain domain) {
  return switch (domain) {
    ManagementEmployeeActivityDomain.accounting => 'Accounting',
    ManagementEmployeeActivityDomain.hr => 'HR',
    ManagementEmployeeActivityDomain.payroll => 'Payroll',
    ManagementEmployeeActivityDomain.crmSupport => 'Client support',
    ManagementEmployeeActivityDomain.remittanceOperations =>
      'Remittance operations',
    ManagementEmployeeActivityDomain.administration => 'Administration',
  };
}

IconData _domainIcon(ManagementEmployeeActivityDomain domain) {
  return switch (domain) {
    ManagementEmployeeActivityDomain.accounting =>
      Icons.account_balance_outlined,
    ManagementEmployeeActivityDomain.hr => Icons.badge_outlined,
    ManagementEmployeeActivityDomain.payroll => Icons.payments_outlined,
    ManagementEmployeeActivityDomain.crmSupport => Icons.support_agent,
    ManagementEmployeeActivityDomain.remittanceOperations =>
      Icons.move_to_inbox_outlined,
    ManagementEmployeeActivityDomain.administration =>
      Icons.admin_panel_settings_outlined,
  };
}

String _statusLabel(ManagementEmployeeActivityStatus status) {
  return switch (status) {
    ManagementEmployeeActivityStatus.noActivity => 'No permitted activity',
    ManagementEmployeeActivityStatus.inProgress => 'In progress',
    ManagementEmployeeActivityStatus.awaitingReview => 'Awaiting Management',
    ManagementEmployeeActivityStatus.completed => 'Completed',
    ManagementEmployeeActivityStatus.needsAttention => 'Needs attention',
  };
}

String _plain(String value) {
  final normalized = value.replaceAll('_', ' ').trim();
  if (normalized.isEmpty) return value;
  return '${normalized[0].toUpperCase()}${normalized.substring(1)}';
}

String _date(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}

String _dateTime(DateTime value) {
  final local = value.toLocal();
  return '${_date(local)} '
      '${local.hour.toString().padLeft(2, '0')}:'
      '${local.minute.toString().padLeft(2, '0')}';
}

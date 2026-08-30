import 'dart:math';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/period_close.dart';
import 'package:gilbic_mobile/src/core/management/period_close_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

class ManagementPeriodClosePage extends StatefulWidget {
  const ManagementPeriodClosePage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.confirmationTokenGenerator,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final PeriodCloseRepository? repository;
  final String Function()? confirmationTokenGenerator;

  @override
  State<ManagementPeriodClosePage> createState() =>
      _ManagementPeriodClosePageState();
}

class _ManagementPeriodClosePageState extends State<ManagementPeriodClosePage> {
  late final PeriodCloseRepository _repository;
  late final String Function() _confirmationTokenGenerator;
  final Map<String, String> _confirmationTokens = <String, String>{};
  PeriodCloseOverview? _overview;
  String _filter = 'all';
  String? _error;
  bool _loading = true;
  String? _submittingPeriodId;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaPeriodCloseRepository();
    _confirmationTokenGenerator =
        widget.confirmationTokenGenerator ?? _newConfirmationToken;
    _load();
  }

  Future<void> _load({String? status}) async {
    final nextStatus = status ?? _filter;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final overview = await _repository.load(
        widget.session,
        deviceId: identity.installationId,
        status: nextStatus,
      );
      if (!mounted) return;
      setState(() {
        _filter = nextStatus;
        _overview = overview;
      });
    } on SpinaApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) {
        setState(
          () =>
              _error = 'The protected period-close queue could not be loaded.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _prepare(PeriodCloseItem item) async {
    final overview = _overview;
    if (overview == null || !_canPrepare(overview, item)) return;
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        surface: ManagementMutationSurface.periodClose,
        recordLabel: 'Fiscal period',
        recordValue: item.label,
        statusLabel: _statusLabel(item.closeStatus),
        facts: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Period start',
            value: periodCloseDateText(item.startDate),
          ),
          ManagementReviewFact(
            label: 'Period end',
            value: periodCloseDateText(item.endDate),
          ),
        ],
        warnings: const <ManagementReviewWarning>[
          ManagementReviewWarning(
            severity: ManagementReviewWarningSeverity.caution,
            message:
                'The server will freeze an exact close snapshot for separate posting review.',
          ),
        ],
        nextActionLabel: 'Prepare protected close',
        consequence:
            'The server will create an immutable preparation snapshot. No retained-earnings journal is posted and the period is not closed yet.',
        risk: ManagementReviewRisk.protectedFinancial,
      ),
    );
    if (!confirmed || !mounted) return;

    setState(() => _submittingPeriodId = item.fiscalPeriodId);
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final prepared = await _repository.prepare(
        widget.session,
        deviceId: identity.installationId,
        fiscalPeriodId: item.fiscalPeriodId,
      );
      if (!mounted) return;
      _replaceItem(prepared);
      _showMessage('Protected close prepared for final review.');
    } on SpinaApiException catch (error) {
      if (mounted) _showMessage(error.message);
    } on Object {
      if (mounted) _showMessage('The protected close could not be prepared.');
    } finally {
      if (mounted) setState(() => _submittingPeriodId = null);
    }
  }

  Future<void> _post(PeriodCloseItem item) async {
    final overview = _overview;
    if (overview == null || !_canPost(overview, item)) return;
    item.requirePostCoordinates();
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        surface: ManagementMutationSurface.periodClose,
        recordLabel: 'Fiscal period',
        recordValue: item.label,
        statusLabel: _statusLabel(item.closeStatus),
        facts: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Period end',
            value: periodCloseDateText(item.endDate),
          ),
          ManagementReviewFact(
            label: 'Net profit / loss',
            value: item.netIncome!,
          ),
          const ManagementReviewFact(
            label: 'Retained Earnings account',
            value: '3100',
          ),
          ManagementReviewFact(
            label: 'Balance before close',
            value: item.retainedEarningsBalanceBefore!,
          ),
          ManagementReviewFact(
            label: 'Temporary accounts',
            value: item.temporaryAccountCount!.toString(),
          ),
        ],
        warnings: const <ManagementReviewWarning>[
          ManagementReviewWarning(
            severity: ManagementReviewWarningSeverity.caution,
            message:
                'The close journal and audit evidence are permanent. Corrections require a separately authorized accounting process.',
          ),
        ],
        secondaryReferences: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Immutable journal reference',
            value: item.journalEntryId!,
          ),
          ManagementReviewFact(label: 'Close digest', value: item.closeDigest!),
        ],
        nextActionLabel: 'Post retained earnings & close',
        consequence:
            'The server will immutably post the retained-earnings close, close the fiscal period, and permanently audit this confirmation.',
        risk: ManagementReviewRisk.protectedFinancial,
      ),
    );
    if (!confirmed || !mounted) return;

    final tokenKey = '${item.fiscalPeriodId}:${item.closeDigest!}';
    final token = _confirmationTokens.putIfAbsent(
      tokenKey,
      _confirmationTokenGenerator,
    );
    setState(() => _submittingPeriodId = item.fiscalPeriodId);
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final closed = await _repository.post(
        widget.session,
        deviceId: identity.installationId,
        item: item,
        confirmationToken: token,
      );
      if (!mounted) return;
      _confirmationTokens.remove(tokenKey);
      _replaceItem(closed);
      _showMessage('Protected period close posted.');
    } on SpinaApiException catch (error) {
      if (mounted) _showMessage(error.message);
    } on Object {
      if (mounted) {
        _showMessage(
          'The close result is uncertain. Review the server state before retrying.',
        );
      }
    } finally {
      if (mounted) setState(() => _submittingPeriodId = null);
    }
  }

  void _replaceItem(PeriodCloseItem replacement) {
    final current = _overview;
    if (current == null) return;
    final items = current.items
        .map(
          (item) => item.fiscalPeriodId == replacement.fiscalPeriodId
              ? replacement
              : item,
        )
        .toList(growable: false);
    setState(
      () => _overview = PeriodCloseOverview(
        summary: current.summary,
        items: items,
        permissions: current.permissions,
        notice: current.notice,
      ),
    );
  }

  bool _canPrepare(PeriodCloseOverview overview, PeriodCloseItem item) {
    return item.closeStatus == 'ready_to_prepare' &&
        overview.permissions.closePrepare &&
        widget.session.hasPermission('accounting.period.close.prepare');
  }

  bool _canPost(PeriodCloseOverview overview, PeriodCloseItem item) {
    return item.isPrepared &&
        overview.permissions.closePost &&
        widget.session.hasPermission('accounting.period.close.post');
  }

  void _showMessage(String message) {
    final messenger = ScaffoldMessenger.of(context);
    messenger.clearSnackBars();
    messenger.showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Formal Period Close'),
        actions: <Widget>[
          IconButton(
            tooltip: 'Refresh period-close queue',
            onPressed: _loading || _submittingPeriodId != null
                ? null
                : () => _load(),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(child: _body()),
    );
  }

  Widget _body() {
    final overview = _overview;
    if (_loading && overview == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null && overview == null) {
      return _ErrorState(message: _error!, onRetry: _load);
    }
    if (overview == null) return const SizedBox.shrink();

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
        physics: const AlwaysScrollableScrollPhysics(),
        children: <Widget>[
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Text(overview.notice),
            ),
          ),
          const SizedBox(height: 12),
          _PeriodCloseSummaryCard(summary: overview.summary),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 6,
            children: _filters.entries
                .map(
                  (entry) => ChoiceChip(
                    label: Text(entry.value),
                    selected: _filter == entry.key,
                    onSelected: _submittingPeriodId == null
                        ? (_) => _load(status: entry.key)
                        : null,
                  ),
                )
                .toList(growable: false),
          ),
          const SizedBox(height: 12),
          if (overview.items.any(
                (item) => item.closeStatus == 'ready_to_prepare',
              ) &&
              !(overview.permissions.closePrepare &&
                  widget.session.hasPermission(
                    'accounting.period.close.prepare',
                  ))) ...<Widget>[
            const _PermissionNotice(
              message: 'Preparation permission is not assigned.',
            ),
            const SizedBox(height: 8),
          ],
          if (overview.items.any((item) => item.isPrepared) &&
              !(overview.permissions.closePost &&
                  widget.session.hasPermission(
                    'accounting.period.close.post',
                  ))) ...<Widget>[
            const _PermissionNotice(
              message: 'Posting permission is not assigned.',
            ),
            const SizedBox(height: 8),
          ],
          if (_error != null) ...<Widget>[
            Card(
              color: Theme.of(context).colorScheme.errorContainer,
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Text(_error!),
              ),
            ),
            const SizedBox(height: 12),
          ],
          if (overview.items.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(18),
                child: Text('No fiscal periods match this server filter.'),
              ),
            )
          else
            ...overview.items.map(
              (item) => _PeriodCloseCard(
                item: item,
                canPrepare: _canPrepare(overview, item),
                canPost: _canPost(overview, item),
                submitting: _submittingPeriodId == item.fiscalPeriodId,
                onPrepare: () => _prepare(item),
                onPost: () => _post(item),
              ),
            ),
        ],
      ),
    );
  }
}

class _PeriodCloseSummaryCard extends StatelessWidget {
  const _PeriodCloseSummaryCard({required this.summary});

  final PeriodCloseSummary summary;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: const Key('period-close-summary'),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Server summary',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 18,
              runSpacing: 8,
              children: <Widget>[
                _SummaryFact(label: 'Periods', value: summary.periodCount),
                _SummaryFact(
                  label: 'Ready to prepare',
                  value: summary.readyToPrepareCount,
                ),
                _SummaryFact(label: 'Prepared', value: summary.preparedCount),
                _SummaryFact(label: 'Blocked', value: summary.blockedCount),
                _SummaryFact(
                  label: 'Protected closed',
                  value: summary.protectedClosedCount,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _SummaryFact extends StatelessWidget {
  const _SummaryFact({required this.label, required this.value});

  final String label;
  final int value;

  @override
  Widget build(BuildContext context) {
    return Semantics(label: '$label: $value', child: Text('$label: $value'));
  }
}

class _PeriodCloseCard extends StatelessWidget {
  const _PeriodCloseCard({
    required this.item,
    required this.canPrepare,
    required this.canPost,
    required this.submitting,
    required this.onPrepare,
    required this.onPost,
  });

  final PeriodCloseItem item;
  final bool canPrepare;
  final bool canPost;
  final bool submitting;
  final VoidCallback onPrepare;
  final VoidCallback onPost;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Text(item.label, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 4),
            Text(
              '${periodCloseDateText(item.startDate)} to '
              '${periodCloseDateText(item.endDate)}',
            ),
            const SizedBox(height: 6),
            Text(_statusLabel(item.closeStatus)),
            if (item.closeBlocker != null) ...<Widget>[
              const SizedBox(height: 8),
              Text(
                item.closeBlocker!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ],
            if (item.netIncome != null) ...<Widget>[
              const SizedBox(height: 8),
              Text('Net profit / loss: ${item.netIncome}'),
              Text(
                'Retained Earnings before close: '
                '${item.retainedEarningsBalanceBefore}',
              ),
            ],
            if (item.closingEntryNumber != null) ...<Widget>[
              const SizedBox(height: 8),
              Text('Closing journal: ${item.closingEntryNumber}'),
              Text(
                'Retained Earnings after close: '
                '${item.retainedEarningsBalanceAfter}',
              ),
            ],
            if (item.closeStatus == 'ready_to_prepare') ...<Widget>[
              const SizedBox(height: 10),
              if (canPrepare)
                FilledButton.icon(
                  key: Key('prepare-period-${item.fiscalPeriodId}'),
                  onPressed: submitting ? null : onPrepare,
                  icon: const Icon(Icons.fact_check_outlined),
                  label: const Text('Prepare protected close'),
                ),
            ],
            if (item.isPrepared) ...<Widget>[
              const SizedBox(height: 10),
              if (canPost)
                FilledButton.icon(
                  key: Key('post-period-${item.fiscalPeriodId}'),
                  onPressed: submitting ? null : onPost,
                  icon: const Icon(Icons.lock_outline),
                  label: const Text('Post retained earnings & close'),
                ),
            ],
            if (submitting) ...<Widget>[
              const SizedBox(height: 8),
              const LinearProgressIndicator(),
            ],
          ],
        ),
      ),
    );
  }
}

class _PermissionNotice extends StatelessWidget {
  const _PermissionNotice({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: <Widget>[
            const Icon(Icons.lock_outline),
            const SizedBox(width: 10),
            Expanded(child: Text(message)),
          ],
        ),
      ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.message, required this.onRetry});

  final String message;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            const Icon(Icons.error_outline, size: 48),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
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

const _filters = <String, String>{
  'all': 'All',
  'ready_for_review': 'Open',
  'ready_to_prepare': 'Ready',
  'prepared': 'Prepared',
  'blocked': 'Blocked',
  'closed': 'Closed',
};

String _statusLabel(String status) {
  if (status.startsWith('blocked_')) return 'Blocked by server checks';
  return switch (status) {
    'ready_for_review' => 'Open — send to review first',
    'ready_to_prepare' => 'Ready to prepare',
    'prepared_confirmation_required' =>
      'Prepared — final confirmation required',
    'closed_protected' => 'Closed with protected evidence',
    'closed_legacy_without_protected_close_audit' =>
      'Legacy close — protected audit unavailable',
    _ => 'Status needs review',
  };
}

String _newConfirmationToken() {
  final random = Random.secure();
  return List<int>.generate(
    32,
    (_) => random.nextInt(256),
  ).map((value) => value.toRadixString(16).padLeft(2, '0')).join();
}

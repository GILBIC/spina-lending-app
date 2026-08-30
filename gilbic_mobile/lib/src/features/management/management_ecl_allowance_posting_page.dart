import 'dart:math';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/ecl_allowance_posting.dart';
import 'package:gilbic_mobile/src/core/management/ecl_allowance_posting_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

class ManagementEclAllowancePostingPage extends StatefulWidget {
  const ManagementEclAllowancePostingPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.reviewTokenGenerator,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final EclAllowancePostingRepository? repository;
  final String Function()? reviewTokenGenerator;

  @override
  State<ManagementEclAllowancePostingPage> createState() =>
      _ManagementEclAllowancePostingPageState();
}

class _ManagementEclAllowancePostingPageState
    extends State<ManagementEclAllowancePostingPage> {
  late final EclAllowancePostingRepository _repository;
  late final String Function() _reviewTokenGenerator;
  final Map<String, String> _tokens = <String, String>{};
  EclAllowancePostingOverview? _overview;
  String _filter = 'all';
  String? _error;
  String? _submittingLoanId;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaEclAllowancePostingRepository();
    _reviewTokenGenerator = widget.reviewTokenGenerator ?? _newToken;
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
        _overview = overview;
        _filter = nextStatus;
      });
    } on SpinaApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) {
        setState(
          () =>
              _error = 'The protected ECL allowance queue could not be loaded.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _prepare(EclAllowancePostingItem item) async {
    final overview = _overview;
    if (overview == null || !_canPrepare(overview, item)) return;
    item.requirePreparationCoordinates();
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        surface: ManagementMutationSurface.eclAllowance,
        recordLabel: 'Loan',
        recordValue: '${item.loanNumber} • ${item.loanTypeName}',
        statusLabel: _statusLabel(item.allowancePostingStatus),
        facts: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Measurement date',
            value: eclAllowanceDateText(item.measurementDate!),
          ),
          ManagementReviewFact(
            label: 'Authoritative ECL',
            value: item.authoritativeEclAmount!,
          ),
          ManagementReviewFact(
            label: 'Posting date',
            value: eclAllowanceDateText(item.postingDate!),
          ),
          const ManagementReviewFact(
            label: 'Debit account',
            value: '5000 Credit Loss Expense',
          ),
          const ManagementReviewFact(
            label: 'Credit account',
            value: '1190 ECL Allowance',
          ),
          ManagementReviewFact(
            label: 'Prior allowance',
            value: item.priorAllowanceBalance!,
          ),
        ],
        warnings: const <ManagementReviewWarning>[
          ManagementReviewWarning(
            severity: ManagementReviewWarningSeverity.caution,
            message:
                'The server will prepare a protected draft only. This action does not post the allowance.',
          ),
        ],
        secondaryReferences: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Calculation digest',
            value: item.calculationDigest!,
          ),
          ManagementReviewFact(
            label: 'Fiscal period ID',
            value: item.fiscalPeriodId!,
          ),
        ],
        nextActionLabel: 'Prepare allowance draft',
        consequence:
            'The backend will freeze an exact protected draft for separate posting review. No General Ledger balance changes yet.',
        risk: ManagementReviewRisk.protectedFinancial,
      ),
    );
    if (!confirmed || !mounted) return;
    final tokenKey = 'prepare:${item.measurementId}:${item.calculationDigest}';
    final token = _tokens.putIfAbsent(tokenKey, _reviewTokenGenerator);
    setState(() => _submittingLoanId = item.loanId);
    try {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.prepare(
        widget.session,
        deviceId: identity.installationId,
        item: item,
        reviewToken: token,
      );
      _tokens.remove(tokenKey);
      if (!mounted) return;
      _message('Initial ECL allowance draft prepared.');
      await _load();
    } on SpinaApiException catch (error) {
      if (mounted) _message(error.message);
    } on Object {
      if (mounted) {
        _message(
          'The preparation result is uncertain. Review the server state before retrying.',
        );
      }
    } finally {
      if (mounted) setState(() => _submittingLoanId = null);
    }
  }

  Future<void> _post(EclAllowancePostingItem item) async {
    final overview = _overview;
    if (overview == null || !_canPost(overview, item)) return;
    item.requirePostingCoordinates();
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        surface: ManagementMutationSurface.eclAllowance,
        recordLabel: 'Prepared allowance journal',
        recordValue: '${item.loanNumber} • ${item.sourceEventKey}',
        statusLabel: _statusLabel(item.allowancePostingStatus),
        facts: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Allowance amount',
            value: item.allowanceAmount!,
          ),
          const ManagementReviewFact(
            label: 'Credit Loss Expense',
            value: '5000',
          ),
          const ManagementReviewFact(label: 'ECL Allowance', value: '1190'),
          ManagementReviewFact(
            label: 'Prior allowance',
            value: item.priorAllowanceBalance!,
          ),
          ManagementReviewFact(
            label: 'Posting date',
            value: eclAllowanceDateText(item.postingDate!),
          ),
        ],
        warnings: const <ManagementReviewWarning>[
          ManagementReviewWarning(
            severity: ManagementReviewWarningSeverity.caution,
            message:
                'Posting is immutable. Later measurement changes require the separate protected A5 workflow.',
          ),
        ],
        secondaryReferences: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Journal entry ID',
            value: item.journalEntryId!,
          ),
          ManagementReviewFact(
            label: 'Preparation digest',
            value: item.preparationDigest!,
          ),
          ManagementReviewFact(
            label: 'Calculation digest',
            value: item.calculationDigest!,
          ),
        ],
        nextActionLabel: 'Post initial allowance',
        consequence:
            'The backend will immutably post the initial ECL allowance to the protected General Ledger and permanently audit this confirmation.',
        risk: ManagementReviewRisk.protectedFinancial,
      ),
    );
    if (!confirmed || !mounted) return;
    final tokenKey = 'post:${item.preparationId}:${item.preparationDigest}';
    final token = _tokens.putIfAbsent(tokenKey, _reviewTokenGenerator);
    setState(() => _submittingLoanId = item.loanId);
    try {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.post(
        widget.session,
        deviceId: identity.installationId,
        item: item,
        reviewToken: token,
      );
      _tokens.remove(tokenKey);
      if (!mounted) return;
      _message('Initial ECL allowance posted.');
      await _load();
    } on SpinaApiException catch (error) {
      if (mounted) _message(error.message);
    } on Object {
      if (mounted) {
        _message(
          'The posting result is uncertain. Review the server state before retrying.',
        );
      }
    } finally {
      if (mounted) setState(() => _submittingLoanId = null);
    }
  }

  bool _canPrepare(
    EclAllowancePostingOverview overview,
    EclAllowancePostingItem item,
  ) {
    return item.isPreparationRequired &&
        item.protectedAllowanceActionReady &&
        overview.permissions.prepare &&
        widget.session.hasPermission('accounting.ecl.allowance.prepare');
  }

  bool _canPost(
    EclAllowancePostingOverview overview,
    EclAllowancePostingItem item,
  ) {
    return item.isPostingReady &&
        item.protectedAllowanceActionReady &&
        overview.permissions.post &&
        widget.session.hasPermission('accounting.ecl.allowance.post');
  }

  void _message(String value) {
    final messenger = ScaffoldMessenger.of(context);
    messenger.clearSnackBars();
    messenger.showSnackBar(SnackBar(content: Text(value)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Initial ECL Allowance'),
        actions: <Widget>[
          IconButton(
            tooltip: 'Refresh initial ECL allowance queue',
            onPressed: _loading || _submittingLoanId != null ? null : _load,
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
    final prepareDenied =
        overview.items.any((item) => item.isPreparationRequired) &&
        !(overview.permissions.prepare &&
            widget.session.hasPermission('accounting.ecl.allowance.prepare'));
    final postDenied =
        overview.items.any((item) => item.isPostingReady) &&
        !(overview.permissions.post &&
            widget.session.hasPermission('accounting.ecl.allowance.post'));

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
          _SummaryCard(summary: overview.summary),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 6,
            children: _filters.entries
                .map(
                  (entry) => ChoiceChip(
                    label: Text(entry.value),
                    selected: _filter == entry.key,
                    onSelected: _submittingLoanId == null
                        ? (_) => _load(status: entry.key)
                        : null,
                  ),
                )
                .toList(growable: false),
          ),
          const SizedBox(height: 12),
          if (prepareDenied) ...<Widget>[
            const _PermissionNotice(
              message: 'Preparation permission is not assigned.',
            ),
            const SizedBox(height: 8),
          ],
          if (postDenied) ...<Widget>[
            const _PermissionNotice(
              message: 'Posting permission is not assigned.',
            ),
            const SizedBox(height: 8),
          ],
          if (_error != null) ...<Widget>[
            Card(
              color: Theme.of(context).colorScheme.errorContainer,
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(_error!),
              ),
            ),
            const SizedBox(height: 8),
          ],
          if (overview.items.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(18),
                child: Text('No loans match this server filter.'),
              ),
            )
          else
            ...overview.items.map(
              (item) => _AllowanceCard(
                item: item,
                canPrepare: _canPrepare(overview, item),
                canPost: _canPost(overview, item),
                submitting: _submittingLoanId == item.loanId,
                onPrepare: () => _prepare(item),
                onPost: () => _post(item),
              ),
            ),
        ],
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({required this.summary});

  final EclAllowancePostingSummary summary;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: const Key('ecl-allowance-summary'),
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
              spacing: 16,
              runSpacing: 8,
              children: <Widget>[
                Text('Loans: ${summary.loanCount}'),
                Text('Prepare: ${summary.preparationRequiredCount}'),
                Text('Post: ${summary.postingReadyCount}'),
                Text('Posted: ${summary.postedCurrentCount}'),
                Text('A5 required: ${summary.a5RemeasurementRequiredCount}'),
                Text('Blocked: ${summary.preparationBlockedCount}'),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _AllowanceCard extends StatelessWidget {
  const _AllowanceCard({
    required this.item,
    required this.canPrepare,
    required this.canPost,
    required this.submitting,
    required this.onPrepare,
    required this.onPost,
  });

  final EclAllowancePostingItem item;
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
            Text(
              item.loanNumber,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            Text('${item.loanTypeName} • ${item.loanStatus}'),
            const SizedBox(height: 6),
            Text(_statusLabel(item.allowancePostingStatus)),
            if (item.authoritativeEclAmount != null)
              Text('Authoritative ECL: ${item.authoritativeEclAmount}'),
            Text(
              'Current protected allowance: ${item.currentAllowanceBalance}',
            ),
            if (item.entryNumber != null) Text('Journal: ${item.entryNumber}'),
            if (canPrepare) ...<Widget>[
              const SizedBox(height: 10),
              FilledButton.icon(
                key: Key('prepare-ecl-${item.measurementId}'),
                onPressed: submitting ? null : onPrepare,
                icon: const Icon(Icons.fact_check_outlined),
                label: const Text('Prepare allowance draft'),
              ),
            ],
            if (canPost) ...<Widget>[
              const SizedBox(height: 10),
              FilledButton.icon(
                key: Key('post-ecl-${item.preparationId}'),
                onPressed: submitting ? null : onPost,
                icon: const Icon(Icons.lock_outline),
                label: const Text('Post initial allowance'),
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
  'preparation_required': 'Prepare',
  'posting_ready': 'Post',
  'posted_current': 'Posted',
  'ready': 'Actionable',
};

String _statusLabel(String status) {
  return switch (status) {
    'measurement_not_authoritative' => 'Measurement is not authoritative',
    'no_allowance_required' => 'No initial allowance required',
    'preparation_required' => 'Ready to prepare initial allowance',
    'posting_ready' => 'Prepared — posting confirmation required',
    'posted_current' => 'Posted — current protected allowance',
    'a5_remeasurement_required' => 'A5 remeasurement required',
    'posting_audit_incomplete' =>
      'Posting audit incomplete — Management review required',
    'preparation_blocked' =>
      'Preparation blocked — verify open period and accounts',
    _ => 'Status needs review',
  };
}

String _newToken() {
  final random = Random.secure();
  return List<int>.generate(
    32,
    (_) => random.nextInt(256),
  ).map((value) => value.toRadixString(16).padLeft(2, '0')).join();
}

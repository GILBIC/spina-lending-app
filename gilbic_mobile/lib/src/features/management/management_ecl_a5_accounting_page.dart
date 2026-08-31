import 'dart:math';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/ecl_a5_accounting.dart';
import 'package:gilbic_mobile/src/core/management/ecl_a5_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

class ManagementEclA5AccountingPage extends StatefulWidget {
  const ManagementEclA5AccountingPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.reviewTokenGenerator,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final EclA5AccountingRepository? repository;
  final String Function()? reviewTokenGenerator;

  @override
  State<ManagementEclA5AccountingPage> createState() =>
      _ManagementEclA5AccountingPageState();
}

class _ManagementEclA5AccountingPageState
    extends State<ManagementEclA5AccountingPage> {
  late final EclA5AccountingRepository _repository;
  late final String Function() _reviewTokenGenerator;
  final Map<String, String> _tokens = <String, String>{};
  EclA5Overview? _overview;
  String _filter = 'all';
  String? _error;
  String? _busyLoanId;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaEclA5AccountingRepository();
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
          () => _error =
              'The protected ECL adjustments queue could not be loaded.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _remeasure(EclA5ActionItem item) async {
    final overview = _overview;
    if (overview == null || !_canRemeasure(overview, item)) return;
    item.requireRemeasurementCoordinates();
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        binding: ManagementMutationBinding.eclA5,
        recordLabel: 'Loan',
        recordValue: item.loanNumber,
        statusLabel: _statusLabel(item.a5Status),
        facts: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Measurement date',
            value: eclA5DateText(item.measurementDate!),
          ),
          ManagementReviewFact(
            label: 'Prior allowance',
            value: item.currentAllowanceBalance,
          ),
          ManagementReviewFact(
            label: 'Target allowance',
            value: item.authoritativeEclAmount!,
          ),
          const ManagementReviewFact(label: 'Accounts', value: '5000 ↔ 1190'),
          ManagementReviewFact(
            label: 'Posting date',
            value: eclA5DateText(item.postingDate!),
          ),
        ],
        warnings: const <ManagementReviewWarning>[
          ManagementReviewWarning(
            severity: ManagementReviewWarningSeverity.caution,
            message:
                'This posts an immutable allowance adjustment from the exact current authoritative measurement.',
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
        nextActionLabel: 'Post ECL remeasurement',
        consequence:
            'The backend will post the exact allowance increase, decrease, or reversal and permanently audit this Management confirmation.',
      ),
    );
    if (!confirmed || !mounted) return;
    final tokenKey =
        'remeasure:${item.measurementId}:${item.calculationDigest}';
    await _runAction(
      item,
      tokenKey,
      (deviceId, token) => _repository.postRemeasurement(
        widget.session,
        deviceId: deviceId,
        item: item,
        reviewToken: token,
      ),
      'ECL allowance remeasurement posted.',
    );
  }

  Future<void> _writeoff(EclA5ActionItem item) async {
    final overview = _overview;
    if (overview == null || !_canWriteoff(overview, item)) return;
    item.requireWriteoffCoordinates();
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        binding: ManagementMutationBinding.eclA5,
        recordLabel: 'Loan',
        recordValue: item.loanNumber,
        statusLabel: _statusLabel(item.a5Status),
        facts: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Loan receivable',
            value: item.loanComponent!,
          ),
          ManagementReviewFact(
            label: 'Accrued interest',
            value: item.accruedInterestComponent!,
          ),
          ManagementReviewFact(
            label: 'Gross carrying amount',
            value: item.grossCarryingAmount!,
          ),
          ManagementReviewFact(
            label: 'Protected allowance',
            value: item.currentAllowanceBalance,
          ),
          ManagementReviewFact(
            label: 'Posting date',
            value: eclA5DateText(item.postingDate!),
          ),
        ],
        warnings: const <ManagementReviewWarning>[
          ManagementReviewWarning(
            severity: ManagementReviewWarningSeverity.caution,
            message:
                'This fully derecognizes the exact protected loan and accrued-interest balances. Write-off support alone never performs this action.',
          ),
        ],
        secondaryReferences: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Credit-risk review ID',
            value: '${item.creditRiskReviewId}',
          ),
          ManagementReviewFact(
            label: 'Calculation digest',
            value: item.calculationDigest!,
          ),
        ],
        nextActionLabel: 'Post full write-off',
        consequence:
            'The backend will immutably use the fully covering ECL allowance to derecognize the exact gross carrying amount and audit the result.',
      ),
    );
    if (!confirmed || !mounted) return;
    final tokenKey =
        'writeoff:${item.loanId}:${item.creditRiskReviewId}:${item.measurementId}';
    await _runAction(
      item,
      tokenKey,
      (deviceId, token) => _repository.postFullWriteoff(
        widget.session,
        deviceId: deviceId,
        item: item,
        reviewToken: token,
      ),
      'Full ECL accounting write-off posted.',
    );
  }

  Future<void> _reviewRecovery(EclA5ActionItem item) async {
    final overview = _overview;
    if (overview == null || !_canReviewRecovery(overview, item)) return;
    item.requireRecoveryReviewCoordinates();
    final evidence = await showDialog<_RecoveryEvidence>(
      context: context,
      builder: (context) => const _RecoveryEvidenceDialog(),
    );
    if (evidence == null || !mounted) return;
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        binding: ManagementMutationBinding.eclA5,
        recordLabel: 'Protected later cash',
        recordValue: item.loanNumber,
        statusLabel: _statusLabel(item.a5Status),
        facts: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Recovery amount',
            value: item.recoveryCandidateAmount!,
          ),
          ManagementReviewFact(
            label: 'Collection date',
            value: eclA5DateText(item.recoveryCandidateCollectionDate!),
          ),
          ManagementReviewFact(
            label: 'Evidence reference',
            value: evidence.reference,
          ),
        ],
        warnings: const <ManagementReviewWarning>[
          ManagementReviewWarning(
            severity: ManagementReviewWarningSeverity.caution,
            message:
                'This records immutable recovery evidence only. It does not mark the borrower cured and does not post a journal.',
          ),
        ],
        secondaryReferences: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Transaction ID',
            value: item.recoveryCandidateTransactionId!,
          ),
          ManagementReviewFact(label: 'Management note', value: evidence.note),
        ],
        nextActionLabel: 'Record recovery evidence',
        consequence:
            'The backend will bind this exact protected later cash transaction to retained Management evidence for separate recovery posting review.',
      ),
    );
    if (!confirmed || !mounted) return;
    final tokenKey =
        'recovery-review:${item.loanId}:${item.recoveryCandidateTransactionId}';
    await _runAction(
      item,
      tokenKey,
      (deviceId, token) => _repository.reviewRecovery(
        widget.session,
        deviceId: deviceId,
        item: item,
        reviewToken: token,
        evidenceReference: evidence.reference,
        reviewNote: evidence.note,
      ),
      'Post-write-off recovery evidence recorded.',
    );
  }

  Future<void> _postRecovery(EclA5ActionItem item) async {
    final overview = _overview;
    if (overview == null || !_canPostRecovery(overview, item)) return;
    item.requireRecoveryPostingCoordinates();
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        binding: ManagementMutationBinding.eclA5,
        recordLabel: 'Reviewed recovery',
        recordValue: item.loanNumber,
        statusLabel: _statusLabel(item.a5Status),
        facts: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Recovery amount',
            value: item.recoveryAmount!,
          ),
          ManagementReviewFact(
            label: 'Posting date',
            value: eclA5DateText(item.postingDate!),
          ),
          const ManagementReviewFact(
            label: 'Journal',
            value: 'Debit 1020 / Credit 5000',
          ),
        ],
        warnings: const <ManagementReviewWarning>[
          ManagementReviewWarning(
            severity: ManagementReviewWarningSeverity.caution,
            message:
                'Posting recognizes protected cash in profit or loss; it never recreates a receivable or allowance.',
          ),
        ],
        secondaryReferences: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Credit-risk review ID',
            value: '${item.creditRiskReviewId}',
          ),
          ManagementReviewFact(
            label: 'Transaction ID',
            value: item.recoveryTransactionId!,
          ),
        ],
        nextActionLabel: 'Post cash recovery',
        consequence:
            'The backend will immutably post the exact reviewed cash recovery and permanently audit this Management confirmation.',
      ),
    );
    if (!confirmed || !mounted) return;
    final tokenKey =
        'recovery-post:${item.creditRiskReviewId}:${item.recoveryTransactionId}';
    await _runAction(
      item,
      tokenKey,
      (deviceId, token) => _repository.postRecovery(
        widget.session,
        deviceId: deviceId,
        item: item,
        reviewToken: token,
      ),
      'Post-write-off cash recovery posted.',
    );
  }

  Future<void> _runAction(
    EclA5ActionItem item,
    String tokenKey,
    Future<EclA5ActionReceipt> Function(String deviceId, String token) action,
    String successMessage,
  ) async {
    final token = _tokens.putIfAbsent(tokenKey, _reviewTokenGenerator);
    setState(() => _busyLoanId = item.loanId);
    try {
      final identity = await widget.deviceIdentityProvider.load();
      await action(identity.installationId, token);
      _tokens.remove(tokenKey);
      if (!mounted) return;
      _message(successMessage);
      await _load();
    } on SpinaApiException catch (error) {
      if (mounted) _message(error.message);
    } on Object {
      if (mounted) {
        _message(
          'The result is uncertain. Review the authoritative server state before retrying.',
        );
      }
    } finally {
      if (mounted) setState(() => _busyLoanId = null);
    }
  }

  bool _canRemeasure(EclA5Overview overview, EclA5ActionItem item) =>
      item.isRemeasurementRequired &&
      overview.permissions.remeasurementPost &&
      widget.session.hasPermission('accounting.ecl.remeasurement.post');

  bool _canWriteoff(EclA5Overview overview, EclA5ActionItem item) =>
      item.isWriteoffReady &&
      overview.permissions.writeoffPost &&
      widget.session.hasPermission('accounting.ecl.writeoff.post');

  bool _canReviewRecovery(EclA5Overview overview, EclA5ActionItem item) =>
      item.isRecoveryReviewRequired &&
      overview.permissions.recoveryReview &&
      widget.session.hasPermission('accounting.ecl.recovery.review');

  bool _canPostRecovery(EclA5Overview overview, EclA5ActionItem item) =>
      item.isRecoveryReady &&
      overview.permissions.recoveryPost &&
      widget.session.hasPermission('accounting.ecl.recovery.post');

  void _message(String value) {
    final messenger = ScaffoldMessenger.of(context);
    messenger.clearSnackBars();
    messenger.showSnackBar(SnackBar(content: Text(value)));
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('ECL Adjustments'),
      actions: <Widget>[
        IconButton(
          tooltip: 'Refresh ECL adjustments',
          onPressed: _loading || _busyLoanId != null ? null : _load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: SafeArea(child: _body()),
  );

  Widget _body() {
    final overview = _overview;
    if (_loading && overview == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null && overview == null) {
      return _ErrorState(message: _error!, onRetry: _load);
    }
    if (overview == null) return const SizedBox.shrink();
    final notices = _permissionNotices(overview);
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
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
                    onSelected: _busyLoanId == null
                        ? (_) => _load(status: entry.key)
                        : null,
                  ),
                )
                .toList(growable: false),
          ),
          if (notices.isNotEmpty) ...<Widget>[
            const SizedBox(height: 12),
            for (final notice in notices) ...<Widget>[
              _PermissionNotice(message: notice),
              const SizedBox(height: 8),
            ],
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
          const SizedBox(height: 4),
          if (overview.items.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(18),
                child: Text('No A5 ECL actions match this server filter.'),
              ),
            )
          else
            for (final item in overview.items) ...<Widget>[
              _ActionCard(
                item: item,
                busy: _busyLoanId == item.loanId,
                canRemeasure: _canRemeasure(overview, item),
                canWriteoff: _canWriteoff(overview, item),
                canReviewRecovery: _canReviewRecovery(overview, item),
                canPostRecovery: _canPostRecovery(overview, item),
                onRemeasure: () => _remeasure(item),
                onWriteoff: () => _writeoff(item),
                onReviewRecovery: () => _reviewRecovery(item),
                onPostRecovery: () => _postRecovery(item),
              ),
              const SizedBox(height: 10),
            ],
        ],
      ),
    );
  }

  List<String> _permissionNotices(EclA5Overview overview) {
    final items = overview.items;
    return <String>[
      if (items.any((item) => item.isRemeasurementRequired) &&
          !(overview.permissions.remeasurementPost &&
              widget.session.hasPermission(
                'accounting.ecl.remeasurement.post',
              )))
        'Remeasurement permission is not assigned.',
      if (items.any((item) => item.isWriteoffReady) &&
          !(overview.permissions.writeoffPost &&
              widget.session.hasPermission('accounting.ecl.writeoff.post')))
        'Write-off permission is not assigned.',
      if (items.any((item) => item.isRecoveryReviewRequired) &&
          !(overview.permissions.recoveryReview &&
              widget.session.hasPermission('accounting.ecl.recovery.review')))
        'Recovery review permission is not assigned.',
      if (items.any((item) => item.isRecoveryReady) &&
          !(overview.permissions.recoveryPost &&
              widget.session.hasPermission('accounting.ecl.recovery.post')))
        'Recovery posting permission is not assigned.',
    ];
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({required this.summary});
  final EclA5Summary summary;

  @override
  Widget build(BuildContext context) => Card(
    key: const Key('ecl-a5-summary'),
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Wrap(
        spacing: 16,
        runSpacing: 8,
        children: <Widget>[
          Text('Remeasure: ${summary.remeasurementRequiredCount}'),
          Text('Write-off: ${summary.writeoffReadyCount}'),
          Text('Review cash: ${summary.recoveryReviewRequiredCount}'),
          Text('Post recovery: ${summary.recoveryReadyCount}'),
          Text('Blocked: ${summary.blockedCount}'),
        ],
      ),
    ),
  );
}

class _ActionCard extends StatelessWidget {
  const _ActionCard({
    required this.item,
    required this.busy,
    required this.canRemeasure,
    required this.canWriteoff,
    required this.canReviewRecovery,
    required this.canPostRecovery,
    required this.onRemeasure,
    required this.onWriteoff,
    required this.onReviewRecovery,
    required this.onPostRecovery,
  });

  final EclA5ActionItem item;
  final bool busy;
  final bool canRemeasure;
  final bool canWriteoff;
  final bool canReviewRecovery;
  final bool canPostRecovery;
  final VoidCallback onRemeasure;
  final VoidCallback onWriteoff;
  final VoidCallback onReviewRecovery;
  final VoidCallback onPostRecovery;

  @override
  Widget build(BuildContext context) => Card(
    key: Key('ecl-a5-${item.loanId}'),
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Text(item.loanNumber, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 4),
          Align(
            alignment: Alignment.centerLeft,
            child: _StatusChip(label: _statusLabel(item.a5Status)),
          ),
          const SizedBox(height: 8),
          _Fact(
            label: 'Protected allowance',
            value: item.currentAllowanceBalance,
          ),
          if (item.authoritativeEclAmount != null)
            _Fact(
              label: 'Authoritative ECL',
              value: item.authoritativeEclAmount!,
            ),
          if (item.grossCarryingAmount != null)
            _Fact(label: 'Gross carrying', value: item.grossCarryingAmount!),
          if (item.recoveryCandidateAmount != null)
            _Fact(
              label: 'Unreviewed protected cash',
              value: item.recoveryCandidateAmount!,
            ),
          if (item.recoveryAmount != null)
            _Fact(label: 'Reviewed recovery', value: item.recoveryAmount!),
          if (busy) ...<Widget>[
            const SizedBox(height: 10),
            const LinearProgressIndicator(),
          ],
          if (canRemeasure)
            FilledButton.icon(
              key: Key('remeasure-ecl-${item.loanId}'),
              onPressed: busy ? null : onRemeasure,
              icon: const Icon(Icons.tune),
              label: const Text('Post remeasurement'),
            ),
          if (canWriteoff)
            FilledButton.icon(
              key: Key('writeoff-ecl-${item.loanId}'),
              onPressed: busy ? null : onWriteoff,
              icon: const Icon(Icons.remove_circle_outline),
              label: const Text('Post full write-off'),
            ),
          if (canReviewRecovery)
            FilledButton.icon(
              key: Key('review-recovery-${item.loanId}'),
              onPressed: busy ? null : onReviewRecovery,
              icon: const Icon(Icons.fact_check_outlined),
              label: const Text('Review recovery evidence'),
            ),
          if (canPostRecovery)
            FilledButton.icon(
              key: Key('post-recovery-${item.loanId}'),
              onPressed: busy ? null : onPostRecovery,
              icon: const Icon(Icons.account_balance_outlined),
              label: const Text('Post cash recovery'),
            ),
        ],
      ),
    ),
  );
}

class _RecoveryEvidenceDialog extends StatefulWidget {
  const _RecoveryEvidenceDialog();

  @override
  State<_RecoveryEvidenceDialog> createState() =>
      _RecoveryEvidenceDialogState();
}

class _RecoveryEvidenceDialogState extends State<_RecoveryEvidenceDialog> {
  final _formKey = GlobalKey<FormState>();
  final _reference = TextEditingController();
  final _note = TextEditingController();

  @override
  void dispose() {
    _reference.dispose();
    _note.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Recovery evidence'),
    content: Form(
      key: _formKey,
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            TextFormField(
              key: const Key('recovery-evidence-reference'),
              controller: _reference,
              maxLength: 500,
              decoration: const InputDecoration(
                labelText: 'Evidence reference',
              ),
              validator: (value) => (value?.trim().isEmpty ?? true)
                  ? 'Evidence reference is required.'
                  : null,
            ),
            TextFormField(
              key: const Key('recovery-review-note'),
              controller: _note,
              minLines: 3,
              maxLines: 6,
              maxLength: 4000,
              decoration: const InputDecoration(
                labelText: 'Management rationale',
              ),
              validator: (value) => (value?.trim().length ?? 0) < 20
                  ? 'Enter at least 20 characters.'
                  : null,
            ),
          ],
        ),
      ),
    ),
    actions: <Widget>[
      TextButton(
        onPressed: () => Navigator.of(context).pop(),
        child: const Text('Cancel'),
      ),
      FilledButton(
        key: const Key('continue-recovery-review'),
        onPressed: () {
          if (!_formKey.currentState!.validate()) return;
          Navigator.of(context).pop(
            _RecoveryEvidence(
              reference: _reference.text.trim(),
              note: _note.text.trim(),
            ),
          );
        },
        child: const Text('Continue to review'),
      ),
    ],
  );
}

class _RecoveryEvidence {
  const _RecoveryEvidence({required this.reference, required this.note});
  final String reference;
  final String note;
}

class _Fact extends StatelessWidget {
  const _Fact({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 4),
    child: Row(
      children: <Widget>[
        Expanded(child: Text(label)),
        const SizedBox(width: 8),
        Text(value, style: Theme.of(context).textTheme.labelLarge),
      ],
    ),
  );
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) =>
      Chip(visualDensity: VisualDensity.compact, label: Text(label));
}

class _PermissionNotice extends StatelessWidget {
  const _PermissionNotice({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) => Card(
    color: Theme.of(context).colorScheme.secondaryContainer,
    child: Padding(padding: const EdgeInsets.all(12), child: Text(message)),
  );
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
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

const _filters = <String, String>{
  'all': 'All',
  'remeasurement_required': 'Remeasure',
  'writeoff_ready': 'Write-off',
  'recovery_review_required': 'Review cash',
  'post_writeoff_recovery_ready': 'Post recovery',
  'blocked': 'Blocked',
};

String _statusLabel(String value) => switch (value) {
  'remeasurement_required' => 'Remeasurement required',
  'allowance_current' => 'Allowance current',
  'writeoff_ready' => 'Full write-off ready',
  'written_off' => 'Written off',
  'recovery_review_required' => 'Recovery evidence review required',
  'post_writeoff_recovery_ready' => 'Recovery posting ready',
  'blocked' => 'Blocked — review protected evidence',
  _ => 'Status needs review',
};

String _newToken() {
  const digits = '0123456789abcdef';
  final random = Random.secure();
  return List<String>.generate(64, (_) => digits[random.nextInt(16)]).join();
}

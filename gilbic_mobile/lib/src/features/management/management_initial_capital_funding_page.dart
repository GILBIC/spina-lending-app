import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/initial_capital_funding.dart';
import 'package:gilbic_mobile/src/core/management/initial_capital_funding_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

class ManagementInitialCapitalFundingPage extends StatefulWidget {
  const ManagementInitialCapitalFundingPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.uuidGenerator,
    this.confirmationTokenGenerator,
    this.now,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final InitialCapitalFundingRepository? repository;
  final String Function()? uuidGenerator;
  final String Function()? confirmationTokenGenerator;
  final DateTime Function()? now;

  @override
  State<ManagementInitialCapitalFundingPage> createState() =>
      _ManagementInitialCapitalFundingPageState();
}

class _ManagementInitialCapitalFundingPageState
    extends State<ManagementInitialCapitalFundingPage> {
  late final InitialCapitalFundingRepository _repository;
  late final String Function() _uuidGenerator;
  late final String Function() _confirmationTokenGenerator;
  late final DateTime Function() _now;
  final Map<String, String> _evidenceRetryIds = <String, String>{};
  final Map<String, String> _postingTokens = <String, String>{};
  InitialCapitalFundingOverview? _overview;
  String? _error;
  String? _busyKey;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaInitialCapitalFundingRepository();
    _uuidGenerator = widget.uuidGenerator ?? _newUuid;
    _confirmationTokenGenerator =
        widget.confirmationTokenGenerator ?? _newToken;
    _now = widget.now ?? DateTime.now;
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final overview = await _repository.load(
        widget.session,
        deviceId: identity.installationId,
      );
      if (mounted) setState(() => _overview = overview);
    } on SpinaApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) {
        setState(
          () => _error =
              'The protected initial-capital queue could not be loaded.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _recordEvidence() async {
    final overview = _overview;
    if (overview == null || !_canRecord(overview)) return;
    final draft = await showDialog<InitialCapitalEvidenceDraft>(
      context: context,
      builder: (context) => _EvidenceDialog(
        accounts: overview.cashAccounts,
        initialDate: initialCapitalDateText(_now()),
      ),
    );
    if (draft == null || !mounted) return;
    final account = overview.cashAccounts.singleWhere(
      (candidate) => candidate.code == draft.cashAccountCode,
    );
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        surface: ManagementMutationSurface.initialCapital,
        recordLabel: 'Retained funding evidence',
        recordValue: draft.evidenceReference,
        statusLabel: 'Ready to record immutable evidence',
        facts: <ManagementReviewFact>[
          ManagementReviewFact(label: 'Funding date', value: draft.fundingDate),
          ManagementReviewFact(label: 'Amount', value: draft.amount),
          ManagementReviewFact(
            label: 'Cash account',
            value: '${account.code} ${account.name}',
          ),
          const ManagementReviewFact(
            label: 'Credit account',
            value: '3000 Capital',
          ),
        ],
        warnings: const <ManagementReviewWarning>[
          ManagementReviewWarning(
            severity: ManagementReviewWarningSeverity.caution,
            message:
                'Use only real retained funding evidence. Recording evidence does not post a journal or change a balance.',
          ),
        ],
        secondaryReferences: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Evidence source',
            value: draft.evidenceSource,
          ),
          ManagementReviewFact(
            label: 'Evidence fingerprint',
            value: draft.evidenceDigest,
          ),
        ],
        nextActionLabel: 'Record funding evidence',
        consequence:
            'The backend will immutably retain this evidence for a separate protected preparation and posting review.',
        risk: ManagementReviewRisk.protectedFinancial,
      ),
    );
    if (!confirmed || !mounted) return;
    final retryKey = <String>[
      draft.fundingDate,
      draft.amount,
      draft.cashAccountCode,
      draft.evidenceSource,
      draft.evidenceReference,
      draft.evidenceDigest,
      draft.evidenceNote,
    ].join('|');
    final retryId = _evidenceRetryIds.putIfAbsent(retryKey, _uuidGenerator);
    await _run('evidence:$retryKey', () async {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.recordEvidence(
        widget.session,
        deviceId: identity.installationId,
        draft: draft,
        idempotencyKey: retryId,
      );
      _evidenceRetryIds.remove(retryKey);
      _message('Initial-capital funding evidence recorded.');
    });
  }

  Future<void> _prepare(InitialCapitalFundingItem item) async {
    final overview = _overview;
    if (overview == null || !_canPrepare(overview, item)) return;
    item.requirePrepareCoordinates();
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        surface: ManagementMutationSurface.initialCapital,
        recordLabel: 'Initial-capital evidence',
        recordValue: item.evidenceReference,
        statusLabel: 'Evidence ready for protected draft preparation',
        facts: <ManagementReviewFact>[
          ManagementReviewFact(label: 'Funding date', value: item.fundingDate),
          ManagementReviewFact(label: 'Amount', value: item.amount),
          ManagementReviewFact(
            label: 'Debit account',
            value: '${item.cashAccountCode} ${item.cashAccountName}',
          ),
          ManagementReviewFact(
            label: 'Credit account',
            value: '${item.capitalAccountCode} Capital',
          ),
        ],
        secondaryReferences: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Evidence fingerprint',
            value: item.evidenceDigest,
          ),
          ManagementReviewFact(label: 'Evidence ID', value: item.evidenceId),
        ],
        warnings: const <ManagementReviewWarning>[
          ManagementReviewWarning(
            severity: ManagementReviewWarningSeverity.caution,
            message:
                'The server will prepare a protected draft only. No General Ledger balance changes yet.',
          ),
        ],
        nextActionLabel: 'Prepare capital journal',
        consequence:
            'The backend will create an exact two-line draft for separate posting confirmation.',
        risk: ManagementReviewRisk.protectedFinancial,
      ),
    );
    if (!confirmed || !mounted) return;
    await _run(item.evidenceId, () async {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.prepare(
        widget.session,
        deviceId: identity.installationId,
        item: item,
      );
      _message('Initial-capital journal draft prepared.');
    });
  }

  Future<void> _post(InitialCapitalFundingItem item) async {
    final overview = _overview;
    if (overview == null || !_canPost(overview, item)) return;
    item.requirePostCoordinates();
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        surface: ManagementMutationSurface.initialCapital,
        recordLabel: 'Prepared initial-capital journal',
        recordValue: item.evidenceReference,
        statusLabel: 'Prepared — exact posting confirmation required',
        facts: <ManagementReviewFact>[
          ManagementReviewFact(label: 'Funding date', value: item.fundingDate),
          ManagementReviewFact(label: 'Amount', value: item.amount),
          ManagementReviewFact(
            label: 'Debit account',
            value: '${item.cashAccountCode} ${item.cashAccountName}',
          ),
          ManagementReviewFact(
            label: 'Credit account',
            value: '${item.capitalAccountCode} Capital',
          ),
        ],
        secondaryReferences: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Fiscal period ID',
            value: item.fiscalPeriodId!,
          ),
          ManagementReviewFact(
            label: 'Journal entry ID',
            value: item.journalEntryId!,
          ),
          ManagementReviewFact(
            label: 'Evidence fingerprint',
            value: item.evidenceDigest,
          ),
        ],
        warnings: const <ManagementReviewWarning>[
          ManagementReviewWarning(
            severity: ManagementReviewWarningSeverity.caution,
            message:
                'Posting is immutable. It must represent actual company funding supported by retained evidence.',
          ),
        ],
        nextActionLabel: 'Post initial capital',
        consequence:
            'The backend will immutably post Debit selected cash account and Credit Capital 3000 with permanent audit evidence.',
        risk: ManagementReviewRisk.protectedFinancial,
      ),
    );
    if (!confirmed || !mounted) return;
    final tokenKey = <String>[
      item.evidenceId,
      item.evidenceDigest,
      item.amount,
      item.cashAccountCode,
      item.fundingDate,
      item.fiscalPeriodId!,
      item.journalEntryId!,
    ].join('|');
    final token = _postingTokens.putIfAbsent(
      tokenKey,
      _confirmationTokenGenerator,
    );
    await _run(item.evidenceId, () async {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.post(
        widget.session,
        deviceId: identity.installationId,
        item: item,
        confirmationToken: token,
      );
      _postingTokens.remove(tokenKey);
      _message('Initial capital posted.');
    });
  }

  Future<void> _run(String busyKey, Future<void> Function() action) async {
    if (_busyKey != null) return;
    setState(() => _busyKey = busyKey);
    var succeeded = false;
    try {
      await action();
      succeeded = true;
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
      if (mounted) setState(() => _busyKey = null);
      if (!succeeded && mounted) setState(() {});
    }
  }

  bool _canRecord(InitialCapitalFundingOverview overview) =>
      overview.permissions.evidenceRecord &&
      overview.cashAccounts.isNotEmpty &&
      widget.session.hasPermission(
        'accounting.initial_capital.evidence.record',
      );

  bool _canPrepare(
    InitialCapitalFundingOverview overview,
    InitialCapitalFundingItem item,
  ) =>
      item.isEvidenceReady &&
      overview.permissions.prepare &&
      widget.session.hasPermission('accounting.initial_capital.prepare');

  bool _canPost(
    InitialCapitalFundingOverview overview,
    InitialCapitalFundingItem item,
  ) =>
      item.isPrepared &&
      overview.permissions.post &&
      widget.session.hasPermission('accounting.initial_capital.post');

  void _message(String value) {
    final messenger = ScaffoldMessenger.of(context);
    messenger.clearSnackBars();
    messenger.showSnackBar(SnackBar(content: Text(value)));
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Initial Capital Funding'),
      actions: <Widget>[
        IconButton(
          tooltip: 'Refresh initial-capital funding',
          onPressed: _loading || _busyKey != null ? null : _load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    floatingActionButton: _overview != null && _canRecord(_overview!)
        ? FloatingActionButton.small(
            key: const Key('record-initial-capital-evidence'),
            tooltip: 'Record retained funding evidence',
            onPressed: _busyKey == null ? _recordEvidence : null,
            child: const Icon(Icons.add),
          )
        : null,
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
    final evidenceDenied =
        !overview.permissions.evidenceRecord ||
        !widget.session.hasPermission(
          'accounting.initial_capital.evidence.record',
        );
    final prepareDenied =
        overview.items.any((item) => item.isEvidenceReady) &&
        !(overview.permissions.prepare &&
            widget.session.hasPermission('accounting.initial_capital.prepare'));
    final postDenied =
        overview.items.any((item) => item.isPrepared) &&
        !(overview.permissions.post &&
            widget.session.hasPermission('accounting.initial_capital.post'));

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 88),
        children: <Widget>[
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Text(overview.notice),
            ),
          ),
          const SizedBox(height: 12),
          _SummaryCard(summary: overview.summary),
          if (evidenceDenied)
            const _PermissionNotice(
              'Evidence-record permission is not assigned.',
            ),
          if (prepareDenied)
            const _PermissionNotice('Preparation permission is not assigned.'),
          if (postDenied)
            const _PermissionNotice('Posting permission is not assigned.'),
          if (overview.cashAccounts.isEmpty)
            const _PermissionNotice(
              'No eligible cash account is available from the server.',
            ),
          if (_error != null)
            Card(
              color: Theme.of(context).colorScheme.errorContainer,
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(_error!),
              ),
            ),
          const SizedBox(height: 4),
          if (overview.items.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(18),
                child: Text('No retained initial-capital evidence yet.'),
              ),
            )
          else
            ...overview.items.map(
              (item) => _FundingCard(
                item: item,
                canPrepare: _canPrepare(overview, item),
                canPost: _canPost(overview, item),
                busy: _busyKey == item.evidenceId,
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
  final InitialCapitalFundingSummary summary;

  @override
  Widget build(BuildContext context) => Card(
    key: const Key('initial-capital-summary'),
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
            spacing: 14,
            runSpacing: 8,
            children: <Widget>[
              Text('Total evidence: ${summary.evidenceCount}'),
              Text('Ready: ${summary.evidenceReadyCount}'),
              Text('Prepared: ${summary.preparedNotPostedCount}'),
              Text('Posted: ${summary.postedCount}'),
              Text('Blocked: ${summary.blockedNoOpenPeriodCount}'),
            ],
          ),
          const SizedBox(height: 6),
          Text('Recorded: ${summary.totalAmount}'),
          Text('Posted: ${summary.postedAmount}'),
        ],
      ),
    ),
  );
}

class _FundingCard extends StatelessWidget {
  const _FundingCard({
    required this.item,
    required this.canPrepare,
    required this.canPost,
    required this.busy,
    required this.onPrepare,
    required this.onPost,
  });

  final InitialCapitalFundingItem item;
  final bool canPrepare;
  final bool canPost;
  final bool busy;
  final VoidCallback onPrepare;
  final VoidCallback onPost;

  @override
  Widget build(BuildContext context) => Card(
    margin: const EdgeInsets.only(bottom: 12),
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  item.evidenceReference,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              Chip(label: Text(_status(item.accountingStatus))),
            ],
          ),
          Text('${item.fundingDate} • ${item.amount}'),
          Text('${item.cashAccountCode} ${item.cashAccountName}'),
          Text(item.evidenceSource),
          if (item.accountingBlocker != null) ...<Widget>[
            const SizedBox(height: 6),
            Text(
              item.accountingBlocker!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
          if (item.entryNumber != null) Text('Journal: ${item.entryNumber}'),
          if (canPrepare) ...<Widget>[
            const SizedBox(height: 10),
            FilledButton.icon(
              key: Key('prepare-initial-capital-${item.evidenceId}'),
              onPressed: busy ? null : onPrepare,
              icon: const Icon(Icons.fact_check_outlined),
              label: const Text('Prepare capital journal'),
            ),
          ],
          if (canPost) ...<Widget>[
            const SizedBox(height: 10),
            FilledButton.icon(
              key: Key('post-initial-capital-${item.evidenceId}'),
              onPressed: busy ? null : onPost,
              icon: const Icon(Icons.lock_outline),
              label: const Text('Post initial capital'),
            ),
          ],
          if (busy) ...<Widget>[
            const SizedBox(height: 8),
            const LinearProgressIndicator(),
          ],
        ],
      ),
    ),
  );
}

class _EvidenceDialog extends StatefulWidget {
  const _EvidenceDialog({required this.accounts, required this.initialDate});
  final List<InitialCapitalCashAccount> accounts;
  final String initialDate;

  @override
  State<_EvidenceDialog> createState() => _EvidenceDialogState();
}

class _EvidenceDialogState extends State<_EvidenceDialog> {
  late final TextEditingController _date;
  final _amount = TextEditingController();
  final _source = TextEditingController();
  final _reference = TextEditingController();
  final _digest = TextEditingController();
  final _note = TextEditingController();
  late String _accountCode;

  @override
  void initState() {
    super.initState();
    _date = TextEditingController(text: widget.initialDate);
    _accountCode = widget.accounts.first.code;
  }

  @override
  void dispose() {
    _date.dispose();
    _amount.dispose();
    _source.dispose();
    _reference.dispose();
    _digest.dispose();
    _note.dispose();
    super.dispose();
  }

  void _review() {
    final draft = InitialCapitalEvidenceDraft(
      fundingDate: _date.text.trim(),
      amount: _amount.text.trim(),
      cashAccountCode: _accountCode,
      evidenceSource: _source.text.trim(),
      evidenceReference: _reference.text.trim(),
      evidenceDigest: _digest.text.trim(),
      evidenceNote: _note.text.trim(),
    );
    try {
      draft.validate();
      Navigator.of(context).pop(draft);
    } on Object {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Complete the date, exact amount, retained source/reference, lowercase SHA-256 fingerprint, and evidence note.',
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Record funding evidence'),
    content: SizedBox(
      width: 420,
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            TextField(
              key: const Key('initial-capital-date'),
              controller: _date,
              decoration: const InputDecoration(
                labelText: 'Funding date (YYYY-MM-DD)',
              ),
            ),
            TextField(
              key: const Key('initial-capital-amount'),
              controller: _amount,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              inputFormatters: <TextInputFormatter>[
                FilteringTextInputFormatter.allow(RegExp(r'[0-9.]')),
              ],
              decoration: const InputDecoration(labelText: 'Exact amount'),
            ),
            DropdownButtonFormField<String>(
              initialValue: _accountCode,
              isExpanded: true,
              decoration: const InputDecoration(
                labelText: 'Receiving cash account',
              ),
              items: widget.accounts
                  .map(
                    (account) => DropdownMenuItem<String>(
                      value: account.code,
                      child: Text(
                        '${account.code} ${account.name}',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  )
                  .toList(growable: false),
              onChanged: (value) {
                if (value != null) setState(() => _accountCode = value);
              },
            ),
            TextField(
              key: const Key('initial-capital-source'),
              controller: _source,
              decoration: const InputDecoration(labelText: 'Evidence source'),
            ),
            TextField(
              key: const Key('initial-capital-reference'),
              controller: _reference,
              decoration: const InputDecoration(
                labelText: 'Evidence reference',
              ),
            ),
            TextField(
              key: const Key('initial-capital-digest'),
              controller: _digest,
              maxLength: 64,
              decoration: const InputDecoration(
                labelText: 'Evidence fingerprint (SHA-256)',
              ),
            ),
            TextField(
              key: const Key('initial-capital-note'),
              controller: _note,
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(labelText: 'Evidence note'),
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
        key: const Key('review-initial-capital-evidence'),
        onPressed: _review,
        child: const Text('Review evidence'),
      ),
    ],
  );
}

class _PermissionNotice extends StatelessWidget {
  const _PermissionNotice(this.message);
  final String message;

  @override
  Widget build(BuildContext context) => Card(
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

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.message, required this.onRetry});
  final String message;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) => Center(
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

String _status(String value) => switch (value) {
  'evidence_ready' => 'Evidence ready',
  'prepared_not_posted' => 'Prepared',
  'posted' => 'Posted',
  'blocked_no_open_period' => 'Blocked',
  _ => 'Needs review',
};

String _newToken() {
  final random = Random.secure();
  return List<int>.generate(
    32,
    (_) => random.nextInt(256),
  ).map((value) => value.toRadixString(16).padLeft(2, '0')).join();
}

String _newUuid() {
  final random = Random.secure();
  final bytes = List<int>.generate(16, (_) => random.nextInt(256));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  final hex = bytes
      .map((value) => value.toRadixString(16).padLeft(2, '0'))
      .join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-'
      '${hex.substring(12, 16)}-${hex.substring(16, 20)}-'
      '${hex.substring(20)}';
}

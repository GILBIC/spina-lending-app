import 'package:gilbic_mobile/src/features/treasury/loan_payout_page.dart';
import 'package:gilbic_mobile/src/features/treasury/treasury_selectable_text.dart';
import 'dart:math';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/features/treasury/collector_surplus_page.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_saver.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_repository.dart';
import 'package:gilbic_mobile/src/features/treasury/treasury_claim_page.dart';
import 'package:gilbic_mobile/src/features/treasury/treasury_command_page.dart';

String newTreasuryRequestId() {
  final random = Random.secure();
  final bytes = List<int>.generate(16, (_) => random.nextInt(256));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  final h = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  return '${h.substring(0, 8)}-${h.substring(8, 12)}-${h.substring(12, 16)}-${h.substring(16, 20)}-${h.substring(20)}';
}

class TreasuryWorkspacePage extends StatefulWidget {
  const TreasuryWorkspacePage({
    required this.session,
    this.deviceIdentityProvider,
    this.repository,
    this.borrowerChoices = const [],
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider? deviceIdentityProvider;
  final TreasuryRepository? repository;
  final List<Map<String, dynamic>> borrowerChoices;
  @override
  State<TreasuryWorkspacePage> createState() => _TreasuryWorkspacePageState();
}

class _TreasuryWorkspacePageState extends State<TreasuryWorkspacePage> {
  TreasuryRepository? _repository;
  TreasuryWorkspace? _workspace;
  TreasuryPage? _page;
  String? _accountId, _error;
  TreasuryListKind _kind = TreasuryListKind.claims;
  bool _loading = true;
  int _offset = 0, _generation = 0;
  TreasuryAccount? get _account =>
      _accountId == null ? null : _workspace?.account(_accountId!);
  bool get _pending =>
      _repository?.pendingRequestId != null || _repository?.busy == true;
  @override
  void initState() {
    super.initState();
    _initialize();
  }

  @override
  void didUpdateWidget(TreasuryWorkspacePage old) {
    super.didUpdateWidget(old);
    if (old.session != widget.session || old.repository != widget.repository) {
      _generation++;
      _repository?.dispose();
      _repository = null;
      _workspace = null;
      _page = null;
      _initialize();
    }
  }

  @override
  void dispose() {
    _generation++;
    _repository?.dispose();
    super.dispose();
  }

  bool _current(int generation) => mounted && generation == _generation;
  Future<void> _initialize() async {
    final generation = ++_generation;
    try {
      final identity = widget.repository == null
          ? await (widget.deviceIdentityProvider ?? DeviceIdentityProvider())
                .load()
          : null;
      if (!_current(generation)) return;
      _repository =
          widget.repository ??
          SpinaTreasuryRepository(
            session: widget.session,
            deviceId: identity!.installationId,
            getSession: () => mounted ? widget.session : null,
          );
      await _refresh(restore: true);
    } catch (error) {
      if (_current(generation)) {
        setState(() {
          _loading = false;
          _error = error.toString();
        });
      }
    }
  }

  Future<void> _refresh({bool restore = false}) async {
    final generation = ++_generation;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final w = await _repository!.loadWorkspace();
      if (!_current(generation)) return;
      _workspace = w;
      _accountId =
          w.account(_accountId ?? '')?.id ?? w.accounts.firstOrNull?.id;
      if (restore) await _repository!.restoreAttempt();
      if (!_current(generation)) return;
      await _loadPage(generation);
    } catch (error) {
      if (_current(generation)) {
        setState(() {
          _error = error.toString();
          if (_repository?.denied == true) {
            _workspace = null;
            _page = null;
          }
        });
      }
    } finally {
      if (_current(generation)) setState(() => _loading = false);
    }
  }

  Future<void> _loadPage(int generation) async {
    final page = await _repository!.list(
      _kind,
      accountId: _accountId,
      offset: _offset,
    );
    if (_current(generation)) setState(() => _page = page);
  }

  Future<void> _select({
    String? accountId,
    TreasuryListKind? kind,
    int? offset,
  }) async {
    if (_loading) return;
    setState(() {
      if (accountId != null) _accountId = accountId;
      if (kind != null) _kind = kind;
      _offset = offset ?? 0;
      _page = null;
      _error = null;
      _loading = true;
    });
    final g = ++_generation;
    try {
      await _loadPage(g);
    } catch (error) {
      if (_current(g)) setState(() => _error = error.toString());
    } finally {
      if (_current(g)) setState(() => _loading = false);
    }
  }

  Future<void> _open(Widget page) async {
    await Navigator.of(
      context,
    ).push<void>(MaterialPageRoute(builder: (_) => page));
    if (mounted) setState(() {});
  }

  Future<void> _command(
    TreasuryAction action, {
    Map<String, dynamic> initial = const {},
    String? targetId,
  }) async {
    if (_pending) return;
    final a = _account;
    if (a == null && action != TreasuryAction.accountConfigure) return;
    await _open(
      TreasuryCommandPage(
        repository: _repository!,
        account: a,
        action: action,
        initial: initial,
        targetId: targetId,
      ),
    );
  }

  Future<void> _recover({bool retry = false}) async {
    if (retry) {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: const Text('Retry unchanged request?'),
          content: const Text(
            'This resends only the exact submitted request and private file. Review the request check first. Nothing will be recalculated.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(c, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(c, true),
              child: const Text('Retry unchanged'),
            ),
          ],
        ),
      );
      if (confirmed != true || !mounted) return;
    }
    setState(() => _loading = true);
    try {
      final result = retry
          ? await _repository!.retrySame()
          : await _repository!.recover();
      if (mounted) {
        setState(
          () => _error = result == null
              ? 'No saved outcome is available yet. The request remains unconfirmed.'
              : result.status == 'saved'
              ? 'Saved request confirmed. Refresh to load current records.'
              : 'Server blocked the unchanged request. Review its reason before starting another action.',
        );
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  List<Map<String, dynamic>> get _borrowers =>
      [
            ...(_workspace?.raw.containsKey('borrower_choices') == true
                ? ((_workspace?.raw['borrower_choices'] as List?) ?? [])
                      .whereType<Map<String, dynamic>>()
                : widget.borrowerChoices),
          ]
          .where(
            (row) =>
                row['allowed_account_ids'] == null ||
                (row['allowed_account_ids'] as List).contains(_accountId),
          )
          .toList();
  @override
  Widget build(BuildContext context) {
    final w = _workspace;
    final a = _account;
    return Scaffold(
      appBar: AppBar(
        toolbarHeight: MediaQuery.textScalerOf(
          context,
        ).scale(56).clamp(56, 112).toDouble(),
        title: const Text('Cash and GCash Control'),
        actions: [
          if (w != null && _repository is LoanPayoutRepository)
            IconButton(
              tooltip: 'Loan payouts',
              onPressed: _loading
                  ? null
                  : () => _open(
                      LoanPayoutPage(
                        repository: _repository as LoanPayoutRepository,
                        accountId: a?.permits('loan_payout_prepare') == true
                            ? a!.id
                            : null,
                      ),
                    ),
              icon: const Icon(Icons.payments_outlined),
            ),
          if (w != null && _repository is CollectorSurplusRepository)
            IconButton(
              tooltip: 'Collector Excess',
              onPressed: _loading
                  ? null
                  : () => _open(
                      CollectorSurplusPage(
                        session: widget.session,
                        repository: _repository as CollectorSurplusRepository,
                      ),
                    ),
              icon: const Icon(Icons.account_balance_wallet_outlined),
            ),
          IconButton(
            tooltip: 'Refresh current records',
            onPressed: _loading ? null : () => _refresh(),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const Text(
              'Online records. Payment proof, recipient verification and official loan recording are separate steps.',
            ),
            const SizedBox(height: 12),
            if (_loading) const LinearProgressIndicator(),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Text(_error!, semanticsLabel: _error),
              ),
            if (_repository?.pendingRequestId != null)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Unconfirmed submitted request'),
                      TreasurySelectableText(_repository!.pendingRequestId!),
                      const Text(
                        'Check this request before another submission. Closing or restarting does not resend it.',
                      ),
                      Wrap(
                        spacing: 8,
                        children: [
                          OutlinedButton(
                            onPressed: _loading ? null : () => _recover(),
                            child: const Text('Check request'),
                          ),
                          TextButton(
                            onPressed: _loading
                                ? null
                                : () => _recover(retry: true),
                            child: const Text('Retry unchanged'),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            if (w != null) ...[
              if (!w.writable)
                const Text(
                  'Cash and GCash Control is disabled or not configured. Existing records remain read-only.',
                ),
              for (final blocker in w.blockers) Text(blocker),
              if (w.accounts.isEmpty)
                const Text('No authorized accounts were returned.'),
              if (w.accounts.isNotEmpty)
                DropdownButtonFormField<String>(
                  key: ValueKey(_accountId),
                  initialValue: _accountId,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Authorized receiving account',
                  ),
                  items: [
                    for (final row in w.accounts)
                      DropdownMenuItem(
                        value: row.id,
                        child: Text(row.alias, overflow: TextOverflow.ellipsis),
                      ),
                  ],
                  onChanged: _loading ? null : (id) => _select(accountId: id),
                ),
              if (a != null) ...[
                const SizedBox(height: 12),
                if (a.instructions.isNotEmpty)
                  TreasurySelectableText(a.instructions),
                if (a.balance != null)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Account balance'),
                          if (a.balance!['available'] == true &&
                              a.balance!['expected_balance'] is String)
                            TreasurySelectableText(
                              'PHP ${a.balance!['expected_balance']}',
                            )
                          else
                            Text(
                              a.balance!['message'] as String? ??
                                  'Opening observation unavailable',
                            ),
                          if (a.balance!['cutoff'] != null)
                            Text('As of ${a.balance!['cutoff']}'),
                          if (a.balance!['opening_cutoff'] != null)
                            Text(
                              'Opening cutoff ${a.balance!['opening_cutoff']}',
                            ),
                        ],
                      ),
                    ),
                  ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    ChoiceChip(
                      label: const Text('Payment proofs'),
                      selected: _kind == TreasuryListKind.claims,
                      onSelected: (_) => _select(kind: TreasuryListKind.claims),
                    ),
                    if (a.balance != null) ...[
                      for (final k in [
                        TreasuryListKind.events,
                        TreasuryListKind.receipts,
                        TreasuryListKind.reconciliations,
                        if (a.permits('opening_activate'))
                          TreasuryListKind.openings,
                      ])
                        ChoiceChip(
                          label: Text(switch (k) {
                            TreasuryListKind.events => 'Movements',
                            TreasuryListKind.receipts => 'Received funds',
                            TreasuryListKind.openings => 'Observed openings',
                            _ => 'Reconciliations',
                          }),
                          selected: _kind == k,
                          onSelected: (_) => _select(kind: k),
                        ),
                    ],
                  ],
                ),
                if (w.capability('claim_submit') && a.permits('claim_submit'))
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    child: FilledButton.icon(
                      onPressed: _pending
                          ? null
                          : () => _open(
                              TreasuryClaimPage(
                                repository: _repository!,
                                account: a,
                                borrowerChoices: _borrowers,
                              ),
                            ),
                      icon: const Icon(Icons.upload_file),
                      label: const Text('Submit payment proof'),
                    ),
                  ),
                if (_page != null) ...[
                  Text(
                    '${_page!.totalCount} records in this authorized query. Showing page ${_offset ~/ 50 + 1}.',
                  ),
                  if (_page!.items.isEmpty)
                    const Text('No records were returned.'),
                  if (_page!.totals != null)
                    TreasuryRecordSummary(
                      record: _page!.totals!,
                      label: 'Server totals for the complete query',
                    ),
                  for (final row in _page!.items)
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            TreasuryRecordSummary(record: row),
                            if (_kind == TreasuryListKind.openings &&
                                row['status'] == 'draft' &&
                                a.permits('opening_activate'))
                              OutlinedButton(
                                onPressed: _pending
                                    ? null
                                    : () => _command(
                                        TreasuryAction.openingActivate,
                                        initial: {
                                          'opening_id': row['id'],
                                          'opening_version': row['version'],
                                        },
                                        targetId: requireTreasuryId(row['id']),
                                      ),
                                child: const Text('Review observed opening'),
                              ),
                            if (_kind != TreasuryListKind.events &&
                                _kind != TreasuryListKind.openings)
                              OutlinedButton(
                                onPressed: () => _open(
                                  TreasuryRecordPage(
                                    repository: _repository!,
                                    kind: _kind,
                                    id: requireTreasuryId(row['id']),
                                  ),
                                ),
                                child: Text(switch (_kind) {
                                  TreasuryListKind.claims =>
                                    'Open payment proof',
                                  TreasuryListKind.receipts =>
                                    'Open received funds',
                                  _ => 'Open reconciliation',
                                }),
                              ),
                          ],
                        ),
                      ),
                    ),
                  Wrap(
                    spacing: 8,
                    children: [
                      OutlinedButton(
                        onPressed: _loading || _offset == 0
                            ? null
                            : () => _select(offset: _offset - 50),
                        child: const Text('Previous'),
                      ),
                      OutlinedButton(
                        onPressed: _loading || !_page!.hasMore
                            ? null
                            : () => _select(offset: _offset + 50),
                        child: const Text('Next page'),
                      ),
                    ],
                  ),
                ],
                const SizedBox(height: 20),
                for (final action in TreasuryAction.values.where(
                  (v) =>
                      v != TreasuryAction.receiptApply &&
                      !isLoanPayoutAction(v) &&
                      a.permits(v.code),
                ))
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: OutlinedButton(
                      onPressed: _pending ? null : () => _command(action),
                      child: Text(action.label),
                    ),
                  ),
              ],
              if (w.capability('account_configure') && a == null)
                OutlinedButton(
                  onPressed: _pending
                      ? null
                      : () => _command(TreasuryAction.accountConfigure),
                  child: const Text('Configure account'),
                ),
            ],
          ],
        ),
      ),
    );
  }
}

class TreasuryRecordSummary extends StatelessWidget {
  const TreasuryRecordSummary({required this.record, this.label, super.key});
  final Map<String, dynamic> record;
  final String? label;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      if (label != null)
        Text(label!, style: Theme.of(context).textTheme.titleSmall),
      for (final key in [
        'alias',
        'status',
        'customer_status',
        'amount',
        'remaining_amount',
        'applied_amount',
        'refunded_amount',
        'reference',
        'provider',
        'direction',
        'purpose',
        'classification',
        'original_classification',
        'corrected',
        'verification',
        'effective_at',
        'verified_at',
        'coverage_start',
        'cutoff',
        'as_of',
        'last_verified_at',
        'ledger_context_id',
        'account_id',
        'actual_balance',
        'expected_balance',
        'difference',
        'message',
        'blocker',
        'opening_id',
        'opening_cutoff',
        'verified_at',
        'unapplied_amount',
        'movement_watermark',
        'transit_amount',
        'loan_type',
        'component',
        'applied_amount',
        'unallocated_amount',
        'loan_id',
        'source_kind',
        'source_id',
        'destination_confirmed',
        'version',
        'id',
      ])
        if (record[key] != null)
          TreasurySelectableText('${key.replaceAll('_', ' ')}: ${record[key]}'),
      if (record['balance'] is Map)
        TreasuryRecordSummary(
          record: treasuryObject(record['balance']),
          label: 'Server balance',
        ),
      if (record['blockers'] is List)
        for (final b in record['blockers'] as List)
          Text(treasuryBlockerMessage(b)),
      if (record['source_link'] is Map)
        TreasuryRecordSummary(
          record: treasuryObject(record['source_link']),
          label: 'Existing source execution',
        ),
      if (record['revisions'] is List)
        for (final revision
            in (record['revisions'] as List).whereType<Map<String, dynamic>>())
          TreasuryRecordSummary(record: revision, label: 'Recorded correction'),
      if (record['incomplete_transfer_ids'] is List &&
          (record['incomplete_transfer_ids'] as List).isNotEmpty)
        const Text('Destination confirmation remains incomplete.'),
      if (record['purpose_exception_event_ids'] is List &&
          (record['purpose_exception_event_ids'] as List).isNotEmpty)
        const Text('Purpose exceptions remain separately visible.'),
    ],
  );
}

class TreasuryRecordPage extends StatefulWidget {
  const TreasuryRecordPage({
    required this.repository,
    required this.kind,
    required this.id,
    this.documentSaver = saveClientDocument,
    super.key,
  });
  final TreasuryRepository repository;
  final TreasuryListKind kind;
  final String id;
  final ClientDocumentSaver documentSaver;
  @override
  State<TreasuryRecordPage> createState() => _TreasuryRecordPageState();
}

class _TreasuryRecordPageState extends State<TreasuryRecordPage> {
  Map<String, dynamic>? _record;
  String? _error;
  bool _loading = true;
  int _generation = 0;
  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _generation++;
    super.dispose();
  }

  Future<void> _load() async {
    final g = ++_generation;
    setState(() => _loading = true);
    try {
      await widget.repository.loadWorkspace();
      final value = await widget.repository.detail(widget.kind, widget.id);
      if (mounted && g == _generation) {
        setState(() {
          _record = value;
          _error = null;
        });
      }
    } catch (error) {
      if (mounted && g == _generation) {
        setState(() {
          _error = error.toString();
          if (widget.repository.denied) _record = null;
        });
      }
    } finally {
      if (mounted && g == _generation) setState(() => _loading = false);
    }
  }

  Future<void> _open(Widget page) async {
    await Navigator.push<void>(
      context,
      MaterialPageRoute(builder: (_) => page),
    );
    if (mounted) setState(() {});
  }

  Future<void> _export() async {
    final approved = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Save private reconciliation?'),
        content: const Text(
          'This file includes private account history and matching exceptions. Choose a trusted destination.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Choose destination'),
          ),
        ],
      ),
    );
    if (!mounted || approved != true) return;
    final g = ++_generation;
    setState(() => _loading = true);
    try {
      final file = await widget.repository.exportReconciliation(widget.id);
      try {
        if (!mounted || g != _generation) return;
        final saved = await widget.documentSaver(file);
        if (mounted && g == _generation) {
          setState(
            () => _error = saved
                ? 'Private reconciliation saved.'
                : 'Save cancelled.',
          );
        }
      } finally {
        file.bytes.fillRange(0, file.bytes.length, 0);
      }
    } catch (error) {
      if (mounted && g == _generation) {
        setState(() {
          _error = error.toString();
          if (widget.repository.denied) _record = null;
        });
      }
    } finally {
      if (mounted && g == _generation) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final r = _record;
    final a = r == null
        ? null
        : widget.repository.workspace?.account(
            r['account_id'] as String? ?? '',
          );
    final claim = widget.kind == TreasuryListKind.claims;
    final current = r?['current_version'] is Map
        ? treasuryObject(r!['current_version'])
        : null;
    final pending =
        widget.repository.busy || widget.repository.pendingRequestId != null;
    return Scaffold(
      appBar: AppBar(
        toolbarHeight: MediaQuery.textScalerOf(
          context,
        ).scale(56).clamp(56, 112).toDouble(),
        title: Text(
          claim
              ? 'Payment proof'
              : widget.kind == TreasuryListKind.receipts
              ? 'Received funds'
              : 'Reconciliation',
        ),
        actions: [
          IconButton(
            tooltip: 'Refresh selected record',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (_loading) const LinearProgressIndicator(),
            if (_error != null) Text(_error!),
            if (r != null) ...[
              TreasuryRecordSummary(record: r),
              if (widget.kind == TreasuryListKind.reconciliations &&
                  a?.balance != null &&
                  a?.permits('reconciliation_observe') == true)
                OutlinedButton(
                  onPressed: _loading ? null : _export,
                  child: const Text('Save private reconciliation'),
                ),
              if (claim) ...[
                const Text(
                  'Proof review does not record a loan payment. Recipient funds must be verified before official recording.',
                ),
                if (current != null) ...[
                  TreasurySelectableText('PHP ${current['amount']}'),
                  TreasuryRecordSummary(record: current),
                  if (current['media_type'] is String)
                    OutlinedButton(
                      onPressed: () => _open(
                        TreasuryPrivateFilePage(
                          repository: widget.repository,
                          claimId: widget.id,
                          version:
                              current['version'] as int? ?? r['version'] as int,
                          mediaType: current['media_type'] as String,
                          digest: current['sha256'] as String?,
                          byteCount: current['byte_count'] as int?,
                        ),
                      ),
                      child: const Text('View private proof'),
                    ),
                ],
                if (r['official_payment_posted'] == true)
                  const Text('Official loan payment recorded.')
                else if (r['receipt'] != null)
                  const Text(
                    'Received funds may remain unapplied. Check the linked receipt.',
                  ),
                if (r['receipt'] is Map &&
                    treasuryUuid((r['receipt'] as Map)['id']))
                  OutlinedButton(
                    onPressed: () => _open(
                      TreasuryRecordPage(
                        repository: widget.repository,
                        kind: TreasuryListKind.receipts,
                        id: (r['receipt'] as Map)['id'] as String,
                      ),
                    ),
                    child: const Text('Open received funds'),
                  ),
                if (a?.permits('claim_version') == true)
                  OutlinedButton(
                    onPressed: pending
                        ? null
                        : () => _open(
                            TreasuryClaimPage(
                              repository: widget.repository,
                              account: a!,
                              claim: r,
                              borrowerChoices: [
                                {
                                  'client_id': r['client_id'],
                                  'name': 'Current borrower',
                                  'loans': [
                                    for (final id
                                        in (current?['loan_ids'] as List?) ??
                                            [])
                                      {'loan_id': id, 'loan_number': id},
                                  ],
                                },
                              ],
                            ),
                          ),
                    child: const Text('Correct payment proof'),
                  ),
              ],
              if (widget.kind == TreasuryListKind.receipts) ...[
                const Text(
                  'Manual recipient verification is separate from loan recording. Unapplied funds remain received if recording fails.',
                ),
                if (a?.permits('receipt_apply') == true)
                  FilledButton(
                    onPressed: pending
                        ? null
                        : () => _open(
                            TreasuryCommandPage(
                              repository: widget.repository,
                              account: a,
                              action: TreasuryAction.receiptApply,
                              targetId: widget.id,
                              initial: {
                                'receipt_id': widget.id,
                                'expected_version': r['version'],
                                'total_amount': r['remaining_amount'],
                                'loan_choices': r['loan_choices'],
                              },
                            ),
                          ),
                    child: const Text('Prepare loan application'),
                  ),
              ],
              if (a != null)
                for (final action in [
                  if (claim) TreasuryAction.claimReview,
                  if (claim) TreasuryAction.receiptVerify,
                  if (widget.kind == TreasuryListKind.reconciliations)
                    TreasuryAction.reconciliationMatch,
                  if (widget.kind == TreasuryListKind.reconciliations &&
                      r['can_close'] == true)
                    TreasuryAction.reconciliationClose,
                  if (widget.kind == TreasuryListKind.reconciliations)
                    TreasuryAction.reconciliationSupersede,
                ].where((v) => a.permits(v.code)))
                  OutlinedButton(
                    onPressed: pending
                        ? null
                        : () => _open(
                            TreasuryCommandPage(
                              repository: widget.repository,
                              account: a,
                              action: action,
                              initial: {
                                if (claim) 'claim_id': widget.id,
                                if (claim) 'claim_version': r['version'],
                                if (claim) 'client_id': r['client_id'],
                                if (current != null)
                                  'amount': current['amount'],
                                if (widget.kind ==
                                    TreasuryListKind.reconciliations)
                                  'reconciliation_id': widget.id,
                                if (widget.kind ==
                                    TreasuryListKind.reconciliations)
                                  'reconciliation_version': r['version'],
                                if (widget.kind ==
                                    TreasuryListKind.reconciliations)
                                  'opening_id': r['opening_id'],
                                if (widget.kind ==
                                    TreasuryListKind.reconciliations)
                                  'movement_watermark': r['movement_watermark'],
                              },
                            ),
                          ),
                    child: Text(action.label),
                  ),
              if (r['history'] is List)
                for (final version
                    in (r['history'] as List).whereType<Map<String, dynamic>>())
                  TreasuryRecordSummary(
                    record: version,
                    label: 'Retained proof version',
                  ),
              if (r['observations'] is List)
                for (final row
                    in (r['observations'] as List)
                        .whereType<Map<String, dynamic>>())
                  TreasuryRecordSummary(
                    record: row,
                    label: 'Statement transaction',
                  ),
              if (r['matches'] is List)
                for (final row
                    in (r['matches'] as List).whereType<Map<String, dynamic>>())
                  TreasuryRecordSummary(
                    record: row,
                    label: 'Existing movement match',
                  ),
              if (r['closed_snapshot'] is Map)
                TreasuryRecordSummary(
                  record: treasuryObject(r['closed_snapshot']),
                  label: 'Immutable closed snapshot',
                ),
            ],
          ],
        ),
      ),
    );
  }
}

class TreasuryPrivateFilePage extends StatefulWidget {
  const TreasuryPrivateFilePage({
    required this.repository,
    required this.mediaType,
    this.claimId,
    this.version,
    this.evidenceId,
    this.digest,
    this.byteCount,
    super.key,
  });
  final TreasuryRepository repository;
  final String mediaType;
  final String? claimId, evidenceId, digest;
  final int? version, byteCount;
  @override
  State<TreasuryPrivateFilePage> createState() =>
      _TreasuryPrivateFilePageState();
}

class _TreasuryPrivateFilePageState extends State<TreasuryPrivateFilePage> {
  Uint8List? _bytes;
  MemoryImage? _image;
  String? _error;
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final bytes = await widget.repository.content(
        claimId: widget.claimId,
        version: widget.version,
        evidenceId: widget.evidenceId,
        mediaType: widget.mediaType,
        digest: widget.digest,
        byteCount: widget.byteCount,
      );
      if (mounted) {
        setState(() {
          _bytes = bytes;
          if (widget.mediaType != 'application/pdf') {
            _image = MemoryImage(bytes);
          }
        });
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  @override
  void dispose() {
    _image?.evict();
    _bytes?.fillRange(0, _bytes!.length, 0);
    _bytes = null;
    _image = null;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      toolbarHeight: MediaQuery.textScalerOf(
        context,
      ).scale(56).clamp(56, 112).toDouble(),
      title: const Text('Private evidence'),
    ),
    body: SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            'Private evidence is kept out of screen sharing and public downloads.',
          ),
          if (_error != null)
            Text(_error!)
          else if (_bytes == null)
            const LinearProgressIndicator()
          else if (_image != null)
            Image(
              image: _image!,
              fit: BoxFit.contain,
              errorBuilder: (_, __, ___) => const Text(
                'This image could not be decoded. Review another valid file.',
              ),
            )
          else
            Text(
              'Private PDF verified (${_bytes!.length} bytes). PDF pages cannot be previewed in this native viewer.',
            ),
        ],
      ),
    ),
  );
}

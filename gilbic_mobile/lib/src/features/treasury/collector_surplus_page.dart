import 'dart:typed_data';
import 'package:file_selector/file_selector.dart' as files;
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/formatting/spina_display.dart';
import 'package:gilbic_mobile/src/core/media/image_recovery_controller.dart';
import 'package:gilbic_mobile/src/features/shared/image_recovery_scope.dart';
import 'package:gilbic_mobile/src/core/treasury/collector_surplus_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_repository.dart';
import 'package:gilbic_mobile/src/core/time/spina_business_time.dart';
import 'package:gilbic_mobile/src/features/treasury/treasury_selectable_text.dart';
import 'package:gilbic_mobile/src/features/treasury/treasury_workspace_page.dart';
import 'package:image_picker/image_picker.dart';
import 'package:file_saver/file_saver.dart';

String collectorDispositionLabel(String code) => switch (code) {
  'outstanding' => 'Outstanding Collector credit',
  'settled' => 'Collector credit settled',
  'pending_identification' => 'Excess pending identification',
  'resolved' => 'Identification resolved',
  'held_disputed' => 'Disputed cash remains held',
  'partly_reversed' => 'Return partly reversed by verified incoming cash',
  'reversed' => 'Return reversed by verified incoming cash',
  'draft' => 'Prepared opening classification',
  'active' => 'Active opening classification',
  'counted_ready' => 'Count recorded - acceptance still required',
  'counted_short_rejected' => 'Short count rejected - cash not accepted',
  'accepted_exact' => 'Exact physical cash accepted',
  'accepted_pending_identification' =>
    'Physical cash accepted - excess pending identification',
  'recognized' => 'Collector credit recognized - no additional cash received',
  'requested' =>
    'Request recorded - approval and actual payment remain separate',
  'reserved' => 'Amount reserved - no payment recorded',
  'return_reversed' =>
    'Actual incoming reversal verified - original debit retained',
  'debited_confirmation_pending' || 'return_debited_confirmation_pending' =>
    'Return debited - confirmation pending',
  'acknowledged_received' =>
    'Receipt acknowledged - independent settlement still required',
  'acknowledged_not_received' => 'Not received - return remains pending',
  'paid' => 'Collector return paid',
  'exception_returned' => 'Disputed retained cash returned',
  'cancelled' => 'Reservation cancelled - no cash movement',
  'opening_prepared' => 'Opening classification prepared - no additional cash',
  'opening_activated' =>
    'Opening classification activated - no additional cash',
  'custody_exception_recorded' =>
    'Actual disputed cash retained - full remittance not accepted',
  'recovery_required' => 'Reclassification requires recovery decision',
  'blocked_adapter' => 'This action is currently unavailable',
  'actual_debit_source_unresolved' =>
    'Debit recorded - approved return remains unresolved',
  _ => code.replaceAll('_', ' '),
};

class CollectorSurplusPage extends StatefulWidget {
  const CollectorSurplusPage({
    required this.session,
    this.repository,
    this.deviceIdentityProvider,
    this.focusRemittanceId,
    this.ownMode = false,
    super.key,
  });
  final UserSession session;
  final CollectorSurplusRepository? repository;
  final DeviceIdentityProvider? deviceIdentityProvider;
  final String? focusRemittanceId;
  final bool ownMode;
  @override
  State<CollectorSurplusPage> createState() => _CollectorSurplusPageState();
}

class _CollectorSurplusPageState extends State<CollectorSurplusPage> {
  CollectorSurplusRepository? _repo;
  CollectorSurplusWorkspace? _workspace;
  CollectorSurplusKind _kind = CollectorSurplusKind.credits;
  List<CollectorSurplusAccount> _accounts = [];
  String? _accountId, _error;
  bool _loading = true;
  int _offset = 0, _generation = 0;
  bool get _locked =>
      _loading ||
      _repo?.busy == true ||
      _repo?.denied == true ||
      _repo?.pendingRequestId != null;
  @override
  void initState() {
    super.initState();
    if (widget.focusRemittanceId != null) {
      _kind = CollectorSurplusKind.remittances;
    }
    _initialize();
  }

  Future<void> _initialize() async {
    try {
      if (widget.repository != null) {
        _repo = widget.repository;
      } else {
        final identity =
            await (widget.deviceIdentityProvider ?? DeviceIdentityProvider())
                .load();
        if (!mounted) return;
        _repo = SpinaTreasuryRepository(
          session: widget.session,
          deviceId: identity.installationId,
          getSession: () => mounted ? widget.session : null,
        );
      }
      await _refresh(restore: true);
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          _loading = false;
        });
      }
    }
  }

  @override
  void dispose() {
    _generation++;
    if (widget.repository == null) _repo?.dispose();
    super.dispose();
  }

  Future<void> _refresh({bool restore = false}) async {
    final generation = ++_generation;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final full = await _repo!.loadCollectorSurplus(
        kind: _kind,
        mode: widget.ownMode ? 'own' : null,
      );
      if (!mounted || generation != _generation) return;
      _accounts = full.accounts;
      if (_accountId != null && full.account(_accountId!) == null) {
        _accountId = null;
      }
      final page = (_accountId != null || _offset != 0)
          ? await _repo!.loadCollectorSurplus(
              kind: _kind,
              accountId: _accountId,
              offset: _offset,
            )
          : full;
      if (restore) await _repo!.restoreAttempt();
      if (!mounted || generation != _generation) return;
      setState(() => _workspace = page);
    } catch (e) {
      if (mounted && generation == _generation) {
        setState(() {
          _error = e.toString();
          if (_repo?.denied == true) {
            _workspace = null;
            _accounts = [];
          }
        });
      }
    } finally {
      if (mounted && generation == _generation) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _recover({bool retry = false}) async {
    if (retry) {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: const Text('Retry unchanged request?'),
          content: const Text(
            'Only the exact submitted phase and evidence will be resent. This does not release a reservation or resend a provider transfer.',
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
    try {
      final result = retry ? await _repo!.retrySame() : await _repo!.recover();
      if (mounted) {
        setState(
          () => _error = result == null
              ? 'Request remains unconfirmed. No new payment or cancellation is permitted.'
              : collectorDispositionLabel(
                  result.result['disposition'] as String? ?? result.status,
                ),
        );
      }
      await _refresh();
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  Future<void> _open(Widget page) async {
    await Navigator.push<void>(
      context,
      MaterialPageRoute(builder: (_) => page),
    );
    if (mounted) await _refresh();
  }

  Future<void> _record(Map<String, dynamic> row) async {
    try {
      final record =
          _kind == CollectorSurplusKind.remittances ||
              _kind == CollectorSurplusKind.openings
          ? row
          : await _repo!.collectorSurplusDetail(_kind, row['id'] as String);
      if (!mounted) return;
      await _open(
        CollectorSurplusRecordPage(
          repository: _repo!,
          kind: _kind,
          record: record,
        ),
      );
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  Future<void> _export() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('Save private Collector history?'),
        content: const Text(
          'Choose a trusted destination. This report contains only your current authorized scope.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(c, true),
            child: const Text('Save private report'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    try {
      final file = await _repo!.exportCollectorSurplus(
        kind: _kind,
        accountId: _accountId,
      );
      try {
        await FileSaver.instance.saveAs(
          name: file.filename,
          bytes: file.bytes,
          fileExtension: 'json',
          mimeType: MimeType.json,
        );
      } finally {
        file.bytes.fillRange(0, file.bytes.length, 0);
      }
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  Future<void> _opening() async {
    final w = _workspace;
    if (w == null) return;
    final choices = (w.raw['opening_choices'] as List? ?? [])
        .whereType<Map<String, dynamic>>()
        .toList();
    final collectors = (w.raw['collector_choices'] as List)
        .whereType<Map<String, dynamic>>()
        .toList();
    if (choices.isEmpty || collectors.isEmpty) {
      setState(
        () => _error =
            'No current authorized physical opening and Collector choices were returned.',
      );
      return;
    }
    final selected = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (c) => SimpleDialog(
        title: const Text('Choose evidenced opening and Collector'),
        children: [
          for (final opening in choices)
            for (final collector in collectors)
              SimpleDialogOption(
                onPressed: () => Navigator.pop(c, {
                  'opening': opening,
                  'collector': collector,
                }),
                child: Text(
                  '${collector['full_name'] ?? collector['name'] ?? collector['id']} - ${opening['cutoff']}',
                ),
              ),
        ],
      ),
    );
    if (selected == null || !mounted) return;
    final opening = selected['opening'] as Map,
        collector = selected['collector'] as Map;
    final account = w.account(opening['account_id'] as String);
    if (account == null) return;
    await _open(
      CollectorSurplusActionForm(
        repository: _repo!,
        action: TreasuryAction.collectorSurplusOpeningPrepare,
        account: account,
        initial: {
          'opening_id': opening['id'],
          'opening_version': opening['version'],
          'collector_user_id': collector['id'],
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final w = _workspace;
    final rows = (w?.page.items ?? [])
        .where(
          (r) =>
              widget.focusRemittanceId == null ||
              _kind != CollectorSurplusKind.remittances ||
              r['id'] == widget.focusRemittanceId,
        )
        .toList();
    return Scaffold(
      appBar: AppBar(
        toolbarHeight: MediaQuery.textScalerOf(
          context,
        ).scale(56).clamp(56, 112).toDouble(),
        title: Text(w?.mode == 'own' ? 'My excess credit' : 'Collector Excess'),
        actions: [
          IconButton(
            onPressed: _loading ? null : () => _refresh(),
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh authorized history',
          ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const Text(
              'Counted cash, accepted cash, pending identification and confirmed credit are separate. No automatic offset or provider transfer.',
            ),
            if (_loading) const LinearProgressIndicator(),
            if (_error != null) Text(_error!),
            if (_repo?.pendingRequestId != null) ...[
              const Text('Unconfirmed submitted phase'),
              TreasurySelectableText(_repo!.pendingRequestId!),
              const Text(
                'Check this exact request before another submission. Restarting does not resend.',
              ),
              Wrap(
                spacing: 8,
                children: [
                  OutlinedButton(
                    onPressed: _loading ? null : () => _recover(),
                    child: const Text('Check request'),
                  ),
                  TextButton(
                    onPressed: _loading ? null : () => _recover(retry: true),
                    child: const Text('Retry unchanged'),
                  ),
                ],
              ),
            ],
            if (w != null) ...[
              for (final blocker in w.blockers) Text(_plainBlocker(blocker)),
              if (w.raw['readiness']['enabled'] != true)
                const Text(
                  'New entry is disabled. Existing history and pending returns remain visible.',
                ),
              DropdownButtonFormField<CollectorSurplusKind>(
                key: ValueKey(_kind),
                initialValue: _kind,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Local view'),
                items: [
                  for (final k in CollectorSurplusKind.values)
                    DropdownMenuItem(
                      value: k,
                      child: Text(
                        k == CollectorSurplusKind.cases
                            ? 'Pending identification'
                            : k.name.replaceAll('_', ' '),
                      ),
                    ),
                ],
                onChanged: _loading
                    ? null
                    : (k) {
                        if (k == null) return;
                        setState(() {
                          _kind = k;
                          _offset = 0;
                        });
                        _refresh();
                      },
              ),
              if (w.mode == 'staff' && _accounts.isNotEmpty)
                DropdownButtonFormField<String>(
                  key: ValueKey(_accountId),
                  initialValue: _accountId,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Authorized account',
                  ),
                  items: [
                    const DropdownMenuItem(
                      value: null,
                      child: Text('All authorized accounts'),
                    ),
                    for (final a in _accounts)
                      DropdownMenuItem(
                        value: a.id,
                        child: Text(a.alias, overflow: TextOverflow.ellipsis),
                      ),
                  ],
                  onChanged: _loading
                      ? null
                      : (id) {
                          setState(() {
                            _accountId = id;
                            _offset = 0;
                          });
                          _refresh();
                        },
                ),
              const SizedBox(height: 12),
              Text('${w.page.totalCount} records - server totals'),
              for (final e in (w.page.totals ?? {}).entries)
                TreasurySelectableText(
                  '${e.key.replaceAll('_', ' ')}: PHP ${e.value}',
                ),
              if (rows.isEmpty)
                const Text('No authorized records in this view.'),
              for (final row in rows)
                Card(
                  child: ListTile(
                    title: Text(
                      collectorDispositionLabel(
                        (row['disposition'] ?? row['status'] ?? 'record')
                            as String,
                      ),
                    ),
                    subtitle: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        TreasurySelectableText(
                          row['remittance_number'] as String? ??
                              row['id'] as String,
                        ),
                        for (final key in collectorSurplusAmounts)
                          if (row[key] != null)
                            TreasurySelectableText(
                              '${key.replaceAll('_', ' ')}: PHP ${row[key]}',
                            ),
                      ],
                    ),
                    onTap: () => _record(row),
                  ),
                ),
              Wrap(
                spacing: 8,
                children: [
                  if (_offset > 0)
                    OutlinedButton(
                      onPressed: _loading
                          ? null
                          : () {
                              _offset = (_offset - 50).clamp(0, 100000);
                              _refresh();
                            },
                      child: const Text('Previous'),
                    ),
                  if (w.page.hasMore)
                    OutlinedButton(
                      onPressed: _loading
                          ? null
                          : () {
                              _offset += 50;
                              _refresh();
                            },
                      child: const Text('Next'),
                    ),
                  OutlinedButton(
                    onPressed: _locked ? null : _export,
                    child: const Text('Save private history'),
                  ),
                  if (w.mode == 'staff' && w.capability('opening_prepare'))
                    OutlinedButton(
                      onPressed: _locked ? null : _opening,
                      child: const Text('Prepare opening credit'),
                    ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class CollectorSurplusRecordPage extends StatefulWidget {
  const CollectorSurplusRecordPage({
    required this.repository,
    required this.kind,
    required this.record,
    super.key,
  });
  final CollectorSurplusRepository repository;
  final CollectorSurplusKind kind;
  final Map<String, dynamic> record;
  @override
  State<CollectorSurplusRecordPage> createState() =>
      _CollectorSurplusRecordPageState();
}

class _CollectorSurplusRecordPageState
    extends State<CollectorSurplusRecordPage> {
  late Map<String, dynamic> _record;
  CollectorSettlementPreview? _preview;
  String? _accountId, _error;
  bool _busy = false;
  bool get _locked =>
      _busy ||
      widget.repository.busy ||
      widget.repository.denied ||
      widget.repository.pendingRequestId != null;
  @override
  void initState() {
    super.initState();
    _record = widget.record;
    _accountId =
        (_record['paying_account_id'] ??
                _record['account_id'] ??
                _record['origin_account_id'])
            as String?;
  }

  Future<void> _open(
    TreasuryAction action,
    Map<String, dynamic> initial, {
    CollectorSurplusAccount? account,
  }) async {
    await Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) => CollectorSurplusActionForm(
          repository: widget.repository,
          action: action,
          account: account,
          initial: initial,
          reviewLabel:
              '${_record['remittance_number'] ?? collectorDispositionLabel((_record['disposition'] ?? _record['status']) as String)}${_record['collection_date'] == null ? '' : ' / ${_record['collection_date']}'}',
        ),
      ),
    );
    if (!mounted) return;
    try {
      if (widget.kind != CollectorSurplusKind.remittances &&
          widget.kind != CollectorSurplusKind.openings) {
        _record = await widget.repository.collectorSurplusDetail(
          widget.kind,
          _record['id'] as String,
        );
      }
      if (mounted) setState(() {});
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          if (widget.repository.denied) _record = {};
        });
      }
    }
  }

  Future<void> _countPreview() async {
    if (_locked || _accountId == null) return;
    setState(() => _busy = true);
    try {
      final p = await widget.repository.collectorSettlementPreview(
        _record['id'] as String,
        _accountId!,
      );
      if (mounted) setState(() => _preview = p);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _prepareRequest() async {
    setState(() => _busy = true);
    try {
      final credit = await widget.repository.collectorSurplusDetail(
        CollectorSurplusKind.credits,
        _record['credit_id'] as String,
      );
      if (!mounted) return;
      final a = widget.repository.surplusWorkspace?.account(_accountId ?? '');
      if (a == null) throw StateError('Choose an authorized paying account.');
      await _open(
        _record['kind'] == 'application'
            ? TreasuryAction.collectorSurplusApplicationPrepare
            : TreasuryAction.collectorSurplusReturnPrepare,
        {
          'credit_id': credit['id'],
          'credit_version': credit['version'],
          'collector_request_id': _record['id'],
          'collector_request_version': _record['version'],
          'amount': _record['amount'],
          if (_record['kind'] == 'return')
            'destination': _record['destination'],
          if (_record['kind'] == 'application') ...{
            'remittance_id': _record['remittance_id'],
            'source_digest': _record['source_digest'],
          },
        },
        account: a,
      );
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _acknowledge() async {
    final exception = _record['kind'] == 'exception_return';
    final target = await widget.repository.collectorSurplusDetail(
      exception
          ? CollectorSurplusKind.exceptions
          : CollectorSurplusKind.credits,
      _record[exception ? 'exception_id' : 'credit_id'] as String,
    );
    if (!mounted) return;
    await _open(
      exception
          ? TreasuryAction.collectorCustodyExceptionReturnAcknowledge
          : TreasuryAction.collectorSurplusReturnAcknowledge,
      {
        'action_id': _record['id'],
        'action_version': _record['version'],
        'event_id': _record['event_id'],
        'event_version': _record['event_version'],
        'reviewed_amount': _record['amount'],
        exception ? 'exception_id' : 'credit_id': target['id'],
        exception ? 'exception_version' : 'credit_version': target['version'],
      },
    );
  }

  Future<void> _applicationIntent() async {
    try {
      final w = await widget.repository.loadCollectorSurplus(
        kind: CollectorSurplusKind.remittances,
      );
      if (!mounted) return;
      final choices = w.page.items
          .where(
            (r) =>
                r['application_request_supported'] == true &&
                r['source_digest'] is String,
          )
          .toList();
      if (choices.isEmpty) {
        throw StateError(
          'No protected same-Collector application target is available. Execution remains blocked.',
        );
      }
      final target = await showDialog<Map<String, dynamic>>(
        context: context,
        builder: (c) => SimpleDialog(
          title: const Text('Choose current remittance intent'),
          children: [
            for (final row in choices)
              SimpleDialogOption(
                onPressed: () => Navigator.pop(c, row),
                child: Text(
                  row['remittance_number'] as String? ?? row['id'] as String,
                ),
              ),
          ],
        ),
      );
      if (target == null || !mounted) return;
      await _open(TreasuryAction.collectorSurplusApplicationRequest, {
        'credit_id': _record['id'],
        'credit_version': _record['version'],
        'remittance_id': target['id'],
        'source_digest': target['source_digest'],
      });
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    final w = widget.repository.surplusWorkspace, r = _record;
    final own = w?.mode == 'own';
    final a = w?.account(_accountId ?? '');
    Widget action(String label, String cap, VoidCallback run) => OutlinedButton(
      onPressed: _locked || w?.capability(cap) != true ? null : run,
      child: Text(label),
    );
    return Scaffold(
      appBar: AppBar(
        toolbarHeight: MediaQuery.textScalerOf(
          context,
        ).scale(56).clamp(56, 112).toDouble(),
        title: const Text('Collector record'),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (_busy) const LinearProgressIndicator(),
            if (_error != null) Text(_error!),
            if (r.isNotEmpty) ...[
              Text(
                collectorDispositionLabel(
                  (r['disposition'] ?? r['status']) as String,
                ),
              ),
              ..._recordFacts(r),
              if (widget.kind == CollectorSurplusKind.remittances &&
                  r['source_digest'] == null)
                const Text(
                  'Current source evidence unavailable. Credit application intent is disabled.',
                ),
              if (!own && w != null)
                DropdownButtonFormField<String>(
                  key: ValueKey(_accountId),
                  initialValue: w.account(_accountId ?? '') != null
                      ? _accountId
                      : null,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Authorized receiving / paying account',
                  ),
                  items: [
                    for (final account in w.accounts)
                      DropdownMenuItem(
                        value: account.id,
                        child: Text(
                          account.alias,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                  ],
                  onChanged: _locked
                      ? null
                      : (id) => setState(() {
                          _accountId = id;
                          _preview = null;
                        }),
                ),
              if (widget.kind == CollectorSurplusKind.remittances && !own) ...[
                action(
                  'Review current count snapshot',
                  'count_record',
                  _countPreview,
                ),
                if (_preview != null) ...[
                  ..._recordFacts(_preview!.raw),
                  for (final blocker in _preview!.blockers)
                    Text(_plainBlocker(blocker)),
                  if (_preview!.canCount && a != null)
                    action(
                      'Record actual cash count',
                      'count_record',
                      () => _open(TreasuryAction.collectorCountRecord, {
                        'remittance_id': r['id'],
                        'source_digest': _preview!.digest,
                      }, account: a),
                    ),
                ],
              ],
              if (widget.kind == CollectorSurplusKind.counts &&
                  !own &&
                  a != null) ...[
                if (r['disposition'] == 'counted_ready')
                  action(
                    'Accept reviewed physical cash',
                    'count_accept',
                    () => _open(TreasuryAction.collectorCountAccept, {
                      'count_id': r['id'],
                      'count_version': r['version'],
                      'source_digest': r['source_digest'],
                    }, account: a),
                  ),
                if (r['disposition'] == 'counted_short_rejected') ...[
                  const Text(
                    'Rejected count does not clear custody. Record retained cash only if it was actually held during the dispute.',
                  ),
                  action(
                    'Record actual disputed cash retained',
                    'exception_record',
                    () =>
                        _open(TreasuryAction.collectorCustodyExceptionRecord, {
                          'count_id': r['id'],
                          'count_version': r['version'],
                          'source_digest': r['source_digest'],
                        }, account: a),
                  ),
                ],
              ],
              if (widget.kind == CollectorSurplusKind.cases &&
                  !own &&
                  a != null)
                action(
                  'Recognize evidenced Collector credit',
                  'recognize',
                  () => _open(TreasuryAction.collectorSurplusRecognize, {
                    'case_id': r['id'],
                    'case_version': r['version'],
                    'source_digest': r['source_digest'],
                  }, account: a),
                ),
              if (widget.kind == CollectorSurplusKind.credits && own) ...[
                action(
                  'Request partial or full return',
                  'return_request',
                  () => _open(TreasuryAction.collectorSurplusReturnRequest, {
                    'credit_id': r['id'],
                    'credit_version': r['version'],
                  }),
                ),
                action(
                  'Request later remittance application',
                  'application_request',
                  _applicationIntent,
                ),
              ],
              if (widget.kind == CollectorSurplusKind.requests && !own)
                action(
                  'Review independent preparation',
                  r['kind'] == 'application'
                      ? 'application_prepare'
                      : 'return_prepare',
                  _prepareRequest,
                ),
              if (widget.kind == CollectorSurplusKind.exceptions &&
                  !own &&
                  a != null)
                action(
                  'Prepare actual custody return',
                  'exception_return_prepare',
                  () => _open(
                    TreasuryAction.collectorCustodyExceptionReturnPrepare,
                    {
                      'exception_id': r['id'],
                      'exception_version': r['version'],
                    },
                    account: a,
                  ),
                ),
              if (widget.kind == CollectorSurplusKind.actions) ...[
                if (own && r['status'] == 'debited_confirmation_pending')
                  action(
                    'Acknowledge actual received / not received',
                    r['kind'] == 'exception_return'
                        ? 'exception_acknowledge'
                        : 'return_acknowledge',
                    _acknowledge,
                  ),
                if (!own && a != null && r['status'] == 'reserved') ...[
                  action(
                    'Record actual outgoing observation',
                    'return_record',
                    () => _open(TreasuryAction.disbursementRecord, {
                      'source_id': r['id'],
                      'source_version': r['version'],
                      'payee_id': r['collector_user_id'],
                      'amount': r['amount'],
                      'provider': a.kind,
                      'direction': 'debit',
                      'purpose': r['kind'] == 'exception_return'
                          ? 'collector_custody_exception_return'
                          : 'collector_surplus_return',
                    }, account: a),
                  ),
                  action(
                    'Cancel proven unpaid reservation',
                    'action_cancel',
                    () => _open(TreasuryAction.collectorSurplusActionCancel, {
                      'action_id': r['id'],
                      'action_version': r['version'],
                    }, account: a),
                  ),
                ],
                if (!own &&
                    a != null &&
                    r['status'] == 'debited_confirmation_pending') ...[
                  const Text(
                    'Actual debit remains reserved until the recipient acknowledgment and independent settlement are confirmed. Do not resend.',
                  ),
                  if (r['acknowledgment'] is Map &&
                      r['acknowledgment']['confirmation'] == 'received')
                    action(
                      'Confirm independent return settlement',
                      'return_record',
                      () => _open(TreasuryAction.collectorSurplusReturnRecord, {
                        'action_id': r['id'],
                        'action_version': r['version'],
                        'event_id': r['event_id'],
                        'event_version': r['event_version'],
                        'acknowledgment_id': r['acknowledgment']['id'],
                        'acknowledgment_version':
                            r['acknowledgment']['version'],
                      }, account: a),
                    ),
                ],
              ],
              if (widget.kind == CollectorSurplusKind.actions &&
                  !own &&
                  a != null &&
                  r['kind'] == 'return' &&
                  ['paid', 'partly_reversed'].contains(r['status']))
                action(
                  'Record actual incoming return reversal',
                  'return_reverse',
                  () => _open(TreasuryAction.collectorSurplusReturnReverse, {
                    'action_id': r['id'],
                    'action_version': r['version'],
                    'provider': a.kind,
                  }, account: a),
                ),
              if (widget.kind == CollectorSurplusKind.openings &&
                  !own &&
                  a != null &&
                  r['status'] == 'draft')
                action(
                  'Activate evidenced opening classification',
                  'opening_activate',
                  () => _open(TreasuryAction.collectorSurplusOpeningActivate, {
                    'anchor_id': r['id'],
                    'anchor_version': r['version'],
                  }, account: a),
                ),
              const SizedBox(height: 12),
              const Text(
                'Historical payment corrections, applying credit to a later handover and accounting entries are currently unavailable. No automatic deduction or credit offset.',
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class CollectorSurplusActionForm extends StatefulWidget {
  const CollectorSurplusActionForm({
    required this.repository,
    required this.action,
    this.account,
    this.initial = const {},
    this.pickEvidence,
    this.reviewLabel,
    super.key,
  });
  final CollectorSurplusRepository repository;
  final TreasuryAction action;
  final CollectorSurplusAccount? account;
  final Map<String, dynamic> initial;
  final Future<XFile?> Function()? pickEvidence;
  final String? reviewLabel;
  @override
  State<CollectorSurplusActionForm> createState() =>
      _CollectorSurplusActionFormState();
}

class _CollectorSurplusActionFormState
    extends State<CollectorSurplusActionForm> {
  final _controllers = <String, TextEditingController>{};
  final _values = <String, dynamic>{};
  String? _error;
  Map<String, dynamic>? _evidence;
  TreasuryResult? _result;
  String _destinationKind = 'physical_cash';
  final _destinationReference = TextEditingController();
  bool _busy = false, _reviewed = false, _completed = false;
  bool get _locked =>
      _busy ||
      _completed ||
      widget.repository.busy ||
      widget.repository.denied ||
      widget.repository.pendingRequestId != null;
  List<TreasuryField> get _fields => treasuryFields[widget.action]!;
  @override
  void initState() {
    super.initState();
    for (final f in _fields) {
      final value = widget.initial[f.key] ?? f.defaultValue;
      if (f.kind == TreasuryFieldKind.boolean) {
        _values[f.key] = false;
      } else if (f.kind == TreasuryFieldKind.choice) {
        _values[f.key] = value;
      } else if (f.kind == TreasuryFieldKind.destination) {
        if (value is Map) {
          _destinationKind = value['kind'] as String;
          _destinationReference.text =
              value['recipient_reference'] as String? ?? '';
        }
      } else {
        _controllers[f.key] = TextEditingController(
          text: value?.toString() ?? '',
        );
      }
    }
  }

  @override
  void dispose() {
    for (final c in _controllers.values) {
      c.dispose();
    }
    _destinationReference.dispose();
    super.dispose();
  }

  void _changed() {
    setState(() {
      _reviewed = false;
      _result = null;
    });
  }

  String get _purpose =>
      widget.action == TreasuryAction.collectorSurplusOpeningPrepare
      ? 'opening'
      : 'recipient';
  bool _selecting = false;
  Future<void> _pick({bool camera = false}) async {
    if (_locked || widget.account == null) return;
    setState(() {
      _busy = true;
      _selecting = true;
    });
    Uint8List? ownedEvidenceBytes, reviewBuffer;
    MemoryImage? reviewedImage;
    try {
      final file = camera
          ? await pickRecoverableImage(
              context,
              recoveryContext: ImagePickContext(
                purpose: 'collector-surplus-${widget.action.code}',
                target:
                    '${widget.account!.id}:${widget.initial['credit_id'] ?? widget.initial['case_id'] ?? widget.initial['remittance_id'] ?? widget.initial['action_id'] ?? widget.initial['count_id'] ?? 'opening'}',
                label: 'Private Collector evidence',
              ),
              pick: () => ImagePicker().pickImage(source: ImageSource.camera),
            )
          : await (widget.pickEvidence ??
                () => files.openFile(
                  acceptedTypeGroups: [
                    const files.XTypeGroup(
                      label: 'Private evidence',
                      extensions: ['pdf', 'png', 'jpg', 'jpeg'],
                    ),
                  ],
                ))();
      if (file == null || !mounted) return;
      final media = await treasuryMediaType(file);
      final bytes = await file.readAsBytes();
      reviewBuffer = bytes;
      ownedEvidenceBytes = Uint8List.fromList(bytes);
      final frozen = XFile.fromData(
        ownedEvidenceBytes,
        name: file.name,
        mimeType: media,
      );
      if (!mounted) {
        bytes.fillRange(0, bytes.length, 0);
        return;
      }
      final privateImage = MemoryImage(bytes);
      reviewedImage = privateImage;
      final reviewed = await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: const Text('Review private evidence'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('${file.name} - $media - ${bytes.length} bytes'),
                if (media != 'application/pdf')
                  Image(
                    image: privateImage,
                    errorBuilder: (_, __, ___) => const Text(
                      'Image cannot be decoded; choose valid evidence.',
                    ),
                  )
                else
                  const Text(
                    'PDF bytes selected. Inline PDF page rendering is unavailable; review the source document before confirming.',
                  ),
                const Text(
                  'This retains the exact selected bytes. It does not prove a payment or accept custody.',
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(c, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(c, true),
              child: const Text('Evidence reviewed'),
            ),
          ],
        ),
      );
      await privateImage.evict();
      bytes.fillRange(0, bytes.length, 0);
      if (reviewed != true || !mounted) return;
      final result = await widget.repository.uploadEvidence(
        requestId: newTreasuryRequestId(),
        accountId: widget.account!.id,
        purpose: _purpose,
        file: frozen,
      );
      if (mounted) {
        setState(() {
          _evidence = treasuryObject(result.result['evidence']);
          _controllers['evidence_id']?.text = _evidence!['id'] as String;
          _reviewed = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          if (widget.repository.denied) {
            _evidence = null;
            for (final c in _controllers.values) {
              c.clear();
            }
          }
        });
      }
    } finally {
      await reviewedImage?.evict();
      reviewBuffer?.fillRange(0, reviewBuffer.length, 0);
      ownedEvidenceBytes?.fillRange(0, ownedEvidenceBytes.length, 0);
      if (mounted) {
        setState(() {
          _busy = false;
          _selecting = false;
        });
      }
    }
  }

  Future<void> _submit() async {
    if (_locked) return;
    try {
      if (!_reviewed) {
        throw const FormatException(
          'Review the exact phase, identities and evidence first.',
        );
      }
      final fields = <String, dynamic>{};
      for (final f in _fields) {
        final c = _controllers[f.key];
        fields[f.key] = switch (f.kind) {
          TreasuryFieldKind.boolean ||
          TreasuryFieldKind.choice => _values[f.key],
          TreasuryFieldKind.integer => int.tryParse(c!.text),
          TreasuryFieldKind.destination => {
            'kind': _destinationKind,
            'recipient_reference':
                _destinationKind == 'physical_cash' &&
                    _destinationReference.text.isEmpty
                ? null
                : _destinationReference.text,
          },
          _ => c?.text,
        };
      }
      final own = collectorOwnActions.contains(widget.action);
      final command = TreasuryCommand(
        widget.action,
        requestId: newTreasuryRequestId(),
        accountId: own ? null : widget.account?.id,
        expectedVersion: own ? null : widget.account?.version,
        fields: fields,
      );
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: Text(widget.action.label),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(widget.account?.alias ?? 'Your own Collector record'),
                ..._recordFacts(
                  Map<String, dynamic>.from(command.toJson())
                    ..remove('action')
                    ..remove('request_id'),
                ),
                const Text(
                  'This records only this deliberate phase. Approval, actual cash movement, recipient acknowledgment and settlement are separate. No provider transfer occurs.',
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(c, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(c, true),
              child: const Text('Confirm this phase'),
            ),
          ],
        ),
      );
      if (confirmed != true || !mounted) return;
      setState(() => _busy = true);
      if (_evidence != null) {
        await widget.repository.content(
          evidenceId: _evidence!['id'] as String,
          mediaType: _evidence!['media_type'] as String,
          digest: _evidence!['sha256'] as String,
          byteCount: _evidence!['byte_count'] as int,
        );
      }
      final result = await widget.repository.execute(command);
      if (mounted) {
        setState(() {
          _result = result;
          _completed = true;
          _reviewed = false;
          _error = null;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          if (widget.repository.denied) {
            for (final c in _controllers.values) {
              c.clear();
            }
            _evidence = null;
            _destinationReference.clear();
          }
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _recover() async {
    try {
      final result = await widget.repository.recover();
      if (mounted) {
        setState(() {
          if (result == null) {
            _error =
                'The exact request remains unconfirmed. No automatic retry.';
          } else if (result.raw['action'] == 'evidence_upload') {
            _evidence = treasuryObject(result.result['evidence']);
            _controllers['evidence_id']?.text = _evidence!['id'] as String;
            _error =
                'Evidence recovered. Review the separate business phase before submission.';
          } else {
            _result = result;
            _completed = true;
          }
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  Widget _field(TreasuryField f) {
    final bound = widget.initial.containsKey(f.key);
    if (f.kind == TreasuryFieldKind.boolean) {
      return CheckboxListTile(
        contentPadding: EdgeInsets.zero,
        title: Text(f.label),
        value: _values[f.key] == true,
        onChanged: _locked
            ? null
            : (v) {
                _values[f.key] = v == true;
                _changed();
              },
      );
    }
    if (f.kind == TreasuryFieldKind.destination) {
      return Column(
        children: [
          DropdownButtonFormField<String>(
            initialValue: _destinationKind,
            isExpanded: true,
            decoration: const InputDecoration(
              labelText: 'Recipient destination',
            ),
            items: [
              for (final k in ['physical_cash', 'gcash', 'bank'])
                DropdownMenuItem(
                  value: k,
                  child: Text(
                    k == 'physical_cash'
                        ? 'Cash'
                        : k == 'gcash'
                        ? 'GCash'
                        : k == 'bank'
                        ? 'Bank'
                        : k.replaceAll('_', ' '),
                  ),
                ),
            ],
            onChanged: _locked || bound
                ? null
                : (v) {
                    _destinationKind = v!;
                    _changed();
                  },
          ),
          TextField(
            controller: _destinationReference,
            readOnly: _locked || bound,
            decoration: const InputDecoration(
              labelText: 'Recipient reference (wallet / bank)',
            ),
            onChanged: (_) => _changed(),
          ),
        ],
      );
    }
    if (f.kind == TreasuryFieldKind.choice) {
      return DropdownButtonFormField<String>(
        initialValue: _values[f.key] as String?,
        isExpanded: true,
        decoration: InputDecoration(labelText: f.label),
        items: [
          if (!f.required)
            const DropdownMenuItem(value: null, child: Text('Not supplied')),
          for (final k in f.choices)
            DropdownMenuItem(
              value: k,
              child: Text(
                k == 'physical_cash'
                    ? 'Cash'
                    : k == 'gcash'
                    ? 'GCash'
                    : k == 'bank'
                    ? 'Bank'
                    : k.replaceAll('_', ' '),
              ),
            ),
        ],
        onChanged: _locked || bound
            ? null
            : (v) {
                _values[f.key] = v;
                _changed();
              },
      );
    }
    if (f.key == 'evidence_id') {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (_evidence != null)
            TreasurySelectableText('Reviewed evidence ${_evidence!['id']}'),
          Wrap(
            spacing: 8,
            children: [
              OutlinedButton(
                onPressed: _locked ? null : () => _pick(),
                child: const Text('Select private evidence'),
              ),
              OutlinedButton(
                onPressed: _locked ? null : () => _pick(camera: true),
                child: const Text('Camera evidence'),
              ),
            ],
          ),
        ],
      );
    }
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextField(
        key: Key('collector-field-${f.key}'),
        controller: _controllers[f.key],
        readOnly: _locked || bound,
        decoration: InputDecoration(
          labelText: f.label,
          helperText: bound
              ? 'Current server record - read only'
              : f.kind == TreasuryFieldKind.instant
              ? 'Actual date, time and timezone'
              : null,
        ),
        keyboardType:
            [
              TreasuryFieldKind.money,
              TreasuryFieldKind.positiveMoney,
            ].contains(f.kind)
            ? const TextInputType.numberWithOptions(decimal: true)
            : TextInputType.text,
        onChanged: (_) => _changed(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      toolbarHeight: MediaQuery.textScalerOf(
        context,
      ).scale(56).clamp(56, 112).toDouble(),
      title: Text(widget.action.label),
    ),
    body: SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            widget.account?.alias ?? 'Own Collector request / acknowledgment',
          ),
          const Text(
            'Exact PHP values only. Current authority and server versions are checked before submission.',
          ),
          if (_busy)
            if (_selecting)
              const Text('Reviewing private evidence')
            else
              const LinearProgressIndicator(),
          if (_error != null) Text(_error!),
          if (widget.repository.pendingRequestId != null) ...[
            const Text('Unconfirmed phase - new submission locked'),
            TreasurySelectableText(widget.repository.pendingRequestId!),
            OutlinedButton(
              onPressed: _busy ? null : _recover,
              child: const Text('Check exact request'),
            ),
          ],
          if (widget.reviewLabel != null) Text(widget.reviewLabel!),
          for (final f in _fields.where(
            (f) =>
                !widget.initial.containsKey(f.key) ||
                !_technicalReference(f.key),
          ))
            _field(f),
          if (_fields.any(
            (f) =>
                widget.initial.containsKey(f.key) && _technicalReference(f.key),
          ))
            ExpansionTile(
              title: const Text('Record references'),
              children: [
                for (final f in _fields.where(
                  (f) =>
                      widget.initial.containsKey(f.key) &&
                      _technicalReference(f.key),
                ))
                  TreasurySelectableText(
                    '${f.label}: ${widget.initial[f.key]}',
                  ),
              ],
            ),
          CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text(
              'I reviewed the current record, exact amounts and this separate phase',
            ),
            value: _reviewed,
            onChanged: _locked
                ? null
                : (v) => setState(() => _reviewed = v == true),
          ),
          FilledButton(
            onPressed: _locked ? null : _submit,
            child: const Text('Review and confirm phase'),
          ),
          if (_result != null) ...[
            const SizedBox(height: 12),
            Text(
              collectorDispositionLabel(
                _result!.result['disposition'] as String? ??
                    (_result!.result['source_link'] as Map?)?['disposition']
                        as String? ??
                    ((_result!.result['source_link'] as Map?)?['status'] ==
                            'blocked'
                        ? 'actual_debit_source_unresolved'
                        : 'Actual movement observed - settlement remains separate'),
              ),
            ),
            for (final blocker in _result!.result['blockers'] as List? ?? [])
              Text(_plainBlocker(treasuryBlockerMessage(blocker))),
            if ((_result!.result['source_link'] as Map?)?['blocker'] is String)
              Text(
                _plainBlocker(
                  _result!.result['source_link']['blocker'] as String,
                ),
              ),
            ..._recordFacts(_result!.result),
          ],
        ],
      ),
    ),
  );
}

List<Widget> _recordFacts(
  Map<String, dynamic> record, {
  bool includeReferences = false,
}) {
  final ordered = [
    ...record.entries.where((e) => collectorSurplusAmounts.contains(e.key)),
    ...record.entries.where(
      (e) =>
          !collectorSurplusAmounts.contains(e.key) &&
          !['status', 'disposition'].contains(e.key) &&
          (includeReferences || !_technicalReference(e.key)),
    ),
  ];
  return [
    for (final e in ordered)
      if (e.value != null) ...[
        if (e.value is Map) ...[
          Text(e.key.replaceAll('_', ' ')),
          ..._recordFacts(treasuryObject(e.value)),
        ] else if (e.value is List) ...[
          if ((e.value as List).isNotEmpty) Text(e.key.replaceAll('_', ' ')),
          for (final item in e.value as List)
            if (item is Map)
              ..._recordFacts(treasuryObject(item))
            else
              TreasurySelectableText('$item'),
        ] else
          TreasurySelectableText(
            '${e.key.replaceAll('_', ' ')}: ${collectorSurplusAmounts.contains(e.key) ? 'PHP ' : ''}${e.key == 'status' || e.key == 'disposition' ? collectorDispositionLabel(e.value as String) : _plainFact(e.key, e.value)}',
          ),
      ],
    if (!includeReferences && record.keys.any(_technicalReference))
      ExpansionTile(
        title: const Text('Record references'),
        children: _recordFacts({
          for (final e in record.entries)
            if (_technicalReference(e.key)) e.key: e.value,
        }, includeReferences: true),
      ),
  ];
}

bool _technicalReference(String key) =>
    key == 'id' ||
    key.endsWith('_id') ||
    key == 'version' ||
    key.endsWith('_version') ||
    key.contains('digest') ||
    key == 'source_snapshot' ||
    key == 'source_items' ||
    key == 'remittance_snapshot' ||
    key == 'refund_due_releases' ||
    key.endsWith('contract_version');

String _plainFact(String key, Object? value) {
  if (value is! String) return '$value';
  if (value == 'physical_cash') return 'Cash';
  if (value == 'gcash') return 'GCash';
  if (value == 'bank') return 'Bank';
  if (key.endsWith('_at') || key == 'cutoff') {
    return formatSpinaBusinessDateTime(DateTime.tryParse(value));
  }
  if (key == 'collection_date') return formatSpinaCalendarDate(value);
  return value;
}

String _plainBlocker(String message) => message
    .replaceAll('protected adapter', 'supported workflow')
    .replaceAll('custody adapter', 'handover process')
    .replaceAll('adapters', 'workflows')
    .replaceAll('adapter', 'workflow');

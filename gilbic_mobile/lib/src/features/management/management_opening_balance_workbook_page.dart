import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_workbook.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_workbook_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

class ManagementOpeningBalanceWorkbookPage extends StatefulWidget {
  const ManagementOpeningBalanceWorkbookPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final OpeningBalanceWorkbookRepository? repository;

  @override
  State<ManagementOpeningBalanceWorkbookPage> createState() =>
      _ManagementOpeningBalanceWorkbookPageState();
}

class _ManagementOpeningBalanceWorkbookPageState
    extends State<ManagementOpeningBalanceWorkbookPage> {
  late final OpeningBalanceWorkbookRepository _repository;
  OpeningBalanceWorkbookData? _workbook;
  bool _loading = true;
  bool _busy = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaOpeningBalanceWorkbookRepository();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final workbook = await _repository.load(
        widget.session,
        deviceId: identity.installationId,
      );
      if (mounted) {
        setState(() => _workbook = workbook);
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(
          () => _errorMessage = 'Opening Balance Workbook could not be loaded.',
        );
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _initializeWorkbook() async {
    final now = DateTime.now();
    final selected = await showDatePicker(
      context: context,
      initialDate: DateTime(now.year, now.month, now.day),
      firstDate: DateTime(2020),
      lastDate: DateTime(2100),
      helpText: 'Select accounting cutover date',
    );
    if (selected == null || !mounted) {
      return;
    }
    final workbook = _workbook;
    if (workbook == null) {
      return;
    }
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        surface: ManagementMutationSurface.openingWorkbook,
        recordLabel: 'Opening balance workbook',
        recordValue: 'Cutover date ${_date(selected)}',
        statusLabel: 'Not initialized; source references are read-only',
        facts: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Workbook lines',
            value: '${workbook.summary.lineCount}',
          ),
          ManagementReviewFact(
            label: 'Source references',
            value: '${workbook.summary.sourceReferenceCount}',
          ),
        ],
        nextActionLabel: 'Initialize opening workbook',
        consequence:
            'The workbook will snapshot approved source references for the selected '
            'cutover date. It will not create or post a journal.',
        risk: ManagementReviewRisk.protectedFinancial,
      ),
    );
    if (!confirmed || !mounted) {
      return;
    }
    await _runAction(
      () async {
        final identity = await widget.deviceIdentityProvider.load();
        return _repository.create(
          widget.session,
          deviceId: identity.installationId,
          cutoverDate: selected,
        );
      },
      successMessage:
          'Opening-balance workbook initialized for ${_date(selected)}.',
    );
  }

  Future<void> _editLine(OpeningBalanceWorkbookLine line) async {
    final draft = await showDialog<_LineEditDraft>(
      context: context,
      builder: (context) => _EditOpeningBalanceLineDialog(line: line),
    );
    final workbookId = _workbook?.summary.workbookId;
    if (draft == null || workbookId == null || !mounted) {
      return;
    }
    final amount = draft.debit != null
        ? 'Debit ${_money(draft.debit!)}'
        : draft.credit != null
        ? 'Credit ${_money(draft.credit!)}'
        : 'Explicit zero or blank amount';
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        surface: ManagementMutationSurface.openingWorkbook,
        recordLabel: 'Opening workbook line',
        recordValue: '${line.accountCode} • ${line.accountName}',
        statusLabel: plainManagementStatus(
          line.verificationStatus,
          const <String, String>{
            'pending': 'Pending evidence verification',
            'verified': 'Verified from recorded evidence',
          },
        ),
        facts: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Source reference',
            value: line.sourceReferenceAmount == null
                ? 'Not provided'
                : _money(line.sourceReferenceAmount!),
          ),
          ManagementReviewFact(label: 'Proposed amount', value: amount),
          ManagementReviewFact(
            label: 'Next verification status',
            value: _statusLabel(draft.verificationStatus),
          ),
          if (draft.evidenceNote?.trim().isNotEmpty == true)
            ManagementReviewFact(
              label: 'Evidence note',
              value: draft.evidenceNote!,
            ),
        ],
        nextActionLabel: 'Save opening workbook line',
        consequence:
            'The workbook line and its evidence status will be saved. No opening '
            'balance or General Ledger entry will be posted.',
        risk: ManagementReviewRisk.protectedFinancial,
        secondaryReferences: <ManagementReviewFact>[
          ManagementReviewFact(label: 'Workbook ID', value: workbookId),
        ],
      ),
    );
    if (!confirmed || !mounted) {
      return;
    }
    await _runAction(() async {
      final identity = await widget.deviceIdentityProvider.load();
      return _repository.updateLine(
        widget.session,
        deviceId: identity.installationId,
        workbookId: workbookId,
        accountCode: line.accountCode,
        debit: draft.debit,
        credit: draft.credit,
        verificationStatus: draft.verificationStatus,
        evidenceNote: draft.evidenceNote,
      );
    }, successMessage: '${line.accountCode} ${line.accountName} saved.');
  }

  Future<void> _editPolicy() async {
    final workbook = _workbook;
    final workbookId = workbook?.summary.workbookId;
    if (workbook == null || workbookId == null) {
      return;
    }
    final draft = await showDialog<_PolicyEditDraft>(
      context: context,
      builder: (context) => _EditCutoverPolicyDialog(
        confirmed: workbook.summary.profitLossPolicyConfirmed,
        note: workbook.summary.profitLossPolicyNote,
      ),
    );
    if (draft == null || !mounted) {
      return;
    }
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        surface: ManagementMutationSurface.openingWorkbook,
        recordLabel: 'Opening workbook policy',
        recordValue: 'Profit and loss migration policy',
        statusLabel: workbook.summary.profitLossPolicyConfirmed
            ? 'Policy is confirmed'
            : 'Policy is pending approval evidence',
        facts: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Next confirmation state',
            value: draft.confirmed ? 'Confirmed' : 'Not confirmed',
          ),
          if (draft.note?.trim().isNotEmpty == true)
            ManagementReviewFact(label: 'Policy note', value: draft.note!),
        ],
        nextActionLabel: 'Save opening workbook policy',
        consequence:
            'The workbook policy evidence will be saved. No opening balance or '
            'General Ledger entry will be posted.',
        risk: ManagementReviewRisk.protectedFinancial,
        secondaryReferences: <ManagementReviewFact>[
          ManagementReviewFact(label: 'Workbook ID', value: workbookId),
        ],
      ),
    );
    if (!confirmed || !mounted) {
      return;
    }
    await _runAction(() async {
      final identity = await widget.deviceIdentityProvider.load();
      return _repository.updatePolicy(
        widget.session,
        deviceId: identity.installationId,
        workbookId: workbookId,
        confirmed: draft.confirmed,
        policyNote: draft.note,
      );
    }, successMessage: 'Cutover P&L migration policy saved.');
  }

  Future<void> _changeStatus(String targetStatus) async {
    final workbook = _workbook;
    final workbookId = workbook?.summary.workbookId;
    if (workbook == null || workbookId == null) {
      return;
    }
    final targetLabel = targetStatus == 'review_ready'
        ? 'Review Ready'
        : 'Draft';
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        surface: ManagementMutationSurface.openingWorkbook,
        recordLabel: 'Opening balance workbook',
        recordValue: '${_date(workbook.summary.cutoverDate!)} • $workbookId',
        statusLabel: plainManagementStatus(
          workbook.summary.status,
          const <String, String>{
            'draft': 'Draft and editable under Management controls',
            'review_ready': 'Review Ready and read-only',
          },
        ),
        facts: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Verified lines',
            value: '${workbook.summary.verifiedLineCount}',
          ),
          ManagementReviewFact(
            label: 'Pending lines',
            value: '${workbook.summary.pendingLineCount}',
          ),
          ManagementReviewFact(label: 'Next status', value: targetLabel),
        ],
        nextActionLabel: 'Change workbook to $targetLabel',
        consequence: targetStatus == 'review_ready'
            ? 'Only the workbook workflow state will change to Review Ready. '
                  'Journal preparation and posting remain separate protected actions.'
            : 'Only the workbook workflow state will return to Draft. No journal '
                  'will be prepared or posted.',
        risk: ManagementReviewRisk.protectedFinancial,
        secondaryReferences: <ManagementReviewFact>[
          ManagementReviewFact(label: 'Workbook ID', value: workbookId),
        ],
      ),
    );
    if (!confirmed || !mounted) {
      return;
    }
    await _runAction(
      () async {
        final identity = await widget.deviceIdentityProvider.load();
        return _repository.changeStatus(
          widget.session,
          deviceId: identity.installationId,
          workbookId: workbookId,
          status: targetStatus,
        );
      },
      successMessage: targetStatus == 'review_ready'
          ? 'Opening-balance workbook marked review ready.'
          : 'Opening-balance workbook reopened to Draft.',
    );
  }

  Future<void> _runAction(
    Future<OpeningBalanceWorkbookData> Function() action, {
    required String successMessage,
  }) async {
    if (_busy) {
      return;
    }
    setState(() => _busy = true);
    try {
      final workbook = await action();
      if (mounted) {
        setState(() {
          _workbook = workbook;
          _errorMessage = null;
        });
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(successMessage)));
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(error.message)));
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Opening-balance workbook action failed.'),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _busy = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Opening Balance Workbook'),
        actions: [
          IconButton(
            tooltip: 'Refresh opening-balance workbook',
            onPressed: _loading || _busy ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(child: _buildBody()),
    );
  }

  Widget _buildBody() {
    final workbook = _workbook;
    if (_loading && workbook == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_errorMessage != null && workbook == null) {
      return _ErrorPanel(message: _errorMessage!, onRetry: _load);
    }
    if (workbook == null) {
      return const SizedBox.shrink();
    }

    final summary = workbook.summary;
    final editable = workbook.managementEnabled && summary.isDraft && !_busy;
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.shield_outlined),
                  const SizedBox(width: 10),
                  Expanded(child: Text(workbook.notice)),
                ],
              ),
            ),
          ),
          if (_errorMessage != null) ...[
            const SizedBox(height: 10),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(
                  _errorMessage!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            ),
          ],
          const SizedBox(height: 12),
          if (!summary.hasWorkbook)
            _InitializeWorkbookCard(
              sourceReferenceCount: summary.sourceReferenceCount,
              lineCount: summary.lineCount,
              canManage: workbook.managementEnabled,
              busy: _busy,
              onInitialize: _initializeWorkbook,
            )
          else ...[
            _WorkbookSummaryCard(summary: summary),
            const SizedBox(height: 12),
            _CutoverPolicyCard(
              summary: summary,
              editable: editable,
              onEdit: _editPolicy,
            ),
          ],
          const SizedBox(height: 14),
          Wrap(
            spacing: 12,
            runSpacing: 4,
            alignment: WrapAlignment.spaceBetween,
            children: [
              Text(
                'Balance-sheet lines',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              Text('${workbook.lines.length} accounts'),
            ],
          ),
          const SizedBox(height: 8),
          for (final line in workbook.lines) ...[
            _WorkbookLineCard(
              line: line,
              editable: editable,
              onEdit: () => _editLine(line),
            ),
            const SizedBox(height: 8),
          ],
          if (summary.hasWorkbook) ...[
            const SizedBox(height: 6),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Review gate',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      summary.readyForReview
                          ? 'All lines are verified, the workbook balances, and the P&L migration policy is confirmed.'
                          : 'Review remains blocked until every line is explicitly verified, debit equals credit, and the P&L migration policy is confirmed.',
                    ),
                    const SizedBox(height: 10),
                    if (summary.isDraft)
                      FilledButton.icon(
                        key: const Key('opening-workbook-mark-review-ready'),
                        onPressed: summary.readyForReview && !_busy
                            ? () => _changeStatus('review_ready')
                            : null,
                        icon: const Icon(Icons.fact_check_outlined),
                        label: const Text('Mark review ready'),
                      )
                    else if (summary.isReviewReady)
                      OutlinedButton.icon(
                        key: const Key('opening-workbook-reopen-draft'),
                        onPressed: _busy ? null : () => _changeStatus('draft'),
                        icon: const Icon(Icons.edit_outlined),
                        label: const Text('Reopen Draft'),
                      ),
                    const SizedBox(height: 8),
                    const Text(
                      'Opening journal posting: Disabled. Automatic lending posting: Disabled.',
                    ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _InitializeWorkbookCard extends StatelessWidget {
  const _InitializeWorkbookCard({
    required this.sourceReferenceCount,
    required this.lineCount,
    required this.canManage,
    required this.busy,
    required this.onInitialize,
  });

  final int sourceReferenceCount;
  final int lineCount;
  final bool canManage;
  final bool busy;
  final VoidCallback onInitialize;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: const Key('opening-workbook-not-initialized'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Workbook not initialized',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 8),
            Text(
              '$lineCount balance-sheet lines are available, with $sourceReferenceCount source references. Initializing snapshots these references at the selected cutover date; it does not post to the General Ledger.',
            ),
            if (canManage) ...[
              const SizedBox(height: 12),
              FilledButton.icon(
                key: const Key('initialize-opening-balance-workbook'),
                onPressed: busy ? null : onInitialize,
                icon: const Icon(Icons.playlist_add_check_outlined),
                label: const Text('Initialize workbook'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _WorkbookSummaryCard extends StatelessWidget {
  const _WorkbookSummaryCard({required this.summary});

  final OpeningBalanceWorkbookSummary summary;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: const Key('opening-workbook-summary'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.table_view_outlined),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Protected Cutover Workbook',
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                ),
                Chip(label: Text(_statusLabel(summary.status))),
              ],
            ),
            const SizedBox(height: 8),
            _DetailRow(
              label: 'Cutover date',
              value: summary.cutoverDate == null
                  ? 'Not set'
                  : _date(summary.cutoverDate!),
            ),
            _DetailRow(
              label: 'Verified / pending',
              value:
                  '${summary.verifiedLineCount} / ${summary.pendingLineCount}',
            ),
            _DetailRow(label: 'Debit total', value: _money(summary.totalDebit)),
            _DetailRow(
              label: 'Credit total',
              value: _money(summary.totalCredit),
            ),
            _DetailRow(
              label: 'Variance',
              value: _money(summary.balanceVariance),
            ),
            _DetailRow(
              label: 'Balanced',
              value: summary.worksheetBalanced ? 'Yes' : 'No',
            ),
            _DetailRow(
              label: 'Ready for review',
              value: summary.readyForReview ? 'Yes' : 'No',
            ),
            _DetailRow(
              label: 'Ready to post',
              value: summary.readyToPost ? 'Yes' : 'No',
            ),
          ],
        ),
      ),
    );
  }
}

class _CutoverPolicyCard extends StatelessWidget {
  const _CutoverPolicyCard({
    required this.summary,
    required this.editable,
    required this.onEdit,
  });

  final OpeningBalanceWorkbookSummary summary;
  final bool editable;
  final VoidCallback onEdit;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: const Key('opening-workbook-policy'),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    'P&L migration policy',
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                ),
                Chip(
                  label: Text(
                    summary.profitLossPolicyConfirmed ? 'Confirmed' : 'Pending',
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              summary.profitLossPolicyNote ??
                  'Record the approved conversion treatment before the workbook can move to review ready.',
            ),
            if (editable) ...[
              const SizedBox(height: 10),
              OutlinedButton.icon(
                key: const Key('edit-opening-workbook-policy'),
                onPressed: onEdit,
                icon: const Icon(Icons.edit_note_outlined),
                label: const Text('Edit policy'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _WorkbookLineCard extends StatelessWidget {
  const _WorkbookLineCard({
    required this.line,
    required this.editable,
    required this.onEdit,
  });

  final OpeningBalanceWorkbookLine line;
  final bool editable;
  final VoidCallback onEdit;

  @override
  Widget build(BuildContext context) {
    final proposed = line.proposedDebit != null
        ? 'Dr ${_money(line.proposedDebit!)}'
        : line.proposedCredit != null
        ? 'Cr ${_money(line.proposedCredit!)}'
        : 'Not entered';
    return Card(
      key: Key('opening-workbook-line-${line.accountCode}'),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  width: 48,
                  child: Text(
                    line.accountCode,
                    style: Theme.of(context).textTheme.labelLarge,
                  ),
                ),
                Expanded(
                  child: Text(
                    line.accountName,
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                ),
                Chip(label: Text(line.isVerified ? 'Verified' : 'Pending')),
              ],
            ),
            const SizedBox(height: 6),
            _DetailRow(
              label: 'Source reference',
              value: line.sourceReferenceAmount == null
                  ? 'Not set'
                  : _money(line.sourceReferenceAmount!),
            ),
            _DetailRow(
              label: 'Requirement',
              value: _statusLabel(line.requirementType),
            ),
            _DetailRow(label: 'Opening amount', value: proposed),
            if (line.evidenceNote != null)
              _DetailRow(label: 'Evidence note', value: line.evidenceNote!),
            const SizedBox(height: 5),
            Text(line.guidance, style: Theme.of(context).textTheme.bodySmall),
            if (editable) ...[
              const SizedBox(height: 10),
              OutlinedButton.icon(
                key: Key('edit-opening-workbook-line-${line.accountCode}'),
                onPressed: onEdit,
                icon: const Icon(Icons.edit_outlined),
                label: const Text('Edit / verify'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _EditOpeningBalanceLineDialog extends StatefulWidget {
  const _EditOpeningBalanceLineDialog({required this.line});

  final OpeningBalanceWorkbookLine line;

  @override
  State<_EditOpeningBalanceLineDialog> createState() =>
      _EditOpeningBalanceLineDialogState();
}

class _EditOpeningBalanceLineDialogState
    extends State<_EditOpeningBalanceLineDialog> {
  late final TextEditingController _debitController;
  late final TextEditingController _creditController;
  late final TextEditingController _noteController;
  late String _verificationStatus;
  String? _error;

  @override
  void initState() {
    super.initState();
    _debitController = TextEditingController(
      text: widget.line.proposedDebit?.toStringAsFixed(2) ?? '',
    );
    _creditController = TextEditingController(
      text: widget.line.proposedCredit?.toStringAsFixed(2) ?? '',
    );
    _noteController = TextEditingController(
      text: widget.line.evidenceNote ?? '',
    );
    _verificationStatus = widget.line.verificationStatus;
  }

  @override
  void dispose() {
    _debitController.dispose();
    _creditController.dispose();
    _noteController.dispose();
    super.dispose();
  }

  double? _parse(TextEditingController controller) {
    final text = controller.text.trim();
    return text.isEmpty ? null : double.tryParse(text);
  }

  void _save() {
    final debit = _parse(_debitController);
    final credit = _parse(_creditController);
    if ((_debitController.text.trim().isNotEmpty && debit == null) ||
        (_creditController.text.trim().isNotEmpty && credit == null)) {
      setState(() => _error = 'Debit and credit must be valid numbers.');
      return;
    }
    if ((debit ?? 0) < 0 || (credit ?? 0) < 0) {
      setState(() => _error = 'Amounts cannot be negative.');
      return;
    }
    if ((debit ?? 0) > 0 && (credit ?? 0) > 0) {
      setState(() => _error = 'Use only one side: debit or credit.');
      return;
    }
    final note = _noteController.text.trim();
    if (_verificationStatus == 'verified' && debit == null && credit == null) {
      setState(
        () => _error =
            'Verified lines require an explicit amount, including zero.',
      );
      return;
    }
    if (_verificationStatus == 'verified' && note.length < 3) {
      setState(() => _error = 'Verified lines require a short evidence note.');
      return;
    }
    Navigator.of(context).pop(
      _LineEditDraft(
        debit: debit,
        credit: credit,
        verificationStatus: _verificationStatus,
        evidenceNote: note.isEmpty ? null : note,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text('${widget.line.accountCode} ${widget.line.accountName}'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              widget.line.sourceReferenceAmount == null
                  ? 'Source reference: Not set'
                  : 'Source reference: ${_money(widget.line.sourceReferenceAmount!)}',
            ),
            const SizedBox(height: 10),
            TextField(
              key: const Key('opening-line-debit'),
              controller: _debitController,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: const InputDecoration(labelText: 'Debit'),
            ),
            const SizedBox(height: 8),
            TextField(
              key: const Key('opening-line-credit'),
              controller: _creditController,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: const InputDecoration(labelText: 'Credit'),
            ),
            const SizedBox(height: 8),
            DropdownButtonFormField<String>(
              key: const Key('opening-line-verification-status'),
              initialValue: _verificationStatus,
              decoration: const InputDecoration(
                labelText: 'Verification status',
              ),
              items: const [
                DropdownMenuItem(value: 'pending', child: Text('Pending')),
                DropdownMenuItem(value: 'verified', child: Text('Verified')),
              ],
              onChanged: (value) {
                if (value != null) {
                  setState(() => _verificationStatus = value);
                }
              },
            ),
            const SizedBox(height: 8),
            TextField(
              key: const Key('opening-line-evidence-note'),
              controller: _noteController,
              maxLength: 500,
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(
                labelText: 'Evidence / reconciliation note',
              ),
            ),
            if (_error != null)
              Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          key: const Key('save-opening-workbook-line'),
          onPressed: _save,
          child: const Text('Save line'),
        ),
      ],
    );
  }
}

class _EditCutoverPolicyDialog extends StatefulWidget {
  const _EditCutoverPolicyDialog({required this.confirmed, required this.note});

  final bool confirmed;
  final String? note;

  @override
  State<_EditCutoverPolicyDialog> createState() =>
      _EditCutoverPolicyDialogState();
}

class _EditCutoverPolicyDialogState extends State<_EditCutoverPolicyDialog> {
  late final TextEditingController _controller;
  late bool _confirmed;
  String? _error;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.note ?? '');
    _confirmed = widget.confirmed;
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _save() {
    final note = _controller.text.trim();
    if (_confirmed && note.length < 5) {
      setState(() => _error = 'A confirmed policy requires a policy note.');
      return;
    }
    Navigator.of(context).pop(
      _PolicyEditDraft(confirmed: _confirmed, note: note.isEmpty ? null : note),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('P&L migration policy'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              key: const Key('opening-policy-note'),
              controller: _controller,
              maxLength: 1000,
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(
                labelText: 'Approved conversion policy note',
                hintText:
                    'Record the approved treatment; do not guess a policy.',
              ),
            ),
            SwitchListTile(
              key: const Key('opening-policy-confirmed'),
              contentPadding: EdgeInsets.zero,
              value: _confirmed,
              onChanged: (value) => setState(() => _confirmed = value),
              title: const Text('Policy confirmed'),
              subtitle: const Text(
                'Only confirm after the conversion treatment is approved.',
              ),
            ),
            if (_error != null)
              Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          key: const Key('save-opening-workbook-policy'),
          onPressed: _save,
          child: const Text('Save policy'),
        ),
      ],
    );
  }
}

class _LineEditDraft {
  const _LineEditDraft({
    required this.debit,
    required this.credit,
    required this.verificationStatus,
    required this.evidenceNote,
  });

  final double? debit;
  final double? credit;
  final String verificationStatus;
  final String? evidenceNote;
}

class _PolicyEditDraft {
  const _PolicyEditDraft({required this.confirmed, required this.note});

  final bool confirmed;
  final String? note;
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: Text(label)),
          const SizedBox(width: 12),
          Flexible(child: Text(value, textAlign: TextAlign.end)),
        ],
      ),
    );
  }
}

class _ErrorPanel extends StatelessWidget {
  const _ErrorPanel({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, size: 40),
            const SizedBox(height: 10),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            FilledButton(onPressed: onRetry, child: const Text('Retry')),
          ],
        ),
      ),
    );
  }
}

String _statusLabel(String value) {
  return switch (value) {
    'draft' => 'Draft',
    'review_ready' => 'Review ready',
    'source_review_required' => 'Source review required',
    'manual_required' => 'Manual balance',
    'reconciliation_required' => 'Reconciliation',
    'calculation_required' => 'Accounting calculation',
    'assessment_required' => 'Assessment',
    _ =>
      value
          .split('_')
          .where((part) => part.isNotEmpty)
          .map((part) => '${part[0].toUpperCase()}${part.substring(1)}')
          .join(' '),
  };
}

String _money(double value) {
  final negative = value < 0;
  final fixed = value.abs().toStringAsFixed(2);
  final parts = fixed.split('.');
  final chars = parts.first.split('').reversed.toList();
  final groups = <String>[];
  for (var index = 0; index < chars.length; index += 3) {
    groups.add(chars.skip(index).take(3).toList().reversed.join());
  }
  final whole = groups.reversed.join(',');
  return '${negative ? '-' : ''}₱$whole.${parts[1]}';
}

String _date(DateTime value) {
  final month = value.month.toString().padLeft(2, '0');
  final day = value.day.toString().padLeft(2, '0');
  return '${value.year}-$month-$day';
}

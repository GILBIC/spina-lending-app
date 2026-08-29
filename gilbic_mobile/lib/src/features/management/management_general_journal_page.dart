import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/financial_accounting.dart';
import 'package:gilbic_mobile/src/core/management/general_journal.dart';
import 'package:gilbic_mobile/src/core/management/general_journal_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

class ManagementGeneralJournalPage extends StatefulWidget {
  const ManagementGeneralJournalPage({
    required this.session,
    required this.deviceIdentityProvider,
    required this.accounts,
    required this.periods,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final List<AccountingAccount> accounts;
  final List<AccountingFiscalPeriod> periods;
  final GeneralJournalRepository? repository;

  @override
  State<ManagementGeneralJournalPage> createState() =>
      _ManagementGeneralJournalPageState();
}

class _ManagementGeneralJournalPageState
    extends State<ManagementGeneralJournalPage> {
  late final GeneralJournalRepository _repository;
  GeneralJournalSnapshot? _snapshot;
  AccountingTrialBalance? _trialBalance;
  String? _selectedPeriodId;
  String? _errorMessage;
  bool _loading = true;
  bool _actionBusy = false;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaGeneralJournalRepository();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final snapshot = await _repository.loadJournals(
        widget.session,
        deviceId: identity.installationId,
      );
      final trial = await _repository.loadTrialBalance(
        widget.session,
        deviceId: identity.installationId,
        periodId: _selectedPeriodId,
      );
      if (mounted) {
        setState(() {
          _snapshot = snapshot;
          _trialBalance = trial;
        });
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() => _errorMessage = 'General Journal could not be loaded.');
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _createDraft() async {
    final draft = await showDialog<_JournalDraft>(
      context: context,
      builder: (context) => _JournalDialog(
        title: 'Create manual journal draft',
        accounts: widget.accounts
            .where((account) => account.isActive && account.isPosting)
            .toList(),
      ),
    );
    if (draft == null || !mounted) {
      return;
    }
    final confirmed = await showManagementReviewConfirmation(
      context,
      _draftReview(draft: draft),
    );
    if (!confirmed || !mounted) {
      return;
    }
    await _runAction(() async {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.createDraft(
        widget.session,
        deviceId: identity.installationId,
        postingDate: draft.postingDate,
        description: draft.description,
        lines: draft.lines,
      );
      _snack('Manual journal draft created.');
    });
  }

  Future<void> _editDraft(AccountingJournalEntry entry) async {
    final draft = await showDialog<_JournalDraft>(
      context: context,
      builder: (context) => _JournalDialog(
        title: 'Edit manual journal draft',
        accounts: widget.accounts
            .where((account) => account.isActive && account.isPosting)
            .toList(),
        entry: entry,
      ),
    );
    if (draft == null || !mounted) {
      return;
    }
    final confirmed = await showManagementReviewConfirmation(
      context,
      _draftReview(draft: draft, entry: entry),
    );
    if (!confirmed || !mounted) {
      return;
    }
    await _runAction(() async {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.updateDraft(
        widget.session,
        deviceId: identity.installationId,
        entryId: entry.entryId,
        postingDate: draft.postingDate,
        description: draft.description,
        lines: draft.lines,
      );
      _snack('Journal draft updated.');
    });
  }

  Future<void> _post(AccountingJournalEntry entry) async {
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        surface: ManagementMutationSurface.generalJournal,
        recordLabel: 'Journal draft',
        recordValue: entry.entryNumber ?? entry.entryId,
        statusLabel: 'Draft — not posted',
        statusDetail: entry.description,
        facts: _entryFacts(entry),
        nextActionLabel: 'Post journal',
        consequence:
            'The journal will be posted immutably to the General Ledger. '
            'Corrections require a separate reversal with permanent audit evidence.',
        risk: ManagementReviewRisk.protectedFinancial,
        secondaryReferences: <ManagementReviewFact>[
          ManagementReviewFact(label: 'Entry ID', value: entry.entryId),
        ],
      ),
    );
    if (!confirmed || !mounted) {
      return;
    }
    await _runAction(() async {
      final identity = await widget.deviceIdentityProvider.load();
      final posted = await _repository.postJournal(
        widget.session,
        deviceId: identity.installationId,
        entryId: entry.entryId,
      );
      _snack('${posted.entryNumber ?? 'Journal'} posted.');
    });
  }

  Future<void> _cancel(AccountingJournalEntry entry) async {
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        surface: ManagementMutationSurface.generalJournal,
        recordLabel: 'Journal draft',
        recordValue: entry.entryNumber ?? entry.entryId,
        statusLabel: 'Draft — not posted',
        statusDetail: entry.description,
        facts: _entryFacts(entry),
        nextActionLabel: 'Cancel journal draft',
        consequence:
            'The draft will be cancelled while a permanent audit snapshot is '
            'retained. No posted ledger balance will change.',
        risk: ManagementReviewRisk.protectedFinancial,
        secondaryReferences: <ManagementReviewFact>[
          ManagementReviewFact(label: 'Entry ID', value: entry.entryId),
        ],
      ),
    );
    if (!confirmed || !mounted) {
      return;
    }
    await _runAction(() async {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.cancelDraft(
        widget.session,
        deviceId: identity.installationId,
        entryId: entry.entryId,
      );
      _snack('Journal draft cancelled with audit retained.');
    });
  }

  Future<void> _reverse(AccountingJournalEntry entry) async {
    final draft = await showDialog<_ReversalDraft>(
      context: context,
      builder: (context) => _ReversalDialog(entry: entry),
    );
    if (draft == null || !mounted) {
      return;
    }
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        surface: ManagementMutationSurface.generalJournal,
        recordLabel: 'Posted journal',
        recordValue: entry.entryNumber ?? entry.entryId,
        statusLabel: 'Posted — immutable',
        statusDetail: entry.description,
        facts: <ManagementReviewFact>[
          ..._entryFacts(entry),
          ManagementReviewFact(
            label: 'Reversal posting date',
            value: _date(draft.postingDate),
          ),
          ManagementReviewFact(
            label: 'Reversal description',
            value: draft.description,
          ),
        ],
        nextActionLabel: 'Create reversal draft',
        consequence:
            'A separate unposted reversal draft will be created with debit and '
            'credit lines swapped. It must be reviewed and posted separately.',
        risk: ManagementReviewRisk.protectedFinancial,
        secondaryReferences: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Original entry ID',
            value: entry.entryId,
          ),
        ],
      ),
    );
    if (!confirmed || !mounted) {
      return;
    }
    await _runAction(() async {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.createReversalDraft(
        widget.session,
        deviceId: identity.installationId,
        entryId: entry.entryId,
        postingDate: draft.postingDate,
        description: draft.description,
      );
      _snack('Reversal draft created. Review and post it separately.');
    });
  }

  ManagementReviewPresentation _draftReview({
    required _JournalDraft draft,
    AccountingJournalEntry? entry,
  }) {
    final totalDebit = draft.lines.fold<double>(
      0,
      (total, line) => total + line.debit,
    );
    final totalCredit = draft.lines.fold<double>(
      0,
      (total, line) => total + line.credit,
    );
    return ManagementReviewPresentation.validated(
      surface: ManagementMutationSurface.generalJournal,
      recordLabel: entry == null
          ? 'New manual journal'
          : 'Manual journal draft',
      recordValue: entry?.entryNumber ?? entry?.entryId ?? draft.description,
      statusLabel: entry == null
          ? 'New balanced draft — not posted'
          : 'Draft — not posted',
      statusDetail: draft.description,
      facts: <ManagementReviewFact>[
        ManagementReviewFact(
          label: 'Posting date',
          value: _date(draft.postingDate),
        ),
        ManagementReviewFact(label: 'Total debit', value: _money(totalDebit)),
        ManagementReviewFact(label: 'Total credit', value: _money(totalCredit)),
        ManagementReviewFact(
          label: 'Journal lines',
          value: '${draft.lines.length}',
        ),
      ],
      nextActionLabel: entry == null
          ? 'Create manual journal draft'
          : 'Update manual journal draft',
      consequence:
          'The balanced journal will be saved as an unposted draft. It will '
          'not affect the General Ledger until separately reviewed and posted.',
      risk: ManagementReviewRisk.protectedFinancial,
      secondaryReferences: entry == null
          ? const <ManagementReviewFact>[]
          : <ManagementReviewFact>[
              ManagementReviewFact(label: 'Entry ID', value: entry.entryId),
            ],
    );
  }

  List<ManagementReviewFact> _entryFacts(
    AccountingJournalEntry entry,
  ) => <ManagementReviewFact>[
    ManagementReviewFact(
      label: 'Posting date',
      value: _date(entry.postingDate),
    ),
    ManagementReviewFact(label: 'Total debit', value: _money(entry.totalDebit)),
    ManagementReviewFact(
      label: 'Total credit',
      value: _money(entry.totalCredit),
    ),
    ManagementReviewFact(
      label: 'Journal lines',
      value: '${entry.lines.length}',
    ),
  ];

  Future<void> _runAction(Future<void> Function() action) async {
    if (_actionBusy) {
      return;
    }
    setState(() => _actionBusy = true);
    try {
      await action();
      await _load();
    } on SpinaApiException catch (error) {
      _snack(error.message);
    } on Object {
      _snack('General Journal action failed.');
    } finally {
      if (mounted) {
        setState(() => _actionBusy = false);
      }
    }
  }

  void _snack(String message) {
    if (mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(message)));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('General Journal'),
        actions: [
          IconButton(
            tooltip: 'Refresh General Journal',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      floatingActionButton: _snapshot?.canManage == true
          ? FloatingActionButton.extended(
              key: const Key('create-manual-journal'),
              onPressed: _actionBusy ? null : _createDraft,
              icon: const Icon(Icons.add),
              label: const Text('Journal'),
            )
          : null,
      body: SafeArea(child: _buildBody()),
    );
  }

  Widget _buildBody() {
    if (_loading && _snapshot == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_snapshot == null) {
      return _ErrorPanel(
        message: _errorMessage ?? 'General Journal unavailable.',
        onRetry: _load,
      );
    }
    final snapshot = _snapshot!;
    final entries = snapshot.entries;
    final posted = entries.where((entry) => entry.isPosted).length;
    final drafts = entries.where((entry) => entry.isDraft).length;

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.security_outlined),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      snapshot.automaticLoanPostingEnabled
                          ? 'Automatic source posting is enabled.'
                          : 'Manual journals only. Automatic loan, collection, EIR, ECL, and opening-balance posting remain disabled.',
                    ),
                  ),
                ],
              ),
            ),
          ),
          if (_errorMessage != null) ...[
            const SizedBox(height: 8),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(_errorMessage!),
              ),
            ),
          ],
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _CountCard(
                  label: 'Journal entries',
                  value: '${entries.length}',
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _CountCard(
                  label: 'Posted / drafts',
                  value: '$posted / $drafts',
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _TrialBalanceCard(
            trialBalance: _trialBalance,
            periods: widget.periods,
            selectedPeriodId: _selectedPeriodId,
            onPeriodChanged: (value) async {
              setState(() => _selectedPeriodId = value);
              await _load();
            },
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 12,
            runSpacing: 4,
            alignment: WrapAlignment.spaceBetween,
            children: [
              Text(
                'General Journal',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              Text('${entries.length} shown'),
            ],
          ),
          const SizedBox(height: 8),
          if (entries.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: Text(
                  'No journal entries yet. Create a balanced manual draft to test the protected journal workflow.',
                ),
              ),
            )
          else
            for (final entry in entries) ...[
              _JournalCard(
                entry: entry,
                canManage: snapshot.canManage,
                busy: _actionBusy,
                onEdit: () => _editDraft(entry),
                onPost: () => _post(entry),
                onCancel: () => _cancel(entry),
                onReverse: () => _reverse(entry),
              ),
              const SizedBox(height: 8),
            ],
        ],
      ),
    );
  }
}

class _TrialBalanceCard extends StatelessWidget {
  const _TrialBalanceCard({
    required this.trialBalance,
    required this.periods,
    required this.selectedPeriodId,
    required this.onPeriodChanged,
  });

  final AccountingTrialBalance? trialBalance;
  final List<AccountingFiscalPeriod> periods;
  final String? selectedPeriodId;
  final ValueChanged<String?> onPeriodChanged;

  @override
  Widget build(BuildContext context) {
    final trial = trialBalance;
    final activeLines =
        trial?.lines
            .where((line) => line.debitBalance != 0 || line.creditBalance != 0)
            .toList() ??
        const <AccountingTrialBalanceLine>[];
    return Card(
      key: const Key('general-journal-trial-balance'),
      clipBehavior: Clip.antiAlias,
      child: ExpansionTile(
        initiallyExpanded: true,
        leading: const Icon(Icons.balance_outlined),
        title: const Text('Trial Balance'),
        subtitle: Text(
          trial == null
              ? 'Loading'
              : '${trial.balanced ? 'Balanced' : 'Out of balance'} • ${_money(trial.totalDebits)} / ${_money(trial.totalCredits)}',
        ),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        children: [
          DropdownButtonFormField<String?>(
            initialValue: selectedPeriodId,
            isExpanded: true,
            decoration: const InputDecoration(
              labelText: 'Trial balance period',
            ),
            items: <DropdownMenuItem<String?>>[
              const DropdownMenuItem<String?>(
                value: null,
                child: Text('All posted journals'),
              ),
              ...periods.map(
                (period) => DropdownMenuItem<String?>(
                  value: period.periodId,
                  child: Text(period.label),
                ),
              ),
            ],
            onChanged: onPeriodChanged,
          ),
          const SizedBox(height: 12),
          if (trial != null) ...[
            Row(
              children: [
                Expanded(child: Text('Debit ${_money(trial.totalDebits)}')),
                Expanded(
                  child: Text(
                    'Credit ${_money(trial.totalCredits)}',
                    textAlign: TextAlign.right,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            if (activeLines.isEmpty)
              const Align(
                alignment: Alignment.centerLeft,
                child: Text('No posted balances yet.'),
              )
            else
              for (final line in activeLines)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      SizedBox(width: 50, child: Text(line.accountCode)),
                      Expanded(child: Text(line.accountName)),
                      const SizedBox(width: 8),
                      Text(
                        line.debitBalance > 0
                            ? 'Dr ${_money(line.debitBalance)}'
                            : 'Cr ${_money(line.creditBalance)}',
                      ),
                    ],
                  ),
                ),
          ],
        ],
      ),
    );
  }
}

class _JournalCard extends StatelessWidget {
  const _JournalCard({
    required this.entry,
    required this.canManage,
    required this.busy,
    required this.onEdit,
    required this.onPost,
    required this.onCancel,
    required this.onReverse,
  });

  final AccountingJournalEntry entry;
  final bool canManage;
  final bool busy;
  final VoidCallback onEdit;
  final VoidCallback onPost;
  final VoidCallback onCancel;
  final VoidCallback onReverse;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: Key('journal-${entry.entryId}'),
      clipBehavior: Clip.antiAlias,
      child: ExpansionTile(
        leading: Icon(
          entry.isPosted ? Icons.verified_outlined : Icons.edit_note_outlined,
        ),
        title: Text(entry.entryNumber ?? 'Draft journal'),
        subtitle: Text('${_date(entry.postingDate)} • ${entry.description}'),
        trailing: Chip(label: Text(entry.isPosted ? 'Posted' : 'Draft')),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        children: [
          _JournalDetail(label: 'Period', value: entry.periodLabel),
          _JournalDetail(label: 'Created by', value: entry.createdByName),
          if (entry.postedByName != null)
            _JournalDetail(label: 'Posted by', value: entry.postedByName!),
          _JournalDetail(label: 'Total debit', value: _money(entry.totalDebit)),
          _JournalDetail(
            label: 'Total credit',
            value: _money(entry.totalCredit),
          ),
          if (entry.reversalOfEntryId != null)
            const _JournalDetail(label: 'Type', value: 'Reversal draft'),
          const SizedBox(height: 8),
          for (final line in entry.lines)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(width: 48, child: Text(line.accountCode)),
                  Expanded(child: Text(line.accountName)),
                  const SizedBox(width: 6),
                  Text(
                    line.debit > 0
                        ? 'Dr ${_money(line.debit)}'
                        : 'Cr ${_money(line.credit)}',
                  ),
                ],
              ),
            ),
          if (canManage) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 6,
              children: [
                if (entry.isDraft && entry.isManual)
                  OutlinedButton.icon(
                    key: Key('edit-journal-${entry.entryId}'),
                    onPressed: busy ? null : onEdit,
                    icon: const Icon(Icons.edit_outlined),
                    label: const Text('Edit'),
                  ),
                if (entry.isDraft && entry.isManual)
                  OutlinedButton.icon(
                    key: Key('cancel-journal-${entry.entryId}'),
                    onPressed: busy ? null : onCancel,
                    icon: const Icon(Icons.cancel_outlined),
                    label: const Text('Cancel draft'),
                  ),
                if (entry.isDraft)
                  FilledButton.icon(
                    key: Key('post-journal-${entry.entryId}'),
                    onPressed: busy ? null : onPost,
                    icon: const Icon(Icons.post_add_outlined),
                    label: const Text('Post'),
                  ),
                if (entry.isPosted)
                  OutlinedButton.icon(
                    key: Key('reverse-journal-${entry.entryId}'),
                    onPressed: busy ? null : onReverse,
                    icon: const Icon(Icons.undo_outlined),
                    label: const Text('Create reversal'),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _JournalDialog extends StatefulWidget {
  const _JournalDialog({
    required this.title,
    required this.accounts,
    this.entry,
  });

  final String title;
  final List<AccountingAccount> accounts;
  final AccountingJournalEntry? entry;

  @override
  State<_JournalDialog> createState() => _JournalDialogState();
}

class _JournalDialogState extends State<_JournalDialog> {
  late final TextEditingController _descriptionController;
  late DateTime _postingDate;
  late final List<_LineControllers> _lines;
  String? _validation;

  @override
  void initState() {
    super.initState();
    final entry = widget.entry;
    _postingDate = entry?.postingDate ?? DateTime.now();
    _descriptionController = TextEditingController(
      text: entry?.description ?? '',
    );
    _lines = entry == null
        ? <_LineControllers>[_LineControllers(), _LineControllers()]
        : entry.lines
              .map(
                (line) => _LineControllers(
                  accountCode: line.accountCode,
                  description: line.description,
                  debit: line.debit,
                  credit: line.credit,
                ),
              )
              .toList();
  }

  @override
  void dispose() {
    _descriptionController.dispose();
    for (final line in _lines) {
      line.dispose();
    }
    super.dispose();
  }

  Future<void> _pickDate() async {
    final selected = await showDatePicker(
      context: context,
      initialDate: _postingDate,
      firstDate: DateTime(2020),
      lastDate: DateTime(2100),
    );
    if (selected != null && mounted) {
      setState(() => _postingDate = selected);
    }
  }

  void _save() {
    final description = _descriptionController.text.trim();
    final drafts = <JournalLineDraft>[];
    var debit = 0.0;
    var credit = 0.0;
    for (final line in _lines) {
      final accountCode = line.accountCode;
      final lineDebit = double.tryParse(line.debitController.text.trim()) ?? 0;
      final lineCredit =
          double.tryParse(line.creditController.text.trim()) ?? 0;
      if (accountCode == null || accountCode.isEmpty) {
        setState(
          () => _validation = 'Choose an account for every journal line.',
        );
        return;
      }
      if (!((lineDebit > 0 && lineCredit == 0) ||
          (lineCredit > 0 && lineDebit == 0))) {
        setState(
          () => _validation =
              'Each line needs exactly one positive debit or credit.',
        );
        return;
      }
      debit += lineDebit;
      credit += lineCredit;
      drafts.add(
        JournalLineDraft(
          accountCode: accountCode,
          description: line.descriptionController.text.trim(),
          debit: lineDebit,
          credit: lineCredit,
        ),
      );
    }
    if (description.length < 3) {
      setState(() => _validation = 'Enter a journal description.');
      return;
    }
    if ((debit - credit).abs() > 0.005 || debit <= 0) {
      setState(
        () => _validation = 'The journal must balance before it can be saved.',
      );
      return;
    }
    Navigator.of(context).pop(
      _JournalDraft(
        postingDate: _postingDate,
        description: description,
        lines: drafts,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.title),
      content: SizedBox(
        width: 520,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              TextField(
                key: const Key('journal-description'),
                controller: _descriptionController,
                maxLength: 240,
                decoration: const InputDecoration(labelText: 'Description'),
              ),
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Posting date'),
                subtitle: Text(_date(_postingDate)),
                trailing: const Icon(Icons.calendar_today_outlined),
                onTap: _pickDate,
              ),
              const SizedBox(height: 8),
              for (var index = 0; index < _lines.length; index++) ...[
                _JournalLineEditor(
                  index: index,
                  line: _lines[index],
                  accounts: widget.accounts,
                  canRemove: _lines.length > 2,
                  onRemove: () {
                    setState(() {
                      final removed = _lines.removeAt(index);
                      removed.dispose();
                    });
                  },
                ),
                const Divider(),
              ],
              OutlinedButton.icon(
                onPressed: _lines.length >= 30
                    ? null
                    : () => setState(() => _lines.add(_LineControllers())),
                icon: const Icon(Icons.add),
                label: const Text('Add line'),
              ),
              if (_validation != null) ...[
                const SizedBox(height: 8),
                Text(
                  _validation!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
              const SizedBox(height: 8),
              const Text(
                'Drafts must already balance. Posting is a separate confirmed action and makes the entry immutable.',
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          key: const Key('save-manual-journal'),
          onPressed: _save,
          child: const Text('Save draft'),
        ),
      ],
    );
  }
}

class _JournalLineEditor extends StatelessWidget {
  const _JournalLineEditor({
    required this.index,
    required this.line,
    required this.accounts,
    required this.canRemove,
    required this.onRemove,
  });

  final int index;
  final _LineControllers line;
  final List<AccountingAccount> accounts;
  final bool canRemove;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(
              'Line ${index + 1}',
              style: Theme.of(context).textTheme.labelLarge,
            ),
            const Spacer(),
            if (canRemove)
              IconButton(
                onPressed: onRemove,
                icon: const Icon(Icons.remove_circle_outline),
              ),
          ],
        ),
        DropdownButtonFormField<String>(
          key: Key('journal-line-$index-account'),
          initialValue: line.accountCode,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'Account'),
          items: accounts
              .map(
                (account) => DropdownMenuItem<String>(
                  value: account.code,
                  child: Text(
                    '${account.code} • ${account.name}',
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              )
              .toList(growable: false),
          onChanged: (value) => line.accountCode = value,
        ),
        TextField(
          controller: line.descriptionController,
          decoration: const InputDecoration(
            labelText: 'Line description (optional)',
          ),
        ),
        Row(
          children: [
            Expanded(
              child: TextField(
                key: Key('journal-line-$index-debit'),
                controller: line.debitController,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: const InputDecoration(labelText: 'Debit'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: TextField(
                key: Key('journal-line-$index-credit'),
                controller: line.creditController,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: const InputDecoration(labelText: 'Credit'),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _LineControllers {
  _LineControllers({
    this.accountCode,
    String description = '',
    double debit = 0,
    double credit = 0,
  }) : descriptionController = TextEditingController(text: description),
       debitController = TextEditingController(
         text: debit == 0 ? '' : debit.toStringAsFixed(2),
       ),
       creditController = TextEditingController(
         text: credit == 0 ? '' : credit.toStringAsFixed(2),
       );

  String? accountCode;
  final TextEditingController descriptionController;
  final TextEditingController debitController;
  final TextEditingController creditController;

  void dispose() {
    descriptionController.dispose();
    debitController.dispose();
    creditController.dispose();
  }
}

class _ReversalDialog extends StatefulWidget {
  const _ReversalDialog({required this.entry});

  final AccountingJournalEntry entry;

  @override
  State<_ReversalDialog> createState() => _ReversalDialogState();
}

class _ReversalDialogState extends State<_ReversalDialog> {
  late DateTime _postingDate;
  late final TextEditingController _descriptionController;

  @override
  void initState() {
    super.initState();
    _postingDate = DateTime.now();
    _descriptionController = TextEditingController(
      text:
          'Reversal of ${widget.entry.entryNumber ?? widget.entry.description}',
    );
  }

  @override
  void dispose() {
    _descriptionController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Create reversal draft'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Reversal posting date'),
              subtitle: Text(_date(_postingDate)),
              onTap: () async {
                final selected = await showDatePicker(
                  context: context,
                  initialDate: _postingDate,
                  firstDate: DateTime(2020),
                  lastDate: DateTime(2100),
                );
                if (selected != null && mounted) {
                  setState(() => _postingDate = selected);
                }
              },
            ),
            TextField(
              controller: _descriptionController,
              maxLength: 240,
              decoration: const InputDecoration(labelText: 'Description'),
            ),
            const Text(
              'The reversal is created as a draft with debit and credit lines '
              'swapped. It must be reviewed and posted separately.',
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
          key: const Key('create-reversal-draft'),
          onPressed: () {
            final description = _descriptionController.text.trim();
            if (description.length < 3) {
              return;
            }
            Navigator.of(context).pop(
              _ReversalDraft(
                postingDate: _postingDate,
                description: description,
              ),
            );
          },
          child: const Text('Create draft'),
        ),
      ],
    );
  }
}

class _JournalDraft {
  const _JournalDraft({
    required this.postingDate,
    required this.description,
    required this.lines,
  });

  final DateTime postingDate;
  final String description;
  final List<JournalLineDraft> lines;
}

class _ReversalDraft {
  const _ReversalDraft({required this.postingDate, required this.description});

  final DateTime postingDate;
  final String description;
}

class _CountCard extends StatelessWidget {
  const _CountCard({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(value, style: Theme.of(context).textTheme.titleLarge),
            Text(label),
          ],
        ),
      ),
    );
  }
}

class _JournalDetail extends StatelessWidget {
  const _JournalDetail({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          SizedBox(width: 100, child: Text(label)),
          Expanded(child: Text(value, textAlign: TextAlign.right)),
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
            Icon(
              Icons.error_outline,
              size: 48,
              color: Theme.of(context).colorScheme.error,
            ),
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

String _money(double value) {
  final parts = value.toStringAsFixed(2).split('.');
  final whole = parts.first.replaceAllMapped(
    RegExp(r'\B(?=(\d{3})+(?!\d))'),
    (_) => ',',
  );
  return '₱$whole.${parts.last}';
}

String _date(DateTime value) {
  final month = value.month.toString().padLeft(2, '0');
  final day = value.day.toString().padLeft(2, '0');
  return '${value.year}-$month-$day';
}

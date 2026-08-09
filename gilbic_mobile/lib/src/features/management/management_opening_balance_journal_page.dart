import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_journal.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_journal_repository.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_workbook.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_workbook_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ManagementOpeningBalanceJournalPage extends StatefulWidget {
  const ManagementOpeningBalanceJournalPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.workbookRepository,
    this.journalRepository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final OpeningBalanceWorkbookRepository? workbookRepository;
  final OpeningBalanceJournalRepository? journalRepository;

  @override
  State<ManagementOpeningBalanceJournalPage> createState() =>
      _ManagementOpeningBalanceJournalPageState();
}

class _ManagementOpeningBalanceJournalPageState
    extends State<ManagementOpeningBalanceJournalPage> {
  late final OpeningBalanceWorkbookRepository _workbookRepository;
  late final OpeningBalanceJournalRepository _journalRepository;

  OpeningBalanceWorkbookData? _workbook;
  OpeningBalanceJournalDraftStatus? _journal;
  bool _loading = true;
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _workbookRepository =
        widget.workbookRepository ?? SpinaOpeningBalanceWorkbookRepository();
    _journalRepository =
        widget.journalRepository ?? SpinaOpeningBalanceJournalRepository();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final workbook = await _workbookRepository.load(
        widget.session,
        deviceId: identity.installationId,
      );
      OpeningBalanceJournalDraftStatus? journal;
      final workbookId = workbook.summary.workbookId;
      if (workbookId != null) {
        journal = await _journalRepository.load(
          widget.session,
          deviceId: identity.installationId,
          workbookId: workbookId,
        );
      }
      if (mounted) {
        setState(() {
          _workbook = workbook;
          _journal = journal;
        });
      }
    } on SpinaApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) {
        setState(() => _error = 'Opening Balance Journal could not be loaded.');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _prepareDraft() async {
    final workbookId = _workbook?.summary.workbookId;
    final journal = _journal;
    if (workbookId == null || journal == null || !journal.canPrepare || _busy) {
      return;
    }
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Prepare opening journal draft?'),
        content: const Text(
          'This copies the fully reviewed workbook into one protected system journal draft. '
          'It does not post to the General Ledger and automatic source posting remains disabled.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const Key('confirm-opening-journal-draft'),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Prepare Draft'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    setState(() => _busy = true);
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final prepared = await _journalRepository.prepare(
        widget.session,
        deviceId: identity.installationId,
        workbookId: workbookId,
      );
      if (mounted) {
        setState(() {
          _journal = prepared;
          _error = null;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Protected opening-balance journal draft prepared. Nothing was posted.'),
          ),
        );
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Opening journal draft preparation failed.')),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _postJournal() async {
    final workbookId = _workbook?.summary.workbookId;
    final journal = _journal;
    final journalEntryId = journal?.journalEntryId;
    if (workbookId == null ||
        journal == null ||
        journalEntryId == null ||
        !journal.canPost ||
        _busy) {
      return;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Post opening balances to General Ledger?'),
        content: Text(
          'You are about to post the protected opening-balance journal.\n\n'
          'Debit: ${_money(journal.totalDebit)}\n'
          'Credit: ${_money(journal.totalCredit)}\n\n'
          'The server will revalidate the workbook, journal, accounting period, accounts, and source readiness before posting. '
          'The posted entry becomes immutable; corrections require a controlled reversal. Automatic source posting remains disabled.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const Key('confirm-post-opening-journal'),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Post Opening Balance'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    setState(() => _busy = true);
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final posted = await _journalRepository.post(
        widget.session,
        deviceId: identity.installationId,
        workbookId: workbookId,
        journalEntryId: journalEntryId,
        totalDebit: journal.totalDebit,
        totalCredit: journal.totalCredit,
      );
      if (mounted) {
        setState(() {
          _journal = posted;
          _error = null;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Opening balances posted as ${posted.entryNumber ?? 'protected journal'}.',
            ),
          ),
        );
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Opening-balance posting failed. Nothing was changed.')),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Opening Balance Journal'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _loading || _busy ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(child: _body()),
    );
  }

  Widget _body() {
    if (_loading && _workbook == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null && _workbook == null) {
      return _ErrorPanel(message: _error!, onRetry: _load);
    }

    final workbook = _workbook;
    if (workbook == null || !workbook.summary.hasWorkbook) {
      return _MessagePanel(
        icon: Icons.table_view_outlined,
        title: 'Opening workbook required',
        message: 'Initialize and verify the Opening Balance Workbook before preparing a journal draft.',
        onRefresh: _load,
      );
    }

    final journal = _journal;
    if (journal == null) {
      return _ErrorPanel(
        message: _error ?? 'Opening-balance journal status is unavailable.',
        onRetry: _load,
      );
    }

    final canPreparePermission = widget.session.permissions.contains(
      'accounting.opening_balance.prepare',
    );
    final canPostPermission = widget.session.permissions.contains(
      'accounting.opening_balance.post',
    );
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.lock_outline),
                  const SizedBox(width: 10),
                  Expanded(child: Text(journal.notice)),
                ],
              ),
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 10),
            Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          ],
          const SizedBox(height: 12),
          Card(
            key: const Key('opening-journal-status-card'),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          'Cutover journal',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                      ),
                      Chip(label: Text(_journalStateLabel(journal))),
                    ],
                  ),
                  const SizedBox(height: 10),
                  _DetailRow('Cutover date', _date(journal.cutoverDate)),
                  _DetailRow('Workbook', _statusLabel(journal.workbookStatus)),
                  _DetailRow(
                    'Journal status',
                    journal.journalStatus == null
                        ? 'None'
                        : _statusLabel(journal.journalStatus!),
                  ),
                  if (journal.draftPrepared) ...[
                    _DetailRow('Lines', journal.journalLineCount.toString()),
                    _DetailRow('Debit', _money(journal.totalDebit)),
                    _DetailRow('Credit', _money(journal.totalCredit)),
                  ],
                  if (journal.entryNumber != null)
                    _DetailRow('Entry number', journal.entryNumber!),
                  _DetailRow(
                    'General Ledger posting',
                    journal.isPosted
                        ? 'Posted'
                        : journal.openingBalancePostingEnabled
                            ? 'Protected / explicit only'
                            : 'Disabled',
                  ),
                  _DetailRow('Automatic source posting', 'Disabled'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Preparation gate', style: Theme.of(context).textTheme.titleSmall),
                  const SizedBox(height: 8),
                  Text(_preparationGateMessage(journal, canPreparePermission)),
                  if (!journal.draftPrepared) ...[
                    const SizedBox(height: 12),
                    FilledButton.icon(
                      key: const Key('prepare-opening-journal-draft'),
                      onPressed: journal.canPrepare && canPreparePermission && !_busy
                          ? _prepareDraft
                          : null,
                      icon: const Icon(Icons.description_outlined),
                      label: Text(_busy ? 'Preparing…' : 'Prepare Draft'),
                    ),
                  ],
                  if (journal.draftPrepared) ...[
                    const SizedBox(height: 10),
                    const Text(
                      'Preparation is complete. The protected draft cannot be edited or deleted through General Journal.',
                    ),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          Card(
            key: const Key('opening-journal-posting-gate'),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Posting gate', style: Theme.of(context).textTheme.titleSmall),
                  const SizedBox(height: 8),
                  Text(_postingGateMessage(journal, canPostPermission)),
                  if (!journal.isPosted) ...[
                    const SizedBox(height: 12),
                    FilledButton.icon(
                      key: const Key('post-opening-journal'),
                      onPressed: journal.canPost && canPostPermission && !_busy
                          ? _postJournal
                          : null,
                      icon: const Icon(Icons.account_balance_outlined),
                      label: Text(_busy ? 'Posting…' : 'Post to General Ledger'),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

String _journalStateLabel(OpeningBalanceJournalDraftStatus journal) {
  if (journal.isPosted) return 'Posted';
  if (journal.draftPrepared) return 'Draft prepared';
  return 'Not prepared';
}

String _preparationGateMessage(
  OpeningBalanceJournalDraftStatus journal,
  bool hasPermission,
) {
  if (journal.draftPrepared) {
    return 'Preparation complete. The draft remains protected from normal General Journal editing.';
  }
  if (!journal.preparationReady) {
    final blocker = journal.preparationBlocker ??
        'Opening-balance journal preparation requirements are not complete.';
    return 'Blocked: $blocker';
  }
  if (!hasPermission) {
    return 'Blocked: your current session does not have opening-balance preparation permission.';
  }
  return 'Ready to prepare a protected draft. This action does not post any accounting entry.';
}

String _postingGateMessage(
  OpeningBalanceJournalDraftStatus journal,
  bool hasPermission,
) {
  if (journal.isPosted) {
    return 'Posted as ${journal.entryNumber}. The entry is immutable; corrections require a controlled reversal.';
  }
  if (!journal.openingBalancePostingEnabled) {
    return 'Posting controls are not installed yet.';
  }
  if (!journal.postingReady) {
    return 'Blocked: ${journal.postingBlocker ?? 'Protected opening-balance posting requirements are not complete.'}';
  }
  if (!hasPermission) {
    return 'Blocked: your current session does not have opening-balance posting permission.';
  }
  return 'Ready for explicit Management posting. The server will revalidate every accounting safety gate before committing.';
}

class _DetailRow extends StatelessWidget {
  const _DetailRow(this.label, this.value);

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 150, child: Text(label)),
          Expanded(
            child: Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
          ),
        ],
      ),
    );
  }
}

class _MessagePanel extends StatelessWidget {
  const _MessagePanel({
    required this.icon,
    required this.title,
    required this.message,
    required this.onRefresh,
  });

  final IconData icon;
  final String title;
  final String message;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 48),
            const SizedBox(height: 12),
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: onRefresh,
              icon: const Icon(Icons.refresh),
              label: const Text('Refresh'),
            ),
          ],
        ),
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
            Icon(Icons.error_outline, size: 48, color: Theme.of(context).colorScheme.error),
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

String _money(double amount) {
  final absolute = amount.abs().toStringAsFixed(2);
  final parts = absolute.split('.');
  final whole = parts.first;
  final grouped = StringBuffer();
  for (var i = 0; i < whole.length; i += 1) {
    if (i > 0 && (whole.length - i) % 3 == 0) grouped.write(',');
    grouped.write(whole[i]);
  }
  final text = '₱${grouped.toString()}.${parts.last}';
  return amount < 0 ? '($text)' : text;
}

String _date(DateTime value) {
  final month = value.month.toString().padLeft(2, '0');
  final day = value.day.toString().padLeft(2, '0');
  return '${value.year}-$month-$day';
}

String _statusLabel(String value) {
  return value
      .split('_')
      .where((part) => part.isNotEmpty)
      .map((part) => '${part[0].toUpperCase()}${part.substring(1)}')
      .join(' ');
}

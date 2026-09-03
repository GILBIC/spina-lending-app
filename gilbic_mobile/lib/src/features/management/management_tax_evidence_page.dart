import 'dart:math';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/tax_evidence.dart';
import 'package:gilbic_mobile/src/core/management/tax_evidence_repository.dart';
import 'package:gilbic_mobile/src/core/management/tax_value.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

class ManagementTaxEvidencePage extends StatefulWidget {
  const ManagementTaxEvidencePage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.uuidGenerator,
    this.now,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final TaxEvidenceRepository? repository;
  final String Function()? uuidGenerator;
  final DateTime Function()? now;

  @override
  State<ManagementTaxEvidencePage> createState() =>
      _ManagementTaxEvidencePageState();
}

class _ManagementTaxEvidencePageState extends State<ManagementTaxEvidencePage> {
  late final TaxEvidenceRepository _repository;
  late final String Function() _uuidGenerator;
  late final DateTime Function() _now;
  final Map<String, String> _retryIds = <String, String>{};
  TaxEvidenceOverview? _overview;
  String? _error;
  String? _busy;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaTaxEvidenceRepository();
    _uuidGenerator = widget.uuidGenerator ?? _newUuid;
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
          () =>
              _error = 'The protected tax-evidence queue could not be loaded.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  bool _canRule(TaxEvidenceOverview value) =>
      value.permissions.ruleEvidenceRecord &&
      widget.session.hasPermission('accounting.tax.rule_evidence.record');
  bool _canDst(TaxEvidenceOverview value) =>
      value.permissions.dstEvidenceRecord &&
      widget.session.hasPermission('accounting.tax.dst_evidence.record');
  bool _canPercentage(TaxEvidenceOverview value) =>
      value.permissions.percentageEvidenceRecord &&
      widget.session.hasPermission('accounting.tax.percentage_evidence.record');

  Future<void> _recordRule() async {
    final overview = _overview;
    if (overview == null || !_canRule(overview)) return;
    final draft = await showDialog<TaxRuleEvidenceDraft>(
      context: context,
      builder: (context) =>
          _RuleDialog(rules: overview.rules, initialDate: taxDateText(_now())),
    );
    if (draft == null || !mounted) return;
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        binding: ManagementMutationBinding.taxEvidence,
        recordLabel: 'Tax rule evidence',
        recordValue: draft.ruleKey,
        statusLabel: 'Ready to record immutable retained rule evidence',
        facts: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Tax type',
            value: _taxType(draft.taxType),
          ),
          ManagementReviewFact(
            label: 'Effective from',
            value: draft.effectiveFrom,
          ),
          ManagementReviewFact(label: 'Treatment', value: draft.treatment),
          ManagementReviewFact(label: 'Exact retained rate', value: draft.rate),
        ],
        secondaryReferences: <ManagementReviewFact>[
          ManagementReviewFact(label: 'Legal source', value: draft.legalSource),
          ManagementReviewFact(
            label: 'Evidence fingerprint',
            value: draft.evidenceDigest,
          ),
        ],
        warnings: const <ManagementReviewWarning>[
          ManagementReviewWarning(
            severity: ManagementReviewWarningSeverity.caution,
            message:
                'SPINA does not invent or approve legal tax treatment. Record only current retained evidence reviewed by Management/CPA.',
          ),
        ],
        nextActionLabel: 'Record tax rule evidence',
        consequence:
            'The backend will retain an immutable rule version. This action does not post tax or a journal.',
      ),
    );
    if (!confirmed || !mounted) return;
    final key = <String>[
      'rule',
      draft.taxType,
      draft.ruleKey,
      draft.effectiveFrom,
      draft.effectiveTo ?? '',
      draft.treatment,
      draft.rate,
      '${draft.maturityMaxDays ?? ''}',
      draft.legalSource,
      draft.legalReference,
      draft.retainedSourceReference,
      draft.evidenceDigest,
      draft.managementRationale,
      draft.supersedesRuleId ?? '',
    ].join('|');
    await _run(key, () async {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.recordRule(
        widget.session,
        deviceId: identity.installationId,
        draft: draft,
        idempotencyKey: _retryIds.putIfAbsent(key, _uuidGenerator),
      );
      _retryIds.remove(key);
      _message('Tax rule evidence recorded.');
    });
  }

  Future<void> _recordDst(DstTaxReadiness source) async {
    final overview = _overview;
    if (overview == null || !_canDst(overview)) return;
    final rules = overview.rules
        .where((rule) => rule.taxType == 'documentary_stamp_tax')
        .toList();
    if (rules.isEmpty) {
      _message('Record current retained DST rule evidence first.');
      return;
    }
    final draft = await showDialog<DstEvidenceDraft>(
      context: context,
      builder: (context) => _DstDialog(rules: rules),
    );
    if (draft == null || !mounted) return;
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        binding: ManagementMutationBinding.taxEvidence,
        recordLabel: 'DST source',
        recordValue: source.loanId,
        statusLabel: 'Ready to record exact retained DST evidence',
        facts: <ManagementReviewFact>[
          ManagementReviewFact(label: 'Issue date', value: source.issueDate),
          ManagementReviewFact(
            label: 'Protected issue price',
            value: source.protectedIssuePrice,
          ),
          ManagementReviewFact(
            label: 'Protected term days',
            value: '${source.protectedTermDays}',
          ),
          ManagementReviewFact(
            label: 'Expected tax due',
            value: draft.expectedTaxDue,
          ),
        ],
        secondaryReferences: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Rule evidence ID',
            value: draft.ruleEvidenceId,
          ),
          ManagementReviewFact(
            label: 'Calculation fingerprint',
            value: draft.calculationDigest,
          ),
        ],
        warnings: const <ManagementReviewWarning>[
          ManagementReviewWarning(
            severity: ManagementReviewWarningSeverity.caution,
            message:
                'The backend revalidates the exact loan, disbursement, issue price, term and rule. Mobile performs no DST calculation.',
          ),
        ],
        nextActionLabel: 'Record DST evidence',
        consequence:
            'The backend will retain exact source evidence. Liability preparation remains a separate protected action.',
      ),
    );
    if (!confirmed || !mounted) return;
    final key = <String>[
      'dst',
      source.loanId,
      source.disbursementEventId,
      source.protectedIssuePrice,
      '${source.protectedTermDays}',
      source.evidenceId ?? '',
      draft.ruleEvidenceId,
      draft.expectedTaxDue,
      draft.instrumentReference,
      draft.instrumentDigest,
      draft.calculationReference,
      draft.calculationDigest,
      draft.managementRationale,
    ].join('|');
    await _run(key, () async {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.recordDst(
        widget.session,
        deviceId: identity.installationId,
        source: source,
        draft: draft,
        idempotencyKey: _retryIds.putIfAbsent(key, _uuidGenerator),
      );
      _retryIds.remove(key);
      _message('DST evidence recorded.');
    });
  }

  Future<void> _recordPercentage(PercentageTaxReadiness source) async {
    final overview = _overview;
    if (overview == null || !_canPercentage(overview) || source.isVoided) {
      return;
    }
    final rules = overview.rules
        .where((rule) => rule.taxType == 'percentage_tax_lending')
        .toList();
    if (rules.isEmpty) {
      _message('Record current retained percentage-tax rule evidence first.');
      return;
    }
    final draft = await showDialog<PercentageTaxEvidenceDraft>(
      context: context,
      builder: (context) => _PercentageDialog(rules: rules, source: source),
    );
    if (draft == null || !mounted) return;
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        binding: ManagementMutationBinding.taxEvidence,
        recordLabel: 'Protected cash transaction',
        recordValue: source.transactionId,
        statusLabel: 'Exact allocation reconciled and ready to record',
        facts: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Collection date',
            value: source.collectionDate,
          ),
          ManagementReviewFact(
            label: 'Source cash',
            value: source.sourceCashAmount,
          ),
          ManagementReviewFact(
            label: 'Taxable lending receipt',
            value: draft.taxableLendingReceiptAmount,
          ),
          ManagementReviewFact(
            label: 'Principal receipt',
            value: draft.principalReceiptAmount,
          ),
          ManagementReviewFact(
            label: 'Expected tax due',
            value: draft.expectedTaxDue,
          ),
        ],
        secondaryReferences: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Rule evidence ID',
            value: draft.ruleEvidenceId,
          ),
          ManagementReviewFact(
            label: 'Allocation fingerprint',
            value: draft.allocationDigest,
          ),
        ],
        warnings: const <ManagementReviewWarning>[
          ManagementReviewWarning(
            severity: ManagementReviewWarningSeverity.caution,
            message:
                'PFRS/EIR interest is not substituted as the tax base. The retained allocation must reconcile to exact protected cash.',
          ),
        ],
        nextActionLabel: 'Record percentage evidence',
        consequence:
            'The backend will immutably retain the reconciled allocation. This does not post a tax liability.',
      ),
    );
    if (!confirmed || !mounted) return;
    final key = <String>[
      'percentage',
      source.transactionId,
      source.sourceCashAmount,
      source.evidenceId ?? '',
      draft.ruleEvidenceId,
      draft.taxableLendingReceiptAmount,
      draft.principalReceiptAmount,
      draft.expectedTaxDue,
      draft.allocationReference,
      draft.allocationDigest,
      draft.managementRationale,
    ].join('|');
    await _run(key, () async {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.recordPercentage(
        widget.session,
        deviceId: identity.installationId,
        source: source,
        draft: draft,
        idempotencyKey: _retryIds.putIfAbsent(key, _uuidGenerator),
      );
      _retryIds.remove(key);
      _message('Percentage-tax allocation evidence recorded.');
    });
  }

  Future<void> _run(String key, Future<void> Function() action) async {
    if (_busy != null) return;
    setState(() => _busy = key);
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
          'The result is uncertain. Review authoritative tax evidence before retrying.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = null);
      if (!succeeded && mounted) setState(() {});
    }
  }

  void _message(String value) {
    final messenger = ScaffoldMessenger.of(context);
    messenger.clearSnackBars();
    messenger.showSnackBar(SnackBar(content: Text(value)));
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Tax Evidence'),
      actions: <Widget>[
        IconButton(
          tooltip: 'Refresh tax evidence',
          onPressed: _loading || _busy != null ? null : _load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    floatingActionButton: _overview != null && _canRule(_overview!)
        ? FloatingActionButton.small(
            key: const Key('record-tax-rule'),
            tooltip: 'Record retained tax rule evidence',
            onPressed: _busy == null ? _recordRule : null,
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
      return _Error(message: _error!, onRetry: _load);
    }
    if (overview == null) return const SizedBox.shrink();
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
          const SizedBox(height: 10),
          _Summary(summary: overview.summary),
          if (!_canRule(overview))
            const _Notice('Tax rule evidence permission is not assigned.'),
          if (!_canDst(overview))
            const _Notice('DST evidence permission is not assigned.'),
          if (!_canPercentage(overview))
            const _Notice('Percentage evidence permission is not assigned.'),
          if (_error != null) _Notice(_error!),
          _SectionTitle('Approved rule evidence (${overview.rules.length})'),
          ...overview.rules.map((rule) => _RuleCard(rule: rule)),
          _SectionTitle('DST sources (${overview.dst.length})'),
          ...overview.dst.map(
            (source) => _DstCard(
              source: source,
              canRecord: _canDst(overview),
              busy: _busy?.contains(source.loanId) ?? false,
              onRecord: () => _recordDst(source),
            ),
          ),
          _SectionTitle(
            'Percentage-tax sources (${overview.percentageTax.length})',
          ),
          ...overview.percentageTax.map(
            (source) => _PercentageCard(
              source: source,
              canRecord: _canPercentage(overview) && !source.isVoided,
              busy: _busy?.contains(source.transactionId) ?? false,
              onRecord: () => _recordPercentage(source),
            ),
          ),
        ],
      ),
    );
  }
}

class _Summary extends StatelessWidget {
  const _Summary({required this.summary});
  final TaxEvidenceSummary summary;
  @override
  Widget build(BuildContext context) => Card(
    key: const Key('tax-evidence-summary'),
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Wrap(
        spacing: 14,
        runSpacing: 8,
        children: <Widget>[
          Text('Rules: ${summary.ruleEvidenceCount}'),
          Text('DST ready: ${summary.dstReadyCount}/${summary.dstSourceCount}'),
          Text('DST blocked: ${summary.dstBlockedCount}'),
          Text(
            'Percentage ready: ${summary.percentageReadyCount}/${summary.percentageSourceCount}',
          ),
          Text('Percentage blocked: ${summary.percentageBlockedCount}'),
        ],
      ),
    ),
  );
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 18, bottom: 4),
    child: Text(text, style: Theme.of(context).textTheme.titleMedium),
  );
}

class _RuleCard extends StatelessWidget {
  const _RuleCard({required this.rule});
  final TaxRuleEvidence rule;
  @override
  Widget build(BuildContext context) => Card(
    child: ListTile(
      leading: const Icon(Icons.gavel_outlined),
      title: Text(rule.ruleKey),
      subtitle: Text(
        '${_taxType(rule.taxType)} • ${rule.treatment} • rate ${rule.rate}\nEffective ${rule.effectiveFrom}',
      ),
      isThreeLine: true,
    ),
  );
}

class _DstCard extends StatelessWidget {
  const _DstCard({
    required this.source,
    required this.canRecord,
    required this.busy,
    required this.onRecord,
  });
  final DstTaxReadiness source;
  final bool canRecord;
  final bool busy;
  final VoidCallback onRecord;
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Text(
            'Loan ${source.loanId}',
            style: Theme.of(context).textTheme.titleSmall,
          ),
          Text(
            '${source.issueDate} • ${source.protectedIssuePrice} • ${source.protectedTermDays} days',
          ),
          Text(_status(source.taxStatus)),
          if (source.taxBlocker != null)
            Text(
              source.taxBlocker!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          if (canRecord)
            FilledButton.tonalIcon(
              key: Key('record-dst-${source.loanId}'),
              onPressed: busy ? null : onRecord,
              icon: const Icon(Icons.description_outlined),
              label: const Text('Record DST evidence'),
            ),
        ],
      ),
    ),
  );
}

class _PercentageCard extends StatelessWidget {
  const _PercentageCard({
    required this.source,
    required this.canRecord,
    required this.busy,
    required this.onRecord,
  });
  final PercentageTaxReadiness source;
  final bool canRecord;
  final bool busy;
  final VoidCallback onRecord;
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Text(
            '${source.entryType.toUpperCase()} ${source.transactionId}',
            style: Theme.of(context).textTheme.titleSmall,
          ),
          Text(
            '${source.collectionDate} • source cash ${source.sourceCashAmount}',
          ),
          Text(_status(source.taxStatus)),
          if (source.taxBlocker != null)
            Text(
              source.taxBlocker!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          if (canRecord)
            FilledButton.tonalIcon(
              key: Key('record-percentage-${source.transactionId}'),
              onPressed: busy ? null : onRecord,
              icon: const Icon(Icons.receipt_long_outlined),
              label: const Text('Record percentage allocation'),
            ),
        ],
      ),
    ),
  );
}

class _RuleDialog extends StatefulWidget {
  const _RuleDialog({required this.rules, required this.initialDate});
  final List<TaxRuleEvidence> rules;
  final String initialDate;
  @override
  State<_RuleDialog> createState() => _RuleDialogState();
}

class _RuleDialogState extends State<_RuleDialog> {
  final _key = TextEditingController();
  late final TextEditingController _from;
  final _to = TextEditingController();
  final _rate = TextEditingController();
  final _maturity = TextEditingController();
  final _source = TextEditingController();
  final _legal = TextEditingController();
  final _retained = TextEditingController();
  final _digest = TextEditingController();
  final _rationale = TextEditingController();
  String _type = 'documentary_stamp_tax';
  String _treatment = 'taxable';
  String? _supersedes;
  @override
  void initState() {
    super.initState();
    _from = TextEditingController(text: widget.initialDate);
  }

  @override
  void dispose() {
    for (final value in <TextEditingController>[
      _key,
      _from,
      _to,
      _rate,
      _maturity,
      _source,
      _legal,
      _retained,
      _digest,
      _rationale,
    ]) {
      value.dispose();
    }
    super.dispose();
  }

  void _review() {
    final draft = TaxRuleEvidenceDraft(
      taxType: _type,
      ruleKey: _key.text.trim(),
      effectiveFrom: _from.text.trim(),
      effectiveTo: _to.text.trim().isEmpty ? null : _to.text.trim(),
      treatment: _treatment,
      rate: _rate.text.trim(),
      maturityMaxDays: _maturity.text.trim().isEmpty
          ? null
          : int.tryParse(_maturity.text.trim()),
      legalSource: _source.text.trim(),
      legalReference: _legal.text.trim(),
      retainedSourceReference: _retained.text.trim(),
      evidenceDigest: _digest.text.trim(),
      managementRationale: _rationale.text.trim(),
      supersedesRuleId: _supersedes,
    );
    try {
      draft.validate();
      Navigator.of(context).pop(draft);
    } on Object {
      _invalid(
        context,
        'Complete exact retained legal/rule evidence, dates, rate, lowercase SHA-256 fingerprint, and rationale.',
      );
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Record tax rule evidence'),
    content: SizedBox(
      width: 440,
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            DropdownButtonFormField<String>(
              initialValue: _type,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Tax type'),
              items: const <DropdownMenuItem<String>>[
                DropdownMenuItem(
                  value: 'documentary_stamp_tax',
                  child: Text('Documentary stamp tax'),
                ),
                DropdownMenuItem(
                  value: 'percentage_tax_lending',
                  child: Text('Percentage tax — lending'),
                ),
              ],
              onChanged: (value) => setState(() {
                _type = value!;
                _supersedes = null;
              }),
            ),
            _field(_key, 'Rule key'),
            _field(_from, 'Effective from (YYYY-MM-DD)'),
            _field(_to, 'Effective to (optional)'),
            DropdownButtonFormField<String>(
              initialValue: _treatment,
              decoration: const InputDecoration(labelText: 'Treatment'),
              items: const <DropdownMenuItem<String>>[
                DropdownMenuItem(value: 'taxable', child: Text('Taxable')),
                DropdownMenuItem(value: 'exempt', child: Text('Exempt')),
              ],
              onChanged: (value) => setState(() => _treatment = value!),
            ),
            _field(_rate, 'Exact rate (0 to 1)'),
            _field(_maturity, 'Maturity maximum days (optional)'),
            _field(_source, 'Legal source'),
            _field(_legal, 'Legal reference'),
            _field(_retained, 'Retained source reference'),
            _field(_digest, 'Evidence fingerprint (SHA-256)', maxLength: 64),
            _field(_rationale, 'Management rationale', lines: 3),
            DropdownButtonFormField<String?>(
              initialValue: _supersedes,
              isExpanded: true,
              decoration: const InputDecoration(
                labelText: 'Supersedes rule (optional)',
              ),
              items: <DropdownMenuItem<String?>>[
                const DropdownMenuItem<String?>(
                  value: null,
                  child: Text('None'),
                ),
                ...widget.rules
                    .where((rule) => rule.taxType == _type)
                    .map(
                      (rule) => DropdownMenuItem<String?>(
                        value: rule.id,
                        child: Text(
                          '${rule.ruleKey} v${rule.ruleVersion}',
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ),
              ],
              onChanged: (value) => setState(() => _supersedes = value),
            ),
          ],
        ),
      ),
    ),
    actions: <Widget>[
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Cancel'),
      ),
      FilledButton(onPressed: _review, child: const Text('Review evidence')),
    ],
  );
}

class _DstDialog extends StatefulWidget {
  const _DstDialog({required this.rules});
  final List<TaxRuleEvidence> rules;
  @override
  State<_DstDialog> createState() => _DstDialogState();
}

class _DstDialogState extends State<_DstDialog> {
  late String _rule;
  final _due = TextEditingController();
  final _instrument = TextEditingController();
  final _instrumentDigest = TextEditingController();
  final _calculation = TextEditingController();
  final _calculationDigest = TextEditingController();
  final _rationale = TextEditingController();
  @override
  void initState() {
    super.initState();
    _rule = widget.rules.first.id;
  }

  @override
  void dispose() {
    for (final value in <TextEditingController>[
      _due,
      _instrument,
      _instrumentDigest,
      _calculation,
      _calculationDigest,
      _rationale,
    ]) {
      value.dispose();
    }
    super.dispose();
  }

  void _review() {
    final draft = DstEvidenceDraft(
      ruleEvidenceId: _rule,
      expectedTaxDue: _due.text.trim(),
      instrumentReference: _instrument.text.trim(),
      instrumentDigest: _instrumentDigest.text.trim(),
      calculationReference: _calculation.text.trim(),
      calculationDigest: _calculationDigest.text.trim(),
      managementRationale: _rationale.text.trim(),
    );
    try {
      draft.validate();
      Navigator.pop(context, draft);
    } on Object {
      _invalid(
        context,
        'Complete the exact retained DST calculation, references, fingerprints, and rationale.',
      );
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Record DST evidence'),
    content: SizedBox(
      width: 420,
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            _ruleDropdown(
              widget.rules,
              _rule,
              (value) => setState(() => _rule = value),
            ),
            _field(_due, 'Expected tax due'),
            _field(_instrument, 'Instrument reference'),
            _field(
              _instrumentDigest,
              'Instrument fingerprint (SHA-256)',
              maxLength: 64,
            ),
            _field(_calculation, 'Calculation reference'),
            _field(
              _calculationDigest,
              'Calculation fingerprint (SHA-256)',
              maxLength: 64,
            ),
            _field(_rationale, 'Management rationale', lines: 3),
          ],
        ),
      ),
    ),
    actions: <Widget>[
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Cancel'),
      ),
      FilledButton(onPressed: _review, child: const Text('Review evidence')),
    ],
  );
}

class _PercentageDialog extends StatefulWidget {
  const _PercentageDialog({required this.rules, required this.source});
  final List<TaxRuleEvidence> rules;
  final PercentageTaxReadiness source;
  @override
  State<_PercentageDialog> createState() => _PercentageDialogState();
}

class _PercentageDialogState extends State<_PercentageDialog> {
  late String _rule;
  final _taxable = TextEditingController();
  final _principal = TextEditingController();
  final _due = TextEditingController();
  final _reference = TextEditingController();
  final _digest = TextEditingController();
  final _rationale = TextEditingController();
  @override
  void initState() {
    super.initState();
    _rule = widget.rules.first.id;
  }

  @override
  void dispose() {
    for (final value in <TextEditingController>[
      _taxable,
      _principal,
      _due,
      _reference,
      _digest,
      _rationale,
    ]) {
      value.dispose();
    }
    super.dispose();
  }

  void _review() {
    final draft = PercentageTaxEvidenceDraft(
      ruleEvidenceId: _rule,
      taxableLendingReceiptAmount: _taxable.text.trim(),
      principalReceiptAmount: _principal.text.trim(),
      expectedTaxDue: _due.text.trim(),
      allocationReference: _reference.text.trim(),
      allocationDigest: _digest.text.trim(),
      managementRationale: _rationale.text.trim(),
    );
    try {
      draft.validate(widget.source.sourceCashAmount);
      Navigator.pop(context, draft);
    } on Object {
      _invalid(
        context,
        'Taxable receipt plus principal must exactly equal ${widget.source.sourceCashAmount}; complete the retained reference, fingerprint, due and rationale.',
      );
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Record percentage allocation'),
    content: SizedBox(
      width: 420,
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Text('Protected source cash: ${widget.source.sourceCashAmount}'),
            _ruleDropdown(
              widget.rules,
              _rule,
              (value) => setState(() => _rule = value),
            ),
            _field(
              _taxable,
              'Taxable lending receipt',
              key: const Key('tax-percentage-taxable'),
            ),
            _field(
              _principal,
              'Principal receipt',
              key: const Key('tax-percentage-principal'),
            ),
            _field(
              _due,
              'Expected tax due',
              key: const Key('tax-percentage-due'),
            ),
            _field(
              _reference,
              'Allocation reference',
              key: const Key('tax-allocation-reference'),
            ),
            _field(
              _digest,
              'Allocation fingerprint (SHA-256)',
              key: const Key('tax-allocation-digest'),
              maxLength: 64,
            ),
            _field(
              _rationale,
              'Management rationale',
              key: const Key('tax-evidence-rationale'),
              lines: 3,
            ),
          ],
        ),
      ),
    ),
    actions: <Widget>[
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Cancel'),
      ),
      FilledButton(
        key: const Key('review-percentage-tax-evidence'),
        onPressed: _review,
        child: const Text('Review evidence'),
      ),
    ],
  );
}

Widget _field(
  TextEditingController controller,
  String label, {
  Key? key,
  int lines = 1,
  int? maxLength,
}) => TextField(
  key: key,
  controller: controller,
  minLines: lines,
  maxLines: lines,
  maxLength: maxLength,
  decoration: InputDecoration(labelText: label),
);

Widget _ruleDropdown(
  List<TaxRuleEvidence> rules,
  String value,
  ValueChanged<String> changed,
) => DropdownButtonFormField<String>(
  initialValue: value,
  isExpanded: true,
  decoration: const InputDecoration(labelText: 'Approved rule evidence'),
  items: rules
      .map(
        (rule) => DropdownMenuItem(
          value: rule.id,
          child: Text(
            '${rule.ruleKey} v${rule.ruleVersion}',
            overflow: TextOverflow.ellipsis,
          ),
        ),
      )
      .toList(growable: false),
  onChanged: (value) {
    if (value != null) changed(value);
  },
);

void _invalid(BuildContext context, String message) => ScaffoldMessenger.of(
  context,
).showSnackBar(SnackBar(content: Text(message)));

class _Notice extends StatelessWidget {
  const _Notice(this.message);
  final String message;
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: Row(
        children: <Widget>[
          const Icon(Icons.info_outline),
          const SizedBox(width: 8),
          Expanded(child: Text(message)),
        ],
      ),
    ),
  );
}

class _Error extends StatelessWidget {
  const _Error({required this.message, required this.onRetry});
  final String message;
  final Future<void> Function() onRetry;
  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Text(message, textAlign: TextAlign.center),
          const SizedBox(height: 12),
          FilledButton(onPressed: onRetry, child: const Text('Try again')),
        ],
      ),
    ),
  );
}

String _taxType(String value) => value == 'documentary_stamp_tax'
    ? 'Documentary stamp tax'
    : 'Percentage tax — lending';
String _status(String value) => value.replaceAll('_', ' ');

String _newUuid() {
  final random = Random.secure();
  final bytes = List<int>.generate(16, (_) => random.nextInt(256));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  final hex = bytes
      .map((value) => value.toRadixString(16).padLeft(2, '0'))
      .join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
}

import 'package:flutter/material.dart';

enum ManagementReviewRisk { routine, privileged, protectedFinancial }

enum ManagementReviewWarningSeverity { information, caution, blocker }

enum ManagementMutationSurface {
  clientRegistration('client-registration'),
  renewalWorkflow('renewal-workflow'),
  staffInvitation('staff-invitation'),
  staffAccess('staff-access'),
  collectionVoid('collection-void'),
  contractCollection('contract-collection'),
  noCollection('no-collection'),
  clientSupport('client-support'),
  eclOutcomeReview('ecl-outcome-review'),
  fiscalPeriod('fiscal-period'),
  generalJournal('general-journal'),
  openingWorkbook('opening-workbook'),
  openingJournal('opening-journal'),
  periodClose('period-close'),
  eclAllowance('ecl-allowance'),
  eclA5('ecl-a5'),
  initialCapital('initial-capital'),
  taxEvidence('tax-evidence'),
  taxLiability('tax-liability'),
  taxSettlement('tax-settlement'),
  taxAdjustment('tax-adjustment'),
  additionalTax('additional-tax');

  const ManagementMutationSurface(this.id);

  final String id;
}

@immutable
class ManagementMutationSurfaceEntry {
  const ManagementMutationSurfaceEntry({
    required this.surface,
    required this.owner,
    required this.actions,
    required this.defaultRisk,
  });

  final ManagementMutationSurface surface;
  final String owner;
  final List<String> actions;
  final ManagementReviewRisk defaultRisk;
}

const managementMutationSurfaceCatalog = <ManagementMutationSurfaceEntry>[
  ManagementMutationSurfaceEntry(
    surface: ManagementMutationSurface.clientRegistration,
    owner: 'ClientRegistrationApprovalsPage',
    actions: <String>['approve and link', 'reject'],
    defaultRisk: ManagementReviewRisk.privileged,
  ),
  ManagementMutationSurfaceEntry(
    surface: ManagementMutationSurface.renewalWorkflow,
    owner: 'ManagementRenewalRequestsPage',
    actions: <String>[
      'record terms',
      'reject',
      'release to Collector',
      'review proof',
      'activate',
    ],
    defaultRisk: ManagementReviewRisk.privileged,
  ),
  ManagementMutationSurfaceEntry(
    surface: ManagementMutationSurface.staffInvitation,
    owner: 'ManagementStaffInvitePage',
    actions: <String>['invite', 'reconcile uncertain result'],
    defaultRisk: ManagementReviewRisk.privileged,
  ),
  ManagementMutationSurfaceEntry(
    surface: ManagementMutationSurface.staffAccess,
    owner: 'ManagementStaffDetailPage',
    actions: <String>[
      'change role',
      'change account status',
      'approve or revoke device',
    ],
    defaultRisk: ManagementReviewRisk.privileged,
  ),
  ManagementMutationSurfaceEntry(
    surface: ManagementMutationSurface.collectionVoid,
    owner: 'ManagementCollectionVoidPage',
    actions: <String>['void eligible collection'],
    defaultRisk: ManagementReviewRisk.protectedFinancial,
  ),
  ManagementMutationSurfaceEntry(
    surface: ManagementMutationSurface.contractCollection,
    owner: 'ManagementContractCollectionActivationPage',
    actions: <String>['activate', 'deactivate'],
    defaultRisk: ManagementReviewRisk.privileged,
  ),
  ManagementMutationSurfaceEntry(
    surface: ManagementMutationSurface.noCollection,
    owner: 'ManagementNoCollectionPage',
    actions: <String>['declare', 'reverse'],
    defaultRisk: ManagementReviewRisk.protectedFinancial,
  ),
  ManagementMutationSurfaceEntry(
    surface: ManagementMutationSurface.clientSupport,
    owner: 'ManagementSupportRequestsPage',
    actions: <String>['answer', 'resolve', 'cancel'],
    defaultRisk: ManagementReviewRisk.routine,
  ),
  ManagementMutationSurfaceEntry(
    surface: ManagementMutationSurface.eclOutcomeReview,
    owner: 'ManagementEclOutcomeReviewPage',
    actions: <String>['save historical outcome review'],
    defaultRisk: ManagementReviewRisk.privileged,
  ),
  ManagementMutationSurfaceEntry(
    surface: ManagementMutationSurface.fiscalPeriod,
    owner: 'ManagementFinancialAccountingPage',
    actions: <String>['create period', 'change status'],
    defaultRisk: ManagementReviewRisk.protectedFinancial,
  ),
  ManagementMutationSurfaceEntry(
    surface: ManagementMutationSurface.generalJournal,
    owner: 'ManagementGeneralJournalPage',
    actions: <String>[
      'create or edit draft',
      'post',
      'cancel',
      'create reversal draft',
    ],
    defaultRisk: ManagementReviewRisk.protectedFinancial,
  ),
  ManagementMutationSurfaceEntry(
    surface: ManagementMutationSurface.openingWorkbook,
    owner: 'ManagementOpeningBalanceWorkbookPage',
    actions: <String>['initialize', 'edit line or policy', 'change status'],
    defaultRisk: ManagementReviewRisk.protectedFinancial,
  ),
  ManagementMutationSurfaceEntry(
    surface: ManagementMutationSurface.openingJournal,
    owner: 'ManagementOpeningBalanceJournalPage',
    actions: <String>['prepare', 'post'],
    defaultRisk: ManagementReviewRisk.protectedFinancial,
  ),
  ManagementMutationSurfaceEntry(
    surface: ManagementMutationSurface.periodClose,
    owner: 'ManagementPeriodClosePage',
    actions: <String>['prepare', 'post'],
    defaultRisk: ManagementReviewRisk.protectedFinancial,
  ),
  ManagementMutationSurfaceEntry(
    surface: ManagementMutationSurface.eclAllowance,
    owner: 'ManagementEclAllowancePostingPage',
    actions: <String>['prepare', 'post'],
    defaultRisk: ManagementReviewRisk.protectedFinancial,
  ),
  ManagementMutationSurfaceEntry(
    surface: ManagementMutationSurface.eclA5,
    owner: 'ManagementEclA5AccountingPage',
    actions: <String>[
      'post remeasurement',
      'post full write-off',
      'review recovery evidence',
      'post recovery',
    ],
    defaultRisk: ManagementReviewRisk.protectedFinancial,
  ),
  ManagementMutationSurfaceEntry(
    surface: ManagementMutationSurface.initialCapital,
    owner: 'ManagementInitialCapitalFundingPage',
    actions: <String>['record evidence', 'prepare', 'post'],
    defaultRisk: ManagementReviewRisk.protectedFinancial,
  ),
  ManagementMutationSurfaceEntry(
    surface: ManagementMutationSurface.taxEvidence,
    owner: 'ManagementTaxEvidencePage',
    actions: <String>[
      'record rule',
      'record DST',
      'record percentage allocation',
    ],
    defaultRisk: ManagementReviewRisk.protectedFinancial,
  ),
  ManagementMutationSurfaceEntry(
    surface: ManagementMutationSurface.taxLiability,
    owner: 'ManagementTaxLiabilityPage',
    actions: <String>['prepare', 'post'],
    defaultRisk: ManagementReviewRisk.protectedFinancial,
  ),
  ManagementMutationSurfaceEntry(
    surface: ManagementMutationSurface.taxSettlement,
    owner: 'ManagementTaxSettlementPage',
    actions: <String>['record return', 'record payment', 'prepare', 'post'],
    defaultRisk: ManagementReviewRisk.protectedFinancial,
  ),
  ManagementMutationSurfaceEntry(
    surface: ManagementMutationSurface.taxAdjustment,
    owner: 'ManagementTaxAdjustmentPage',
    actions: <String>['record evidence', 'prepare', 'post'],
    defaultRisk: ManagementReviewRisk.protectedFinancial,
  ),
  ManagementMutationSurfaceEntry(
    surface: ManagementMutationSurface.additionalTax,
    owner: 'ManagementAdditionalTaxPage',
    actions: <String>[
      'record amendment evidence',
      'prepare liability',
      'post liability',
      'record payment evidence',
      'prepare settlement',
      'post settlement',
    ],
    defaultRisk: ManagementReviewRisk.protectedFinancial,
  ),
];

@immutable
class ManagementReviewFact {
  const ManagementReviewFact({required this.label, required this.value});

  final String label;
  final String value;
}

@immutable
class ManagementReviewWarning {
  const ManagementReviewWarning({
    required this.severity,
    required this.message,
  });

  final ManagementReviewWarningSeverity severity;
  final String message;
}

@immutable
class ManagementReviewPresentation {
  const ManagementReviewPresentation._({
    required this.surface,
    required this.recordLabel,
    required this.recordValue,
    required this.statusLabel,
    required this.statusDetail,
    required this.facts,
    required this.warnings,
    required this.nextActionLabel,
    required this.consequence,
    required this.risk,
    required this.secondaryReferences,
    required this.actionEnabled,
  });

  factory ManagementReviewPresentation.validated({
    required ManagementMutationSurface surface,
    required String recordLabel,
    required String recordValue,
    required String statusLabel,
    String? statusDetail,
    List<ManagementReviewFact> facts = const <ManagementReviewFact>[],
    List<ManagementReviewWarning> warnings = const <ManagementReviewWarning>[],
    required String nextActionLabel,
    required String consequence,
    required ManagementReviewRisk risk,
    List<ManagementReviewFact> secondaryReferences =
        const <ManagementReviewFact>[],
    bool actionEnabled = true,
  }) {
    _requireText(recordLabel, 'recordLabel');
    _requireText(recordValue, 'recordValue');
    _requireText(statusLabel, 'statusLabel');
    _requireText(nextActionLabel, 'nextActionLabel');
    _requireText(consequence, 'consequence');
    for (final fact in <ManagementReviewFact>[
      ...facts,
      ...secondaryReferences,
    ]) {
      _requireText(fact.label, 'fact.label');
      _requireText(fact.value, 'fact.value');
    }
    for (final warning in warnings) {
      _requireText(warning.message, 'warning.message');
    }
    final hasBlocker = warnings.any(
      (warning) => warning.severity == ManagementReviewWarningSeverity.blocker,
    );
    if (hasBlocker && actionEnabled) {
      throw ArgumentError.value(
        actionEnabled,
        'actionEnabled',
        'A blocking server warning requires a disabled action.',
      );
    }
    return ManagementReviewPresentation._(
      surface: surface,
      recordLabel: recordLabel.trim(),
      recordValue: recordValue.trim(),
      statusLabel: statusLabel.trim(),
      statusDetail: _optionalText(statusDetail),
      facts: List<ManagementReviewFact>.unmodifiable(facts),
      warnings: List<ManagementReviewWarning>.unmodifiable(warnings),
      nextActionLabel: nextActionLabel.trim(),
      consequence: consequence.trim(),
      risk: risk,
      secondaryReferences: List<ManagementReviewFact>.unmodifiable(
        secondaryReferences,
      ),
      actionEnabled: actionEnabled,
    );
  }

  final ManagementMutationSurface surface;
  final String recordLabel;
  final String recordValue;
  final String statusLabel;
  final String? statusDetail;
  final List<ManagementReviewFact> facts;
  final List<ManagementReviewWarning> warnings;
  final String nextActionLabel;
  final String consequence;
  final ManagementReviewRisk risk;
  final List<ManagementReviewFact> secondaryReferences;
  final bool actionEnabled;

  Key get key => Key('management-review-${surface.id}');
}

String plainManagementStatus(
  String? raw,
  Map<String, String> known, {
  String missing = 'Not provided by the server',
}) {
  final normalized = raw?.trim().toLowerCase() ?? '';
  if (normalized.isEmpty) return missing;
  return known[normalized] ?? 'Status needs review';
}

class ManagementReviewPanel extends StatelessWidget {
  const ManagementReviewPanel({
    required this.review,
    this.compact = false,
    super.key,
  });

  final ManagementReviewPresentation review;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final background = switch (review.risk) {
      ManagementReviewRisk.routine => colorScheme.surfaceContainerLow,
      ManagementReviewRisk.privileged => colorScheme.secondaryContainer,
      ManagementReviewRisk.protectedFinancial => colorScheme.errorContainer,
    };
    return Semantics(
      container: true,
      explicitChildNodes: true,
      label: '${_riskLabel(review.risk)} Management review',
      child: Card(
        key: review.key,
        color: background,
        margin: compact ? EdgeInsets.zero : const EdgeInsets.all(12),
        child: Padding(
          padding: EdgeInsets.all(compact ? 12 : 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              _ReviewSection(
                heading: 'Reviewing',
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(review.recordLabel, style: theme.textTheme.labelLarge),
                    const SizedBox(height: 2),
                    Text(review.recordValue),
                    if (review.facts.isNotEmpty) ...<Widget>[
                      const SizedBox(height: 8),
                      ...review.facts.map(_ReviewFactRow.new),
                    ],
                    if (review.secondaryReferences.isNotEmpty) ...<Widget>[
                      const SizedBox(height: 8),
                      SelectionArea(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: review.secondaryReferences
                              .map(_ReviewFactRow.new)
                              .toList(),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              _ReviewSection(
                heading: 'Current status',
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(review.statusLabel),
                    if (review.statusDetail != null) ...<Widget>[
                      const SizedBox(height: 2),
                      Text(
                        review.statusDetail!,
                        style: theme.textTheme.bodySmall,
                      ),
                    ],
                  ],
                ),
              ),
              _ReviewSection(
                heading: 'Check before continuing',
                child: review.warnings.isEmpty
                    ? const Text('No server warnings')
                    : Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: review.warnings
                            .map((warning) => _WarningRow(warning: warning))
                            .toList(),
                      ),
              ),
              _ReviewSection(
                heading: 'Next action',
                child: Text(review.nextActionLabel),
              ),
              _ReviewSection(
                heading: 'If confirmed',
                last: true,
                child: Text(review.consequence),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

Future<bool> showManagementReviewConfirmation(
  BuildContext context,
  ManagementReviewPresentation review,
) async {
  final confirmed = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(review.nextActionLabel),
      content: SingleChildScrollView(
        child: ManagementReviewPanel(review: review, compact: true),
      ),
      actions: <Widget>[
        TextButton(
          key: Key('cancel-${review.surface.id}'),
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Cancel'),
        ),
        FilledButton(
          key: Key('confirm-${review.surface.id}'),
          style: review.risk == ManagementReviewRisk.protectedFinancial
              ? FilledButton.styleFrom(
                  backgroundColor: Theme.of(context).colorScheme.error,
                  foregroundColor: Theme.of(context).colorScheme.onError,
                )
              : null,
          onPressed: review.actionEnabled
              ? () => Navigator.of(context).pop(true)
              : null,
          child: Text(review.nextActionLabel),
        ),
      ],
    ),
  );
  return confirmed == true;
}

class _ReviewSection extends StatelessWidget {
  const _ReviewSection({
    required this.heading,
    required this.child,
    this.last = false,
  });

  final String heading;
  final Widget child;
  final bool last;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: last ? 0 : 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Semantics(
            header: true,
            child: Text(heading, style: Theme.of(context).textTheme.titleSmall),
          ),
          const SizedBox(height: 4),
          child,
        ],
      ),
    );
  }
}

class _ReviewFactRow extends StatelessWidget {
  const _ReviewFactRow(this.fact);

  final ManagementReviewFact fact;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 3),
      child: Wrap(
        spacing: 6,
        runSpacing: 2,
        children: <Widget>[
          Text(fact.label, style: Theme.of(context).textTheme.labelMedium),
          Text(fact.value),
        ],
      ),
    );
  }
}

class _WarningRow extends StatelessWidget {
  const _WarningRow({required this.warning});

  final ManagementReviewWarning warning;

  @override
  Widget build(BuildContext context) {
    final (label, icon) = switch (warning.severity) {
      ManagementReviewWarningSeverity.information => (
        'Information',
        Icons.info_outline,
      ),
      ManagementReviewWarningSeverity.caution => (
        'Caution',
        Icons.warning_amber_outlined,
      ),
      ManagementReviewWarningSeverity.blocker => (
        'Blocker',
        Icons.block_outlined,
      ),
    };
    return Semantics(
      container: true,
      label: '$label: ${warning.message}',
      child: ExcludeSemantics(
        child: Padding(
          padding: const EdgeInsets.only(bottom: 6),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Icon(icon, size: 20),
              const SizedBox(width: 8),
              Expanded(child: Text('$label: ${warning.message}')),
            ],
          ),
        ),
      ),
    );
  }
}

void _requireText(String value, String name) {
  if (value.trim().isEmpty) {
    throw ArgumentError.value(value, name, 'Must not be blank.');
  }
}

String? _optionalText(String? value) {
  final normalized = value?.trim() ?? '';
  return normalized.isEmpty ? null : normalized;
}

String _riskLabel(ManagementReviewRisk risk) {
  return switch (risk) {
    ManagementReviewRisk.routine => 'Routine',
    ManagementReviewRisk.privileged => 'Privileged',
    ManagementReviewRisk.protectedFinancial => 'Protected financial',
  };
}

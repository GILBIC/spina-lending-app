import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/ecl_outcome_review.dart';
import 'package:gilbic_mobile/src/core/management/ecl_outcome_review_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

class ManagementEclOutcomeReviewPage extends StatefulWidget {
  const ManagementEclOutcomeReviewPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final EclOutcomeReviewRepository? repository;

  @override
  State<ManagementEclOutcomeReviewPage> createState() =>
      _ManagementEclOutcomeReviewPageState();
}

class _ManagementEclOutcomeReviewPageState
    extends State<ManagementEclOutcomeReviewPage> {
  static const int _pageSize = 50;

  late final EclOutcomeReviewRepository _repository;
  EclOutcomeReviewQueueData? _data;
  String _filter = 'pending';
  int _offset = 0;
  bool _loading = true;
  bool _submitting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaEclOutcomeReviewRepository();
    _load();
  }

  Future<void> _load({String? filter, int? offset}) async {
    final nextFilter = filter ?? _filter;
    final nextOffset = offset ?? _offset;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final data = await _repository.loadQueue(
        widget.session,
        deviceId: identity.installationId,
        status: nextFilter,
        limit: _pageSize,
        offset: nextOffset,
      );
      if (!mounted) return;
      setState(() {
        _filter = nextFilter;
        _offset = nextOffset;
        _data = data;
      });
    } on SpinaApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) {
        setState(
          () => _error = 'Historical outcome review could not be loaded.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _review(EclOutcomeReviewEpisode episode) async {
    final data = _data;
    if (data == null || !data.reviewPermission || episode.sourceBlocked) return;

    final draft = await showDialog<_ReviewDraft>(
      context: context,
      barrierDismissible: false,
      builder: (context) => _ReviewDialog(episode: episode),
    );
    if (draft == null || !mounted) return;
    final confirmed = await showManagementReviewConfirmation(
      context,
      _eclReviewPresentation(episode, draft: draft),
    );
    if (!confirmed || !mounted) return;

    setState(() => _submitting = true);
    try {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.reviewOutcome(
        widget.session,
        deviceId: identity.installationId,
        historicalEpisodeId: episode.historicalEpisodeId,
        defaultLabel: draft.defaultLabel,
        evidenceBasis: draft.evidenceBasis,
        evidenceReference: draft.evidenceReference,
        reviewNote: draft.reviewNote,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Outcome review recorded. No ECL amount or journal was created.',
          ),
        ),
      );
      await _load(offset: _offset);
    } on SpinaApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(error.message)));
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Outcome review could not be saved.')),
        );
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Historical Outcome Review'),
        actions: [
          IconButton(
            tooltip: 'Refresh historical outcome review',
            onPressed: _loading || _submitting ? null : () => _load(),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(child: _body()),
    );
  }

  Widget _body() {
    final data = _data;
    if (_loading && data == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null && data == null) {
      return _ErrorState(message: _error!, onRetry: _load);
    }
    if (data == null) return const SizedBox.shrink();

    final previousOffset = _offset <= _pageSize ? 0 : _offset - _pageSize;
    return RefreshIndicator(
      onRefresh: () => _load(),
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          _NoticeCard(notice: data.notice),
          const SizedBox(height: 12),
          _SummaryCard(summary: data.summary),
          const SizedBox(height: 12),
          if (!data.reviewPermission) ...[
            const Card(
              child: Padding(
                padding: EdgeInsets.all(14),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.lock_outline),
                    SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'You can view this queue, but accounting.ecl.review permission is required to record or revise an outcome.',
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
          ],
          _FilterBar(
            value: _filter,
            disabled: _loading || _submitting,
            onChanged: (value) => _load(filter: value, offset: 0),
          ),
          const SizedBox(height: 12),
          if (_error != null) ...[
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(_error!),
              ),
            ),
            const SizedBox(height: 12),
          ],
          Row(
            children: [
              Expanded(
                child: Text(
                  '${_filterLabel(_filter)} • ${data.episodes.length} shown',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              if (_loading)
                const SizedBox.square(
                  dimension: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
            ],
          ),
          const SizedBox(height: 8),
          if (data.episodes.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(20),
                child: Text('No historical episodes match this filter.'),
              ),
            )
          else
            for (final episode in data.episodes) ...[
              _EpisodeCard(
                episode: episode,
                canReview: data.reviewPermission && !_submitting,
                onReview: () => _review(episode),
              ),
              const SizedBox(height: 8),
            ],
          const SizedBox(height: 6),
          _Pagination(
            offset: _offset,
            pageSize: _pageSize,
            hasNext: data.episodes.length == _pageSize,
            disabled: _loading || _submitting,
            onPrevious: () => _load(offset: previousOffset),
            onNext: () => _load(offset: _offset + _pageSize),
          ),
          const SizedBox(height: 12),
          const Card(
            child: Padding(
              padding: EdgeInsets.all(14),
              child: Text(
                "This historical credit-outcome review records only Management's reviewed default/non-default outcomes. Renewal, archive, deletion, cash totals and arrears are evidence to inspect, not automatic labels. Loss, recovery, PD, LGD, ECL amount, opening-balance values and General Ledger posting remain outside this review.",
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _NoticeCard extends StatelessWidget {
  const _NoticeCard({required this.notice});

  final String notice;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: const Key('ecl-outcome-review-notice'),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.fact_check_outlined),
            const SizedBox(width: 10),
            Expanded(child: Text(notice)),
          ],
        ),
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({required this.summary});

  final EclOutcomeReviewSummary summary;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: const Key('ecl-outcome-review-summary'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.rule_folder_outlined),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Historical credit-outcome review progress',
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                ),
                Chip(label: Text(_status(summary.reviewStatus))),
              ],
            ),
            const SizedBox(height: 8),
            _Row(
              label: 'Historical episodes',
              value: '${summary.episodeCount}',
            ),
            _Row(
              label: 'Usable for outcome review',
              value: '${summary.structurallyUsableCount}',
            ),
            _Row(
              label: 'Source review required',
              value: '${summary.sourceReviewRequiredCount}',
            ),
            _Row(
              label: 'Pending outcome review',
              value: '${summary.pendingOutcomeReviewCount}',
            ),
            _Row(label: 'Reviewed', value: '${summary.reviewedOutcomeCount}'),
            _Row(
              label: 'Reviewed default',
              value: '${summary.reviewedDefaultCount}',
            ),
            _Row(
              label: 'Reviewed non-default',
              value: '${summary.reviewedNonDefaultCount}',
            ),
            _Row(
              label: 'ECL included',
              value: summary.eclIncluded ? 'Yes' : 'No',
            ),
            _Row(
              label: 'ECL amount',
              value: summary.eclAmount == null
                  ? 'Not calculated'
                  : _money(summary.eclAmount!),
            ),
            _Row(
              label: 'Ready for evidence review',
              value: summary.readyToPost ? 'Yes' : 'No',
            ),
          ],
        ),
      ),
    );
  }
}

class _FilterBar extends StatelessWidget {
  const _FilterBar({
    required this.value,
    required this.disabled,
    required this.onChanged,
  });

  final String value;
  final bool disabled;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    const filters = <String>['pending', 'reviewed', 'source_review', 'all'];
    return Wrap(
      spacing: 8,
      runSpacing: 6,
      children: [
        for (final filter in filters)
          ChoiceChip(
            key: Key('ecl-filter-$filter'),
            label: Text(_filterLabel(filter)),
            selected: value == filter,
            onSelected: disabled
                ? null
                : (selected) {
                    if (selected && filter != value) onChanged(filter);
                  },
          ),
      ],
    );
  }
}

class _EpisodeCard extends StatelessWidget {
  const _EpisodeCard({
    required this.episode,
    required this.canReview,
    required this.onReview,
  });

  final EclOutcomeReviewEpisode episode;
  final bool canReview;
  final VoidCallback onReview;

  @override
  Widget build(BuildContext context) {
    final label = episode.explicitDefaultLabel;
    return Card(
      key: Key('ecl-outcome-review-${episode.historicalEpisodeId}'),
      child: ExpansionTile(
        title: Text(
          '${_loanType(episode.loanType)} • Episode ${episode.episodeSequence}',
        ),
        subtitle: Text(
          '${_dateOrDash(episode.releaseDate)} • ${_money(episode.principal)} • ${_shortKey(episode.borrowerKey)}',
        ),
        trailing: Chip(
          label: Text(
            episode.sourceBlocked
                ? 'Source review'
                : label == null
                ? 'Pending'
                : label
                ? 'Default'
                : 'Non-default',
          ),
        ),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
        children: [
          _Row(label: 'Episode key', value: episode.episodeKey),
          _Row(label: 'Source event', value: _status(episode.sourceEvent)),
          _Row(label: 'Released', value: _dateOrDash(episode.releaseDate)),
          _Row(label: 'Due', value: _dateOrDash(episode.dueDate)),
          _Row(label: 'Principal', value: _money(episode.principal)),
          _Row(
            label: 'Contractual total',
            value: episode.contractualTotal == null
                ? '—'
                : _money(episode.contractualTotal!),
          ),
          _Row(label: 'Observed cash', value: _money(episode.cashCollected)),
          _Row(
            label: 'Positive payments',
            value: '${episode.positivePaymentCount}',
          ),
          _Row(
            label: 'Zero-payment observations',
            value: '${episode.zeroPaymentObservationCount}',
          ),
          _Row(
            label: 'Observed collection days',
            value: '${episode.observedCollectionDays}',
          ),
          _Row(
            label: 'Lifecycle evidence',
            value: _status(episode.outcomeEvidence ?? 'none'),
          ),
          _Row(
            label: 'Outcome evidence date',
            value: _dateOrDash(episode.outcomeDate),
          ),
          if (episode.renewalRolloverAmount != null)
            _Row(
              label: 'Renewal rollover',
              value: _money(episode.renewalRolloverAmount!),
            ),
          const SizedBox(height: 8),
          if (episode.sourceBlocked)
            ManagementReviewPanel(
              review: _eclReviewPresentation(episode),
              compact: true,
            )
          else if (episode.reviewed) ...[
            _ReviewHistory(episode: episode),
            const SizedBox(height: 10),
          ],
          if (!episode.sourceBlocked)
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton.icon(
                key: Key('review-outcome-${episode.historicalEpisodeId}'),
                onPressed: canReview ? onReview : null,
                icon: Icon(
                  episode.reviewed
                      ? Icons.edit_note
                      : Icons.fact_check_outlined,
                ),
                label: Text(
                  episode.reviewed ? 'Revise review' : 'Review outcome',
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _ReviewHistory extends StatelessWidget {
  const _ReviewHistory({required this.episode});

  final EclOutcomeReviewEpisode episode;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Latest reviewed outcome: ${episode.explicitDefaultLabel == true ? 'Default' : 'Non-default'}',
            style: Theme.of(context).textTheme.titleSmall,
          ),
          const SizedBox(height: 6),
          _Row(label: 'Review version', value: '${episode.reviewVersion ?? 1}'),
          _Row(
            label: 'Evidence basis',
            value: _status(episode.evidenceBasis ?? 'not_recorded'),
          ),
          _Row(
            label: 'Evidence reference',
            value: episode.evidenceReference ?? '—',
          ),
          _Row(label: 'Reviewer', value: episode.reviewerName ?? '—'),
          _Row(
            label: 'Reviewed at',
            value: _dateTimeOrDash(episode.reviewedAt),
          ),
          const SizedBox(height: 6),
          Text(episode.reviewNote ?? 'No review note recorded.'),
        ],
      ),
    );
  }
}

class _Pagination extends StatelessWidget {
  const _Pagination({
    required this.offset,
    required this.pageSize,
    required this.hasNext,
    required this.disabled,
    required this.onPrevious,
    required this.onNext,
  });

  final int offset;
  final int pageSize;
  final bool hasNext;
  final bool disabled;
  final VoidCallback onPrevious;
  final VoidCallback onNext;

  @override
  Widget build(BuildContext context) {
    final page = (offset ~/ pageSize) + 1;
    return Row(
      children: [
        OutlinedButton.icon(
          onPressed: disabled || offset == 0 ? null : onPrevious,
          icon: const Icon(Icons.chevron_left),
          label: const Text('Previous'),
        ),
        Expanded(child: Center(child: Text('Page $page'))),
        OutlinedButton.icon(
          onPressed: disabled || !hasNext ? null : onNext,
          icon: const Icon(Icons.chevron_right),
          label: const Text('Next'),
        ),
      ],
    );
  }
}

class _ReviewDialog extends StatefulWidget {
  const _ReviewDialog({required this.episode});

  final EclOutcomeReviewEpisode episode;

  @override
  State<_ReviewDialog> createState() => _ReviewDialogState();
}

class _ReviewDialogState extends State<_ReviewDialog> {
  bool? _defaultLabel;
  String _basis = 'source_document';
  final _reference = TextEditingController();
  final _note = TextEditingController();

  @override
  void initState() {
    super.initState();
    _defaultLabel = widget.episode.explicitDefaultLabel;
    _basis = widget.episode.evidenceBasis ?? 'source_document';
    _reference.text = widget.episode.evidenceReference ?? '';
    _note.text = widget.episode.reviewNote ?? '';
  }

  @override
  void dispose() {
    _reference.dispose();
    _note.dispose();
    super.dispose();
  }

  bool get _valid =>
      _defaultLabel != null &&
      _reference.text.trim().isNotEmpty &&
      _note.text.trim().isNotEmpty;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Record reviewed outcome'),
      content: SizedBox(
        width: 520,
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Choose the outcome only from reviewed evidence. The system will not infer the answer from renewal, archive, deletion, payments or arrears.',
              ),
              const SizedBox(height: 14),
              Text('Episode: ${widget.episode.episodeKey}'),
              const SizedBox(height: 12),
              SegmentedButton<bool>(
                key: const Key('ecl-outcome-decision'),
                segments: const [
                  ButtonSegment<bool>(
                    value: false,
                    icon: Icon(Icons.check_circle_outline),
                    label: Text('Non-default'),
                  ),
                  ButtonSegment<bool>(
                    value: true,
                    icon: Icon(Icons.report_gmailerrorred_outlined),
                    label: Text('Default'),
                  ),
                ],
                emptySelectionAllowed: true,
                selected: _defaultLabel == null
                    ? <bool>{}
                    : <bool>{_defaultLabel!},
                onSelectionChanged: (selection) {
                  setState(() {
                    _defaultLabel = selection.isEmpty ? null : selection.first;
                  });
                },
              ),
              const SizedBox(height: 14),
              DropdownButtonFormField<String>(
                key: const Key('ecl-evidence-basis'),
                initialValue: _basis,
                decoration: const InputDecoration(labelText: 'Evidence basis'),
                items: const [
                  DropdownMenuItem(
                    value: 'source_document',
                    child: Text('Source document'),
                  ),
                  DropdownMenuItem(
                    value: 'collection_history',
                    child: Text('Collection history'),
                  ),
                  DropdownMenuItem(
                    value: 'renewal_settlement',
                    child: Text('Renewal settlement'),
                  ),
                  DropdownMenuItem(
                    value: 'management_review',
                    child: Text('Management review'),
                  ),
                ],
                onChanged: (value) {
                  if (value != null) setState(() => _basis = value);
                },
              ),
              const SizedBox(height: 12),
              TextField(
                key: const Key('ecl-evidence-reference'),
                controller: _reference,
                maxLength: 300,
                decoration: const InputDecoration(
                  labelText: 'Evidence reference',
                  hintText:
                      'Document, ledger period, settlement reference, or review file',
                ),
                onChanged: (_) => setState(() {}),
              ),
              const SizedBox(height: 8),
              TextField(
                key: const Key('ecl-review-note'),
                controller: _note,
                maxLength: 1000,
                minLines: 3,
                maxLines: 6,
                decoration: const InputDecoration(
                  labelText: 'Review note',
                  hintText:
                      'Explain the evidence supporting this reviewed outcome',
                ),
                onChanged: (_) => setState(() {}),
              ),
              const SizedBox(height: 6),
              const Text(
                'Saving creates an immutable review-history version. It does not calculate loss, recovery, PD, LGD or ECL and does not post to the General Ledger.',
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
          key: const Key('save-ecl-outcome-review'),
          onPressed: !_valid
              ? null
              : () {
                  Navigator.of(context).pop(
                    _ReviewDraft(
                      defaultLabel: _defaultLabel!,
                      evidenceBasis: _basis,
                      evidenceReference: _reference.text.trim(),
                      reviewNote: _note.text.trim(),
                    ),
                  );
                },
          child: const Text('Record review'),
        ),
      ],
    );
  }
}

class _ReviewDraft {
  const _ReviewDraft({
    required this.defaultLabel,
    required this.evidenceBasis,
    required this.evidenceReference,
    required this.reviewNote,
  });

  final bool defaultLabel;
  final String evidenceBasis;
  final String evidenceReference;
  final String reviewNote;
}

ManagementReviewPresentation _eclReviewPresentation(
  EclOutcomeReviewEpisode episode, {
  _ReviewDraft? draft,
}) {
  final sourceBlocked = episode.sourceBlocked;
  final sourceStatus =
      plainManagementStatus(episode.sourceQualityStatus, const <String, String>{
        'ready_for_outcome_labeling': 'Source data ready for outcome labeling',
        'source_review_required': 'Source evidence needs review',
      });
  final outcomeStatus = plainManagementStatus(
    episode.reviewStatus,
    const <String, String>{
      'outcome_review_required': 'Outcome review is pending',
      'reviewed': 'An outcome review version already exists',
      'source_review_required': 'Outcome labeling is blocked by source review',
    },
  );
  return ManagementReviewPresentation.validated(
    surface: ManagementMutationSurface.eclOutcomeReview,
    recordLabel: 'Historical outcome episode',
    recordValue:
        '${_loanType(episode.loanType)} • Episode ${episode.episodeSequence}',
    statusLabel: sourceStatus,
    statusDetail: 'Outcome review: $outcomeStatus',
    facts: <ManagementReviewFact>[
      if (episode.outcomeEvidence?.trim().isNotEmpty == true)
        ManagementReviewFact(
          label: 'Lifecycle evidence',
          value: _status(episode.outcomeEvidence!),
        ),
      if (draft != null) ...<ManagementReviewFact>[
        ManagementReviewFact(
          label: 'Reviewed outcome',
          value: draft.defaultLabel ? 'Default' : 'Non-default',
        ),
        ManagementReviewFact(
          label: 'Evidence basis',
          value: _status(draft.evidenceBasis),
        ),
        ManagementReviewFact(
          label: 'Evidence reference',
          value: draft.evidenceReference,
        ),
        ManagementReviewFact(label: 'Review note', value: draft.reviewNote),
      ],
    ],
    warnings: sourceBlocked
        ? <ManagementReviewWarning>[
            ManagementReviewWarning(
              severity: ManagementReviewWarningSeverity.blocker,
              message:
                  episode.sourceQualityNote ??
                  'This episode requires source review before outcome labeling.',
            ),
          ]
        : const <ManagementReviewWarning>[],
    nextActionLabel: sourceBlocked
        ? 'Resolve source evidence before labeling'
        : 'Record historical outcome review',
    consequence: sourceBlocked
        ? 'No outcome label can be saved until source evidence is reviewed and the server returns the episode to the outcome queue.'
        : 'A new immutable historical outcome-review version will be saved. '
              'This does not calculate loss, recovery, PD, LGD or ECL and does not '
              'post to the General Ledger.',
    risk: ManagementReviewRisk.privileged,
    secondaryReferences: <ManagementReviewFact>[
      ManagementReviewFact(label: 'Episode key', value: episode.episodeKey),
    ],
    actionEnabled: !sourceBlocked,
  );
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

class _Row extends StatelessWidget {
  const _Row({required this.label, required this.value});

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

String _filterLabel(String value) => switch (value) {
  'pending' => 'Pending',
  'reviewed' => 'Reviewed',
  'source_review' => 'Source review',
  'all' => 'All',
  _ => _status(value),
};

String _loanType(String value) => switch (value.toLowerCase()) {
  'regular' => 'Regular',
  '7x7' => '7x7',
  'seven_by_seven' => '7x7',
  _ => _status(value),
};

String _status(String value) => value
    .split('_')
    .where((part) => part.isNotEmpty)
    .map((part) => '${part[0].toUpperCase()}${part.substring(1)}')
    .join(' ');

String _dateOrDash(DateTime? value) {
  if (value == null) return '—';
  final month = value.month.toString().padLeft(2, '0');
  final day = value.day.toString().padLeft(2, '0');
  return '${value.year}-$month-$day';
}

String _dateTimeOrDash(DateTime? value) {
  if (value == null) return '—';
  final local = value.toLocal();
  final hour = local.hour.toString().padLeft(2, '0');
  final minute = local.minute.toString().padLeft(2, '0');
  return '${_dateOrDash(local)} $hour:$minute';
}

String _shortKey(String value) {
  if (value.length <= 12) return value;
  return '${value.substring(0, 12)}…';
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

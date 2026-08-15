import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_grouping.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

/// End-of-route review across every area assigned to the signed-in Collector.
///
/// This page is deliberately read-only. It summarizes the same authoritative
/// route snapshot used by Daily Route and never creates a financial write.
class CollectorMasterReviewPage extends StatefulWidget {
  const CollectorMasterReviewPage({
    required this.session,
    required this.loader,
    super.key,
  });

  final UserSession session;
  final CollectorRouteLoader loader;

  @override
  State<CollectorMasterReviewPage> createState() =>
      _CollectorMasterReviewPageState();
}

class _CollectorMasterReviewPageState extends State<CollectorMasterReviewPage> {
  CollectorRouteLoadResult? _result;
  Object? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await widget.loader.loadToday(widget.session);
      if (mounted) {
        setState(() => _result = result);
      }
    } on Object catch (error) {
      if (mounted) {
        setState(() => _error = error);
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: const Key('collector-master-review-page'),
      appBar: AppBar(
        title: const Text('Master Review'),
        actions: [
          IconButton(
            tooltip: 'Refresh review',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: SafeArea(child: _buildBody(context)),
    );
  }

  Widget _buildBody(BuildContext context) {
    final result = _result;
    if (_loading && result == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (result == null) {
      return _ReviewLoadError(
        message: _error?.toString() ?? 'Master Review could not be loaded.',
        onRetry: _load,
      );
    }

    final route = result.route;
    final areas = groupCollectorRoute(route);
    final reviews = areas
        .expand((area) => area.clients)
        .map((client) => _ClientReview.from(client, route.routeDate))
        .toList(growable: false);
    final unresolved = reviews.where((review) => review.needsAction).toList();
    final attention = reviews.where((review) => review.needsAttention).toList();
    final gcash = reviews.where((review) => review.hasExplicitGcashNote).toList();
    final complete = reviews.length - unresolved.length;

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 26),
        children: [
          _MasterHeader(
            result: result,
            route: route,
            clientCount: reviews.length,
            completeCount: complete,
            unresolvedCount: unresolved.length,
            attentionCount: attention.length,
            gcashCount: gcash.length,
          ),
          if (result.warning != null) ...[
            const SizedBox(height: 10),
            _ReadOnlyNotice(
              message: result.warning!,
              offline: result.isFromCache,
            ),
          ],
          if (_error != null) ...[
            const SizedBox(height: 10),
            _ReadOnlyNotice(
              message: 'The last refresh failed: $_error',
              offline: result.isFromCache,
            ),
          ],
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: Text(
                  'Area completion',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              Text('${areas.length} areas'),
            ],
          ),
          const SizedBox(height: 8),
          for (final area in areas) ...[
            _AreaReviewCard(area: area, routeDate: route.routeDate),
            const SizedBox(height: 8),
          ],
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: Text(
                  'Who still needs action',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              Text('${unresolved.length} clients'),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            'This is the end-of-route check across all assigned areas. '
            'Resolve or deliberately review every client before finishing the day.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 8),
          if (unresolved.isEmpty)
            const _AllDoneCard()
          else
            for (final review in unresolved) ...[
              _OutstandingClientCard(review: review),
              const SizedBox(height: 8),
            ],
          if (reviews.any((review) => review.hasReviewedException)) ...[
            const SizedBox(height: 10),
            Text(
              'Reviewed exceptions / covered today',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 4),
            Text(
              'ADV/PASS and other already-recorded exceptions stay visible here '
              'so the Collector can verify them without treating them as missing cash.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 8),
            for (final review in reviews.where(
              (item) => item.hasReviewedException,
            )) ...[
              _ReviewedExceptionCard(review: review),
              const SizedBox(height: 8),
            ],
          ],
          const SizedBox(height: 6),
          Text(
            result.isFromCache
                ? 'Offline copy: Master Review is read-only. Reconnect and refresh before recording any collection.'
                : 'Master Review is read-only. Record or correct payments from the protected Daily Route flow.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _MasterHeader extends StatelessWidget {
  const _MasterHeader({
    required this.result,
    required this.route,
    required this.clientCount,
    required this.completeCount,
    required this.unresolvedCount,
    required this.attentionCount,
    required this.gcashCount,
  });

  final CollectorRouteLoadResult result;
  final CollectorRoute route;
  final int clientCount;
  final int completeCount;
  final int unresolvedCount;
  final int attentionCount;
  final int gcashCount;

  @override
  Widget build(BuildContext context) {
    final date = route.routeDate == null ? 'Saved route' : _date(route.routeDate!);
    return Container(
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: SpinaTheme.brandPinkSoft,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFFF0D6E1)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'All-area collection check',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        color: SpinaTheme.brandPinkDark,
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              _StateChip(
                label: result.isFromCache ? 'OFFLINE COPY' : 'ONLINE',
                warning: result.isFromCache,
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text('${route.collectorName} • $date'),
          const SizedBox(height: 4),
          const Text(
            'Before leaving the route, check everyone who was not completed across every assigned area.',
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _MasterStat(value: '$clientCount', label: 'Clients'),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: _MasterStat(value: '$completeCount', label: 'Complete'),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: _MasterStat(value: '$unresolvedCount', label: 'Still open'),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              Expanded(
                child: _MasterStat(value: '$attentionCount', label: 'Attention'),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: _MasterStat(value: '$gcashCount', label: 'GCash notes'),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: _MasterStat(
                  value: _moneyCompact(route.expectedTotal),
                  label: 'Route expected',
                  smallValue: true,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MasterStat extends StatelessWidget {
  const _MasterStat({
    required this.value,
    required this.label,
    this.smallValue = false,
  });

  final String value;
  final String label;
  final bool smallValue;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 9),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        children: [
          Text(
            value,
            textAlign: TextAlign.center,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: SpinaTheme.ink,
              fontWeight: FontWeight.w900,
              fontSize: smallValue ? 13 : 19,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.labelSmall,
          ),
        ],
      ),
    );
  }
}

class _AreaReviewCard extends StatelessWidget {
  const _AreaReviewCard({required this.area, required this.routeDate});

  final CollectorRouteAreaGroup area;
  final DateTime? routeDate;

  @override
  Widget build(BuildContext context) {
    final reviews = area.clients
        .map((client) => _ClientReview.from(client, routeDate))
        .toList(growable: false);
    final complete = reviews.where((review) => !review.needsAction).length;
    final remaining = reviews.length - complete;
    final progress = reviews.isEmpty ? 0.0 : complete / reviews.length;
    final expected = area.expectedTotal;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    'AREA: ${area.area.toUpperCase()}',
                    style: const TextStyle(fontWeight: FontWeight.w900),
                  ),
                ),
                Text('$complete/${reviews.length} done'),
              ],
            ),
            const SizedBox(height: 5),
            Row(
              children: [
                Expanded(child: LinearProgressIndicator(value: progress)),
                const SizedBox(width: 10),
                Text('$remaining left'),
              ],
            ),
            const SizedBox(height: 5),
            Text(
              '${area.loanCount} loans • expected ${_moneyCompact(expected)}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}

class _OutstandingClientCard extends StatelessWidget {
  const _OutstandingClientCard({required this.review});

  final _ClientReview review;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: Key('master-review-client-${review.client.clientId}'),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 38,
                  height: 38,
                  decoration: BoxDecoration(
                    color: review.needsAttention
                        ? const Color(0xFFFFE9E5)
                        : SpinaTheme.brandPinkSoft,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(
                    review.needsAttention
                        ? Icons.priority_high_rounded
                        : Icons.person_outline_rounded,
                    color: review.needsAttention
                        ? Theme.of(context).colorScheme.error
                        : SpinaTheme.brandPinkDark,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        review.client.clientName,
                        style: const TextStyle(fontWeight: FontWeight.w900),
                      ),
                      Text(
                        review.client.area,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
                Text(
                  review.amountLabel,
                  style: const TextStyle(
                    color: SpinaTheme.brandPinkDark,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 5,
              runSpacing: 5,
              children: review.chips
                  .map((chip) => _ReviewChip(label: chip.label, tone: chip.tone))
                  .toList(growable: false),
            ),
            if (review.detailLines.isNotEmpty) ...[
              const SizedBox(height: 8),
              for (final line in review.detailLines) ...[
                Text(line, style: Theme.of(context).textTheme.bodySmall),
                const SizedBox(height: 2),
              ],
            ],
          ],
        ),
      ),
    );
  }
}

class _ReviewedExceptionCard extends StatelessWidget {
  const _ReviewedExceptionCard({required this.review});

  final _ClientReview review;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(11),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(
              Icons.fact_check_outlined,
              color: SpinaTheme.brandPinkDark,
              size: 20,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    review.client.clientName,
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                  Text(
                    review.exceptionLabel,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _AllDoneCard extends StatelessWidget {
  const _AllDoneCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      key: const Key('collector-master-review-all-done'),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFEAF7F0),
        borderRadius: BorderRadius.circular(18),
      ),
      child: const Row(
        children: [
          Icon(Icons.check_circle_rounded, color: SpinaTheme.success),
          SizedBox(width: 10),
          Expanded(
            child: Text(
              'Every client on the current route has been completed or explicitly covered for today.',
              style: TextStyle(fontWeight: FontWeight.w700),
            ),
          ),
        ],
      ),
    );
  }
}

class _ReadOnlyNotice extends StatelessWidget {
  const _ReadOnlyNotice({required this.message, required this.offline});

  final String message;
  final bool offline;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(11),
      decoration: BoxDecoration(
        color: offline
            ? Theme.of(context).colorScheme.tertiaryContainer
            : Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(offline ? Icons.cloud_off_outlined : Icons.info_outline_rounded),
          const SizedBox(width: 8),
          Expanded(child: Text(message)),
        ],
      ),
    );
  }
}

class _StateChip extends StatelessWidget {
  const _StateChip({required this.label, required this.warning});

  final String label;
  final bool warning;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: warning ? const Color(0xFFFFF0DE) : const Color(0xFFE8F6EF),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: warning ? const Color(0xFF97510D) : SpinaTheme.success,
          fontSize: 10,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

class _ReviewChip extends StatelessWidget {
  const _ReviewChip({required this.label, required this.tone});

  final String label;
  final _ReviewTone tone;

  @override
  Widget build(BuildContext context) {
    final background = switch (tone) {
      _ReviewTone.good => const Color(0xFFE8F6EF),
      _ReviewTone.warning => const Color(0xFFFFF0DE),
      _ReviewTone.danger => const Color(0xFFFFE7E4),
      _ReviewTone.info => const Color(0xFFE9F1FF),
    };
    final foreground = switch (tone) {
      _ReviewTone.good => SpinaTheme.success,
      _ReviewTone.warning => const Color(0xFF97510D),
      _ReviewTone.danger => Theme.of(context).colorScheme.error,
      _ReviewTone.info => const Color(0xFF315C9B),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 4),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: foreground,
          fontSize: 10,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

class _ReviewLoadError extends StatelessWidget {
  const _ReviewLoadError({required this.message, required this.onRetry});

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
            const Icon(Icons.fact_check_outlined, size: 48),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Try again'),
            ),
          ],
        ),
      ),
    );
  }
}

class _ClientReview {
  _ClientReview({
    required this.client,
    required this.needsAction,
    required this.needsAttention,
    required this.hasExplicitGcashNote,
    required this.hasReviewedException,
    required this.amountLabel,
    required this.chips,
    required this.detailLines,
    required this.exceptionLabel,
  });

  final CollectorRouteClientGroup client;
  final bool needsAction;
  final bool needsAttention;
  final bool hasExplicitGcashNote;
  final bool hasReviewedException;
  final String amountLabel;
  final List<_ChipData> chips;
  final List<String> detailLines;
  final String exceptionLabel;

  factory _ClientReview.from(
    CollectorRouteClientGroup client,
    DateTime? routeDate,
  ) {
    final unresolved = client.loans.where(
      (loan) => !_isResolvedToday(loan, routeDate),
    ).toList(growable: false);
    final missed = client.loans.fold<int>(
      0,
      (value, loan) => loan.passCount > value ? loan.passCount : value,
    );
    final maxDpd = client.loans
        .map((loan) => loan.contractDaysPastDue ?? 0)
        .fold<int>(0, (value, dpd) => dpd > value ? dpd : value);
    final todayUnpaid = client.loans.fold<double>(
      0,
      (total, loan) => total + loan.contractTodayUnpaidAmount,
    );
    final nextUnpaid = client.loans.fold<double>(
      0,
      (total, loan) => total + loan.contractNextUnpaidAmount,
    );
    final hasPassToday = client.loans.any(
      (loan) => loan.todayEntryType.trim().toLowerCase() == 'pass',
    );
    final hasAdvance = client.loans.any(
      (loan) => _isAdvanceCovered(loan, routeDate),
    );
    final hasPartial = client.loans.any((loan) {
      if (!loan.processedToday || loan.todayAmount <= 0) {
        return false;
      }
      final expected = loan.contractTodayScheduledAmount > 0
          ? loan.contractTodayScheduledAmount
          : loan.dailyAmount;
      return loan.todayAmount + 0.005 < expected;
    });
    final explicitGcash = client.loans.any(_containsExplicitGcashNote);
    final needsAction = unresolved.isNotEmpty || hasPartial;
    final attention = missed > 0 || maxDpd > 0 || hasPartial || hasPassToday;
    final reviewedException = !needsAction && (hasPassToday || hasAdvance);

    final chips = <_ChipData>[];
    if (unresolved.isNotEmpty) {
      chips.add(const _ChipData('NOT COLLECTED', _ReviewTone.warning));
    }
    if (missed > 0) {
      chips.add(_ChipData('MISSED $missed', _ReviewTone.danger));
    }
    if (maxDpd > 0) {
      chips.add(_ChipData('DPD $maxDpd', _ReviewTone.danger));
    }
    if (hasPartial) {
      chips.add(const _ChipData('LACKING / PARTIAL', _ReviewTone.danger));
    }
    if (hasPassToday) {
      chips.add(const _ChipData('PASS', _ReviewTone.warning));
    }
    if (hasAdvance) {
      chips.add(const _ChipData('ADV / COVERED', _ReviewTone.good));
    }
    if (explicitGcash) {
      chips.add(const _ChipData('GCASH NOTE', _ReviewTone.info));
    }
    if (chips.isEmpty) {
      chips.add(const _ChipData('REVIEW', _ReviewTone.info));
    }

    final details = <String>[];
    for (final loan in client.loans) {
      final loanLabel = _shortLoanName(loan.loanType);
      if (!_isResolvedToday(loan, routeDate)) {
        details.add(
          '$loanLabel: ${loan.status} • daily ${_moneyCompact(loan.dailyAmount)}',
        );
      }
      if (loan.contractTodayUnpaidAmount > 0) {
        details.add(
          '$loanLabel still unpaid today: ${_moneyCompact(loan.contractTodayUnpaidAmount)}',
        );
      }
      if ((loan.contractDaysPastDue ?? 0) > 0) {
        details.add(
          '$loanLabel contractual days past due: ${loan.contractDaysPastDue}',
        );
      }
      if (loan.contractNextUnpaidDate != null && loan.contractNextUnpaidAmount > 0) {
        details.add(
          '$loanLabel next unpaid: ${_date(loan.contractNextUnpaidDate!)} • ${_moneyCompact(loan.contractNextUnpaidAmount)}',
        );
      }
      if (loan.note.trim().isNotEmpty) {
        details.add('$loanLabel note: ${loan.note.trim()}');
      }
      if (loan.todayNote.trim().isNotEmpty && loan.todayNote.trim() != loan.note.trim()) {
        details.add('$loanLabel today note: ${loan.todayNote.trim()}');
      }
    }

    final dueForAction = todayUnpaid > 0
        ? todayUnpaid
        : unresolved.fold<double>(
            0,
            (total, loan) => total + loan.dailyAmount,
          );
    final amount = dueForAction > 0
        ? dueForAction
        : nextUnpaid > 0
            ? nextUnpaid
            : client.expectedTotal;

    String exceptionLabel = '';
    if (hasPassToday && hasAdvance) {
      exceptionLabel = 'PASS/ADV exception recorded and no unresolved loan remains.';
    } else if (hasPassToday) {
      exceptionLabel = 'PASS / unable-to-pay entry is recorded for today.';
    } else if (hasAdvance) {
      exceptionLabel = 'Today is covered by ADV / advance coverage.';
    }

    return _ClientReview(
      client: client,
      needsAction: needsAction,
      needsAttention: attention,
      hasExplicitGcashNote: explicitGcash,
      hasReviewedException: reviewedException,
      amountLabel: _moneyCompact(amount),
      chips: chips,
      detailLines: details,
      exceptionLabel: exceptionLabel,
    );
  }
}

class _ChipData {
  const _ChipData(this.label, this.tone);

  final String label;
  final _ReviewTone tone;
}

enum _ReviewTone { good, warning, danger, info }

bool _isResolvedToday(CollectorRouteEntry loan, DateTime? routeDate) {
  if (loan.processedToday) {
    return true;
  }
  if (_isAdvanceCovered(loan, routeDate)) {
    return true;
  }
  final normalized = loan.status.trim().toLowerCase();
  return normalized == 'covered' || normalized == 'recorded today';
}

bool _isAdvanceCovered(CollectorRouteEntry loan, DateTime? routeDate) {
  if (loan.contractTodayAlreadyCovered) {
    return true;
  }
  if (loan.todayEntryType.trim().toLowerCase() == 'advance') {
    return true;
  }
  final until = loan.advanceUntil;
  if (until == null || routeDate == null) {
    return false;
  }
  final untilDate = DateTime(until.year, until.month, until.day);
  final target = DateTime(routeDate.year, routeDate.month, routeDate.day);
  return !untilDate.isBefore(target);
}

bool _containsExplicitGcashNote(CollectorRouteEntry loan) {
  return <String>[
    loan.note,
    loan.todayNote,
    loan.collectionMessage,
  ].any((value) => value.toLowerCase().contains('gcash'));
}

String _shortLoanName(String value) {
  final normalized = value.toLowerCase().replaceAll(' ', '');
  if (normalized.contains('7x7') || normalized.contains('7×7')) {
    return '7x7';
  }
  if (normalized.contains('regular')) {
    return 'Regular';
  }
  return value;
}

String _date(DateTime value) {
  final local = value.toLocal();
  return '${local.year.toString().padLeft(4, '0')}-'
      '${local.month.toString().padLeft(2, '0')}-'
      '${local.day.toString().padLeft(2, '0')}';
}

String _moneyCompact(double value) {
  final fixed = value.toStringAsFixed(2);
  final parts = fixed.split('.');
  final digits = parts.first;
  final buffer = StringBuffer();
  for (var index = 0; index < digits.length; index += 1) {
    if (index > 0 && (digits.length - index) % 3 == 0) {
      buffer.write(',');
    }
    buffer.write(digits[index]);
  }
  return '₱$buffer.${parts.last}';
}

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_grouping.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

typedef CollectorEntryReason = String? Function(CollectorRouteEntry entry);
typedef CollectorEntryAction = void Function(CollectorRouteEntry entry);
typedef CollectorClientAction = void Function(CollectorRouteClientGroup client);
typedef CollectorEntryDetailsBuilder = Widget Function(CollectorRouteEntry entry);

/// Production Collector area ledger using one client row with REG, 7x7 and TODAY.
///
/// Exactly one payable loan uses [onRecord]. When one Regular and one protected
/// 7x7 loan are both payable, TODAY uses [onRecordCombined]. The combined action
/// is one server-authoritative atomic operation; the phone never submits two
/// independent financial writes for the same tap.
class CollectorClientLedgerSection extends StatelessWidget {
  const CollectorClientLedgerSection({
    required this.group,
    required this.expandedClients,
    required this.directPayBlockedReasonFor,
    required this.payingLoanIds,
    required this.pendingDirectLoanIds,
    required this.onToggleClient,
    required this.onRecord,
    required this.onRecordCombined,
    required this.detailsBuilder,
    super.key,
  });

  final CollectorRouteAreaGroup group;
  final Set<String> expandedClients;
  final CollectorEntryReason directPayBlockedReasonFor;
  final Set<String> payingLoanIds;
  final Set<String> pendingDirectLoanIds;
  final void Function(String clientId) onToggleClient;
  final CollectorEntryAction onRecord;
  final CollectorClientAction onRecordCombined;
  final CollectorEntryDetailsBuilder detailsBuilder;

  @override
  Widget build(BuildContext context) {
    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: SpinaTheme.line),
      ),
      child: Column(
        children: [
          Container(
            color: SpinaTheme.brandPinkSoft,
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    'AREA: ${group.area.toUpperCase()}',
                    style: const TextStyle(
                      color: SpinaTheme.brandPinkDark,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
                Text('${group.clientCount} clients'),
              ],
            ),
          ),
          const _ClientColumns(),
          for (var index = 0; index < group.clients.length; index++) ...[
            if (index > 0) const Divider(height: 1),
            _ClientRow(
              sequence: index + 1,
              client: group.clients[index],
              expanded: expandedClients.contains(group.clients[index].clientId),
              directPayBlockedReasonFor: directPayBlockedReasonFor,
              payingLoanIds: payingLoanIds,
              pendingDirectLoanIds: pendingDirectLoanIds,
              onToggle: () => onToggleClient(group.clients[index].clientId),
              onRecord: onRecord,
              onRecordCombined: onRecordCombined,
              detailsBuilder: detailsBuilder,
            ),
          ],
        ],
      ),
    );
  }
}

class _ClientColumns extends StatelessWidget {
  const _ClientColumns();

  @override
  Widget build(BuildContext context) {
    final style = Theme.of(context).textTheme.labelSmall?.copyWith(
          fontWeight: FontWeight.w700,
        );
    return Container(
      color: const Color(0xFFFFFAFC),
      padding: const EdgeInsets.fromLTRB(36, 5, 6, 5),
      child: Row(
        children: [
          Expanded(child: Text('CLIENT / STATUS', style: style)),
          SizedBox(
            width: 52,
            child: Text('REG', style: style, textAlign: TextAlign.center),
          ),
          SizedBox(
            width: 44,
            child: Text('7x7', style: style, textAlign: TextAlign.center),
          ),
          SizedBox(
            width: 74,
            child: Text('TODAY', style: style, textAlign: TextAlign.center),
          ),
        ],
      ),
    );
  }
}

class _ClientRow extends StatelessWidget {
  const _ClientRow({
    required this.sequence,
    required this.client,
    required this.expanded,
    required this.directPayBlockedReasonFor,
    required this.payingLoanIds,
    required this.pendingDirectLoanIds,
    required this.onToggle,
    required this.onRecord,
    required this.onRecordCombined,
    required this.detailsBuilder,
  });

  final int sequence;
  final CollectorRouteClientGroup client;
  final bool expanded;
  final CollectorEntryReason directPayBlockedReasonFor;
  final Set<String> payingLoanIds;
  final Set<String> pendingDirectLoanIds;
  final VoidCallback onToggle;
  final CollectorEntryAction onRecord;
  final CollectorClientAction onRecordCombined;
  final CollectorEntryDetailsBuilder detailsBuilder;

  @override
  Widget build(BuildContext context) {
    final regularAmount = client.loans
        .where((entry) => !_isSevenBySeven(entry.loanType))
        .fold<double>(0, (total, entry) => total + _scheduledToday(entry));
    final sevenAmount = client.loans
        .where((entry) => _isSevenBySeven(entry.loanType))
        .fold<double>(0, (total, entry) => total + _scheduledToday(entry));
    final action = _ClientActionState.from(
      client,
      directPayBlockedReasonFor: directPayBlockedReasonFor,
      payingLoanIds: payingLoanIds,
      pendingDirectLoanIds: pendingDirectLoanIds,
    );
    final chips = _statusChips(client);

    return Column(
      children: [
        InkWell(
          key: Key('route-client-${client.clientId}'),
          onTap: onToggle,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(8, 9, 6, 8),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                SizedBox(
                  width: 28,
                  child: Text(
                    '$sequence.',
                    style: Theme.of(context).textTheme.labelLarge,
                  ),
                ),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              client.clientName,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: Theme.of(context)
                                  .textTheme
                                  .labelLarge
                                  ?.copyWith(fontWeight: FontWeight.w900),
                            ),
                          ),
                          Icon(
                            expanded ? Icons.expand_less : Icons.expand_more,
                            size: 18,
                          ),
                        ],
                      ),
                      if (chips.isNotEmpty) ...[
                        const SizedBox(height: 3),
                        Wrap(
                          spacing: 4,
                          runSpacing: 3,
                          children: [for (final chip in chips) _StatusChip(chip)],
                        ),
                      ],
                    ],
                  ),
                ),
                _AmountCell(amount: regularAmount, width: 52),
                _AmountCell(amount: sevenAmount, width: 44),
                SizedBox(
                  width: 74,
                  child: _TodayAction(
                    client: client,
                    state: action,
                    onToggle: onToggle,
                    onRecord: onRecord,
                    onRecordCombined: onRecordCombined,
                  ),
                ),
              ],
            ),
          ),
        ),
        if (expanded)
          Container(
            width: double.infinity,
            margin: const EdgeInsets.fromLTRB(36, 0, 8, 9),
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: const Color(0xFFFFFAFC),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: SpinaTheme.line),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (action.requiresAtomicCombinedPosting) ...[
                  const _CombinedPayNotice(),
                  const SizedBox(height: 9),
                ],
                for (var index = 0; index < client.loans.length; index++) ...[
                  if (index > 0) const Divider(height: 18),
                  _ExpandedLoanHeader(entry: client.loans[index]),
                  const SizedBox(height: 5),
                  detailsBuilder(client.loans[index]),
                ],
              ],
            ),
          ),
      ],
    );
  }
}

class _TodayAction extends StatelessWidget {
  const _TodayAction({
    required this.client,
    required this.state,
    required this.onToggle,
    required this.onRecord,
    required this.onRecordCombined,
  });

  final CollectorRouteClientGroup client;
  final _ClientActionState state;
  final VoidCallback onToggle;
  final CollectorEntryAction onRecord;
  final CollectorClientAction onRecordCombined;

  @override
  Widget build(BuildContext context) {
    final entry = state.singleEntry ??
        (client.loans.length == 1 ? client.loans.single : null);
    final key = entry != null
        ? Key('record-collection-${entry.id}')
        : Key('record-client-${client.clientId}');

    if (state.paying) {
      return SizedBox(
        height: 42,
        child: FilledButton(
          key: key,
          onPressed: null,
          style: _buttonStyle(context),
          child: const SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
        ),
      );
    }

    if (state.requiresAtomicCombinedPosting) {
      return SizedBox(
        height: 42,
        child: FilledButton(
          key: key,
          onPressed: () => onRecordCombined(client),
          style: _buttonStyle(context),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(state.pendingRetry ? 'Retry' : 'Pay'),
              Text(
                _moneyShort(state.payableAmount),
                maxLines: 1,
                style: Theme.of(context).textTheme.labelSmall,
              ),
            ],
          ),
        ),
      );
    }

    final direct = state.singleEntry;
    final enabled = direct != null && state.blockedReason == null;
    final label = state.label;
    final amount = state.actionAmount;
    return SizedBox(
      height: 42,
      child: FilledButton(
        key: key,
        onPressed: enabled ? () => onRecord(direct) : null,
        style: _buttonStyle(context),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(label),
            if (amount > 0 && (label == 'Pay' || label == 'Retry'))
              Text(
                _moneyShort(amount),
                style: Theme.of(context).textTheme.labelSmall,
              ),
          ],
        ),
      ),
    );
  }

  ButtonStyle _buttonStyle(BuildContext context) => FilledButton.styleFrom(
        padding: const EdgeInsets.symmetric(horizontal: 3, vertical: 2),
        minimumSize: const Size(68, 40),
        textStyle: Theme.of(context).textTheme.labelMedium,
      );
}

class _AmountCell extends StatelessWidget {
  const _AmountCell({required this.amount, required this.width});

  final double amount;
  final double width;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      child: Text(
        amount <= 0 ? '—' : _moneyShort(amount),
        textAlign: TextAlign.center,
        style: Theme.of(context).textTheme.bodySmall,
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
      decoration: BoxDecoration(
        color: SpinaTheme.brandPinkSoft,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: SpinaTheme.brandPinkDark,
              fontSize: 9,
              fontWeight: FontWeight.w900,
            ),
      ),
    );
  }
}

class _ExpandedLoanHeader extends StatelessWidget {
  const _ExpandedLoanHeader({required this.entry});

  final CollectorRouteEntry entry;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(
            _loanLabel(entry.loanType),
            style: Theme.of(context).textTheme.labelLarge?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
        ),
        Text(
          'Balance ${_moneyShort(entry.balance)}',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                fontWeight: FontWeight.w700,
              ),
        ),
      ],
    );
  }
}

class _CombinedPayNotice extends StatelessWidget {
  const _CombinedPayNotice();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(9),
      decoration: BoxDecoration(
        color: SpinaTheme.brandPinkSoft,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        'Regular + 7x7 are both due. One-tap Pay sends one atomic server request: both official payments save together or neither saves.',
        style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: SpinaTheme.brandPinkDark,
              fontWeight: FontWeight.w700,
            ),
      ),
    );
  }
}

class _ClientActionState {
  const _ClientActionState({
    required this.payableEntries,
    required this.payableAmount,
    required this.paying,
    required this.pendingRetry,
    required this.label,
    required this.actionAmount,
    this.singleEntry,
    this.blockedReason,
  });

  final List<CollectorRouteEntry> payableEntries;
  final double payableAmount;
  final bool paying;
  final bool pendingRetry;
  final String label;
  final double actionAmount;
  final CollectorRouteEntry? singleEntry;
  final String? blockedReason;

  bool get requiresAtomicCombinedPosting => payableEntries.length > 1;

  factory _ClientActionState.from(
    CollectorRouteClientGroup client, {
    required CollectorEntryReason directPayBlockedReasonFor,
    required Set<String> payingLoanIds,
    required Set<String> pendingDirectLoanIds,
  }) {
    final payable = <CollectorRouteEntry>[];
    for (final entry in client.loans) {
      if (directPayBlockedReasonFor(entry) == null) {
        payable.add(entry);
      }
    }
    final payableAmount = payable.fold<double>(
      0,
      (total, entry) => total + _unpaidToday(entry),
    );
    final paying = client.loans.any(
      (entry) => payingLoanIds.contains(entry.loanId),
    );
    final pendingRetry = client.loans.any(
      (entry) => pendingDirectLoanIds.contains(entry.loanId),
    );

    if (payable.length > 1) {
      return _ClientActionState(
        payableEntries: payable,
        payableAmount: payableAmount,
        paying: paying,
        pendingRetry: pendingRetry,
        label: pendingRetry ? 'Retry' : 'Pay',
        actionAmount: payableAmount,
      );
    }

    if (payable.length == 1) {
      final entry = payable.single;
      return _ClientActionState(
        payableEntries: payable,
        payableAmount: payableAmount,
        paying: paying,
        pendingRetry: pendingRetry,
        label: pendingRetry ? 'Retry' : 'Pay',
        actionAmount: _unpaidToday(entry),
        singleEntry: entry,
      );
    }

    final preferred = _preferredStateEntry(client.loans);
    final blocked = preferred == null ? null : directPayBlockedReasonFor(preferred);
    final label = preferred == null ? 'Done' : _blockedLabel(preferred, blocked);
    return _ClientActionState(
      payableEntries: const <CollectorRouteEntry>[],
      payableAmount: 0,
      paying: paying,
      pendingRetry: pendingRetry,
      label: label,
      actionAmount: 0,
      singleEntry: preferred,
      blockedReason: blocked,
    );
  }
}

CollectorRouteEntry? _preferredStateEntry(List<CollectorRouteEntry> loans) {
  if (loans.isEmpty) {
    return null;
  }
  for (final entry in loans) {
    if (entry.todayIsLocked) {
      return entry;
    }
  }
  for (final entry in loans) {
    if (_isSevenBySeven(entry.loanType) && !entry.sevenBySevenMobileEnabled) {
      return entry;
    }
  }
  for (final entry in loans) {
    if (entry.processedToday) {
      return entry;
    }
  }
  return loans.first;
}

String _blockedLabel(CollectorRouteEntry entry, String? blockedReason) {
  if (_isSevenBySeven(entry.loanType) && !entry.sevenBySevenMobileEnabled) {
    return 'Desk';
  }
  if (entry.todayIsLocked) {
    return 'Locked';
  }
  if (entry.processedToday) {
    if (entry.contractCollectionReady && entry.contractTodayUnpaidAmount > 0) {
      return 'Lacking';
    }
    return 'Paid';
  }
  if (blockedReason != null && blockedReason.toLowerCase().contains('offline')) {
    return 'Offline';
  }
  return 'Locked';
}

List<String> _statusChips(CollectorRouteClientGroup client) {
  final chips = <String>[];
  final loans = client.loans;
  final hasLacking = loans.any(
    (entry) => entry.contractCollectionReady &&
        entry.contractTodayScheduledAmount > 0 &&
        entry.contractTodayUnpaidAmount > 0 &&
        entry.processedToday,
  );
  final hasPass = loans.any(
    (entry) => entry.todayEntryType.trim().toLowerCase() == 'pass',
  );
  final hasAdvance = loans.any(
    (entry) => entry.todayEntryType.trim().toLowerCase() == 'advance' ||
        entry.advanceUntil != null,
  );
  final allComplete = loans.isNotEmpty && loans.every(_todaySatisfied);
  final anyLocked = loans.any((entry) => entry.todayIsLocked);
  final desktop7x7 = loans.any(
    (entry) => _isSevenBySeven(entry.loanType) && !entry.sevenBySevenMobileEnabled,
  );
  final missed = loans.fold<int>(
    0,
    (highest, entry) => entry.passCount > highest ? entry.passCount : highest,
  );
  final textBlob = loans
      .expand((entry) => <String>[entry.status, entry.note, entry.todayNote])
      .join(' ')
      .toLowerCase();

  if (hasLacking) {
    chips.add('LACKING');
  } else if (allComplete) {
    chips.add(anyLocked ? 'REMITTED' : 'COLLECTED');
  } else if (hasPass) {
    chips.add('UNABLE');
  } else if (loans.any((entry) => entry.processedToday)) {
    chips.add('PARTIAL');
  } else {
    chips.add('NOT COLLECTED');
  }

  if (missed > 0) {
    if (!allComplete && !hasPass) {
      chips.add('CATCH-UP');
    }
    chips.add('MISSED $missed');
  }
  if (hasAdvance) {
    chips.add('ADV');
  }
  if (textBlob.contains('gcash')) {
    chips.add('GCASH');
  }
  if (desktop7x7) {
    chips.add('7x7 DESK');
  }
  return chips;
}

bool _todaySatisfied(CollectorRouteEntry entry) {
  if (entry.contractCollectionReady && entry.contractTodayScheduledAmount > 0) {
    return entry.contractTodayUnpaidAmount <= 0;
  }
  return entry.processedToday;
}

double _scheduledToday(CollectorRouteEntry entry) {
  if (entry.contractCollectionReady && entry.contractTodayScheduledAmount > 0) {
    return entry.contractTodayScheduledAmount;
  }
  return entry.dailyAmount;
}

double _unpaidToday(CollectorRouteEntry entry) {
  if (entry.contractCollectionReady && entry.contractTodayScheduledAmount > 0) {
    return entry.contractTodayUnpaidAmount > 0
        ? entry.contractTodayUnpaidAmount
        : 0;
  }
  return entry.processedToday ? 0 : entry.dailyAmount;
}

bool _isSevenBySeven(String value) {
  final normalized = value.toLowerCase().replaceAll(' ', '');
  return normalized.contains('7x7') || normalized.contains('7×7');
}

String _loanLabel(String value) => _isSevenBySeven(value) ? '7x7' : value;

String _moneyShort(double value) {
  if ((value - value.roundToDouble()).abs() < 0.005) {
    return '₱${_groupDigits(value.round().toString())}';
  }
  final fixed = value.toStringAsFixed(2).split('.');
  return '₱${_groupDigits(fixed.first)}.${fixed.last}';
}

String _groupDigits(String digits) {
  final buffer = StringBuffer();
  for (var index = 0; index < digits.length; index += 1) {
    if (index > 0 && (digits.length - index) % 3 == 0) {
      buffer.write(',');
    }
    buffer.write(digits[index]);
  }
  return buffer.toString();
}

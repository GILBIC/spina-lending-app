import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_grouping.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/collection_correction_repository.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/combined_payment_submission.dart';
import 'package:gilbic_mobile/src/core/payments/combined_payment_submission_repository.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collection_correction_page.dart';
import 'package:gilbic_mobile/src/features/collector/collection_entry_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_client_ledger.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_header_cards.dart';

class CollectorRoutePage extends StatefulWidget {
  const CollectorRoutePage({
    required this.session,
    required this.loader,
    this.paymentRepository,
    this.combinedPaymentRepository,
    this.correctionRepository,
    this.deviceIdentityProvider,
    this.deviceSequence,
    super.key,
  });

  final UserSession session;
  final CollectorRouteLoader loader;
  final PaymentSubmissionRepository? paymentRepository;
  final CombinedPaymentSubmissionRepository? combinedPaymentRepository;
  final CollectionCorrectionRepository? correctionRepository;
  final DeviceIdentityProvider? deviceIdentityProvider;
  final CollectionDeviceSequence? deviceSequence;

  @override
  State<CollectorRoutePage> createState() => _CollectorRoutePageState();
}

class _CollectorRoutePageState extends State<CollectorRoutePage> {
  late final PaymentSubmissionRepository _paymentRepository;
  late final CombinedPaymentSubmissionRepository _combinedPaymentRepository;
  late final CollectionCorrectionRepository _correctionRepository;
  late final DeviceIdentityProvider _deviceIdentityProvider;
  late final CollectionDeviceSequence _deviceSequence;

  final Set<String> _expandedClients = <String>{};
  final Set<String> _payingLoanIds = <String>{};
  final Map<String, PaymentSubmissionDraft> _pendingDirectDrafts =
      <String, PaymentSubmissionDraft>{};
  final Map<String, CombinedPaymentSubmissionDraft> _pendingCombinedDrafts =
      <String, CombinedPaymentSubmissionDraft>{};
  CollectorRouteLoadResult? _result;
  Object? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _paymentRepository =
        widget.paymentRepository ?? SpinaPaymentSubmissionRepository();
    _combinedPaymentRepository = widget.combinedPaymentRepository ??
        SpinaCombinedPaymentSubmissionRepository();
    _correctionRepository =
        widget.correctionRepository ?? SpinaCollectionCorrectionRepository();
    _deviceIdentityProvider =
        widget.deviceIdentityProvider ?? DeviceIdentityProvider();
    _deviceSequence =
        widget.deviceSequence ?? SecureCollectionDeviceSequence();
    _loadRoute();
  }

  Future<void> _loadRoute() async {
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

  String? _commonWriteBlockedReason(
    CollectorRouteLoadResult loaded,
    CollectorRouteEntry entry,
  ) {
    if (loaded.isFromCache) {
      return 'Offline route copies are read-only. Reconnect and refresh before recording a collection.';
    }
    if (!widget.session.permissions.contains('collection.create')) {
      return 'This account does not have permission to record collections.';
    }
    if (_isSevenBySevenLoan(entry.loanType) &&
        !entry.sevenBySevenMobileEnabled) {
      return '7x7 mobile collection is disabled. Use SPINA desktop until the protected server allocator explicitly enables this route entry.';
    }
    if (!entry.canCollectMobile || !entry.canEnterPayment) {
      return entry.collectionMessage.isNotEmpty
          ? entry.collectionMessage
          : 'Use SPINA desktop for this loan.';
    }
    if (entry.loanId.trim().isEmpty || entry.routeRevision == null) {
      return 'Refresh the route before recording this collection.';
    }
    return null;
  }

  String? _directPayBlockedReason(
    CollectorRouteLoadResult loaded,
    CollectorRouteEntry entry,
  ) {
    final common = _commonWriteBlockedReason(loaded, entry);
    if (common != null) {
      return common;
    }

    if (entry.contractCollectionReady) {
      if (entry.contractTodayScheduledAmount <= 0) {
        return 'No scheduled payment is due today. Expand this loan for covered dates or other payment details.';
      }
      if (entry.contractTodayUnpaidAmount <= 0) {
        return "Today's scheduled payment is already fully paid.";
      }
      return null;
    }

    if (entry.processedToday) {
      return "Today's collection has already been recorded.";
    }
    return null;
  }

  String? _detailsBlockedReason(
    CollectorRouteLoadResult loaded,
    CollectorRouteEntry entry,
  ) {
    final common = _commonWriteBlockedReason(loaded, entry);
    if (common != null) {
      return common;
    }
    final canAddPartialContractReceipt = entry.contractCollectionReady &&
        entry.contractTodayUnpaidAmount > 0;
    if (entry.processedToday && !canAddPartialContractReceipt) {
      return "Today's scheduled payment is already recorded. Use Edit for a correction before remittance.";
    }
    return null;
  }

  double _normalDueAmount(CollectorRouteEntry entry) {
    if (entry.contractCollectionReady &&
        entry.contractTodayUnpaidAmount > 0) {
      return entry.contractTodayUnpaidAmount;
    }
    return entry.dailyAmount;
  }

  Future<PaymentSubmissionDraft> _buildDirectPaymentDraft(
    CollectorRouteLoadResult loaded,
    CollectorRouteEntry entry,
  ) async {
    final identity = await _deviceIdentityProvider.load();
    final sequence = await _deviceSequence.next();
    final collectionDate = _dateOnly(loaded.route.routeDate ?? DateTime.now());
    return PaymentSubmissionDraft(
      idempotencyKey: SecureIdempotencyKeyGenerator().generate(),
      routeEntryId: entry.id,
      clientId: entry.clientId,
      loanId: entry.loanId,
      collectionDate: collectionDate,
      entryType: CollectionEntryType.payment,
      amount: _normalDueAmount(entry),
      coveredDates: <DateTime>[collectionDate],
      recordedAt: DateTime.now().toUtc(),
      deviceId: identity.installationId,
      deviceSequence: sequence,
      routeRevision: entry.routeRevision,
    );
  }

  Future<CombinedPaymentSubmissionDraft> _buildCombinedPaymentDraft(
    CollectorRouteLoadResult loaded,
    CollectorRouteClientGroup client,
  ) async {
    final payable = client.loans
        .where((entry) => _directPayBlockedReason(loaded, entry) == null)
        .toList(growable: false);
    if (payable.length != 2 ||
        payable.where((entry) => _isSevenBySevenLoan(entry.loanType)).length != 1) {
      throw const SpinaApiException(
        'Combined Pay requires exactly one payable Regular loan and one payable 7x7 loan.',
        code: 'combined_regular_7x7_required',
      );
    }
    final ordered = <CollectorRouteEntry>[
      ...payable.where((entry) => !_isSevenBySevenLoan(entry.loanType)),
      ...payable.where((entry) => _isSevenBySevenLoan(entry.loanType)),
    ];
    final identity = await _deviceIdentityProvider.load();
    final firstSequence = await _deviceSequence.next();
    final secondSequence = await _deviceSequence.next();
    if (secondSequence != firstSequence + 1) {
      throw const SpinaApiException(
        'SPINA could not reserve two consecutive device entries for combined Pay. Refresh and try again.',
        code: 'combined_device_sequence_unavailable',
      );
    }
    final collectionDate = _dateOnly(loaded.route.routeDate ?? DateTime.now());
    return CombinedPaymentSubmissionDraft(
      idempotencyKey: SecureIdempotencyKeyGenerator().generate(),
      clientId: client.clientId,
      collectionDate: collectionDate,
      recordedAt: DateTime.now().toUtc(),
      deviceId: identity.installationId,
      deviceSequence: firstSequence,
      legs: ordered
          .map(
            (entry) => CombinedPaymentLegDraft(
              routeEntryId: entry.id,
              loanId: entry.loanId,
              routeRevision: entry.routeRevision!,
              amount: _normalDueAmount(entry),
            ),
          )
          .toList(growable: false),
    );
  }

  Future<void> _payNow(
    CollectorRouteLoadResult loaded,
    CollectorRouteEntry entry,
  ) async {
    final blockedReason = _directPayBlockedReason(loaded, entry);
    if (blockedReason != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(blockedReason)),
      );
      return;
    }
    if (_payingLoanIds.contains(entry.loanId)) {
      return;
    }

    setState(() => _payingLoanIds.add(entry.loanId));
    try {
      final draft = _pendingDirectDrafts[entry.loanId] ??
          await _buildDirectPaymentDraft(loaded, entry);
      _pendingDirectDrafts[entry.loanId] = draft;
      final result = await _paymentRepository.submit(widget.session, draft);
      if (!mounted) {
        return;
      }

      if (result.isFinalSuccess) {
        _pendingDirectDrafts.remove(entry.loanId);
        final receipt = result.receiptNumber?.trim();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              receipt == null || receipt.isEmpty
                  ? 'Payment saved.'
                  : 'Payment saved • Receipt $receipt',
            ),
          ),
        );
        await _loadRoute();
        return;
      }

      _pendingDirectDrafts.remove(entry.loanId);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(result.message)),
      );
      await _loadRoute();
    } on SpinaApiException catch (error) {
      if (!mounted) {
        return;
      }
      final status = error.statusCode;
      final uncertain = status == null || status == 429 || status >= 500;
      if (!uncertain) {
        _pendingDirectDrafts.remove(entry.loanId);
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            uncertain
                ? 'Payment result is not confirmed. Tap Retry to check the same payment.'
                : error.message,
          ),
        ),
      );
    } on Object {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Payment result is not confirmed. Tap Retry to check the same payment.',
          ),
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _payingLoanIds.remove(entry.loanId));
      }
    }
  }

  Future<void> _payCombined(
    CollectorRouteLoadResult loaded,
    CollectorRouteClientGroup client,
  ) async {
    final payable = client.loans
        .where((entry) => _directPayBlockedReason(loaded, entry) == null)
        .toList(growable: false);
    if (payable.length != 2 ||
        payable.where((entry) => _isSevenBySevenLoan(entry.loanType)).length != 1) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Combined Pay requires exactly one payable Regular loan and one payable 7x7 loan.',
          ),
        ),
      );
      return;
    }
    if (payable.any((entry) => _payingLoanIds.contains(entry.loanId))) {
      return;
    }

    setState(() {
      _payingLoanIds.addAll(payable.map((entry) => entry.loanId));
    });
    try {
      final draft = _pendingCombinedDrafts[client.clientId] ??
          await _buildCombinedPaymentDraft(loaded, client);
      _pendingCombinedDrafts[client.clientId] = draft;
      final result =
          await _combinedPaymentRepository.submit(widget.session, draft);
      if (!mounted) {
        return;
      }
      if (result.isFinalSuccess) {
        _pendingCombinedDrafts.remove(client.clientId);
        final receipts = result.receiptNumbers.join(' + ');
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              receipts.isEmpty
                  ? 'Regular + 7x7 payments saved atomically.'
                  : 'Regular + 7x7 saved • Receipts $receipts',
            ),
          ),
        );
        await _loadRoute();
        return;
      }
      _pendingCombinedDrafts.remove(client.clientId);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(result.message)),
      );
      await _loadRoute();
    } on SpinaApiException catch (error) {
      if (!mounted) {
        return;
      }
      final status = error.statusCode;
      final uncertain = status == null || status == 429 || status >= 500;
      if (!uncertain) {
        _pendingCombinedDrafts.remove(client.clientId);
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            uncertain
                ? 'Combined payment result is not confirmed. Tap Retry to check the same Regular + 7x7 payment.'
                : error.message,
          ),
        ),
      );
    } on Object {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Combined payment result is not confirmed. Tap Retry to check the same Regular + 7x7 payment.',
          ),
        ),
      );
    } finally {
      if (mounted) {
        setState(() {
          _payingLoanIds.removeAll(payable.map((entry) => entry.loanId));
        });
      }
    }
  }

  Set<String> _pendingPaymentLoanIds() {
    final result = _pendingDirectDrafts.keys.toSet();
    for (final draft in _pendingCombinedDrafts.values) {
      result.addAll(draft.legs.map((leg) => leg.loanId));
    }
    return result;
  }

  Future<void> _openCollectionDetails(
    CollectorRouteLoadResult loaded,
    CollectorRouteEntry entry,
  ) async {
    final blockedReason = _detailsBlockedReason(loaded, entry);
    if (blockedReason != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(blockedReason)),
      );
      return;
    }

    final saved = await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (context) => CollectionEntryPage(
          session: widget.session,
          entry: entry,
          repository: _paymentRepository,
          deviceIdentityProvider: _deviceIdentityProvider,
          deviceSequence: _deviceSequence,
          collectionDate: loaded.route.routeDate,
        ),
      ),
    );
    if (saved == true && mounted) {
      await _loadRoute();
    }
  }

  Future<void> _openCorrection(
    CollectorRouteLoadResult loaded,
    CollectorRouteEntry entry,
  ) async {
    final blockedReason = _correctionBlockedReason(loaded, entry);
    if (blockedReason != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(blockedReason)),
      );
      return;
    }

    final saved = await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (context) => CollectionCorrectionPage(
          session: widget.session,
          entry: entry,
          collectionDate: loaded.route.routeDate ?? DateTime.now(),
          repository: _correctionRepository,
          deviceIdentityProvider: _deviceIdentityProvider,
        ),
      ),
    );
    if (saved == true && mounted) {
      await _loadRoute();
    }
  }

  String? _correctionBlockedReason(
    CollectorRouteLoadResult loaded,
    CollectorRouteEntry entry,
  ) {
    if (loaded.isFromCache) {
      return 'Offline route copies are read-only. Reconnect and refresh before editing.';
    }
    if (!widget.session.permissions
        .contains('collection.correct.own_unremitted')) {
      return 'This account does not have collection correction permission.';
    }
    if (!entry.processedToday || entry.todayTransactionId == null) {
      return 'There is no collection entry to edit.';
    }
    if (entry.todayIsLocked) {
      return 'This collection is already remitted and permanently locked.';
    }
    if (!entry.canEditToday) {
      return 'This unremitted receipt is not available for correction from this route yet.';
    }
    return null;
  }

  void _toggleClient(String clientId) {
    setState(() {
      if (!_expandedClients.add(clientId)) {
        _expandedClients.remove(clientId);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Daily Collection'),
        actions: [
          IconButton(
            tooltip: 'Refresh route',
            onPressed: _loading ? null : _loadRoute,
            icon: const Icon(Icons.refresh),
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

    final error = _error;
    if (error != null && result == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off, size: 48),
              const SizedBox(height: 12),
              Text(
                error.toString(),
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyLarge,
              ),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: _loadRoute,
                icon: const Icon(Icons.refresh),
                label: const Text('Try again'),
              ),
            ],
          ),
        ),
      );
    }

    final loaded = result!;
    final route = loaded.route;
    final areaGroups = groupCollectorRoute(route);
    final clientCount = areaGroups.fold<int>(
      0,
      (total, group) => total + group.clientCount,
    );

    return RefreshIndicator(
      onRefresh: _loadRoute,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(10, 8, 10, 16),
        children: [
          CollectorRouteHeaderCard(
            result: loaded,
            route: route,
            clientCount: clientCount,
          ),
          const SizedBox(height: 8),
          CollectorAreaArrangementCard(
            areas: areaGroups.map((group) => group.area).toList(),
          ),
          if (loaded.warning != null) ...[
            const SizedBox(height: 8),
            MaterialBanner(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              content: Text(loaded.warning!),
              leading: Icon(
                loaded.isFromCache ? Icons.cloud_off : Icons.storage,
              ),
              actions: [
                TextButton(onPressed: _loadRoute, child: const Text('Retry')),
              ],
            ),
          ],
          if (error != null) ...[
            const SizedBox(height: 8),
            MaterialBanner(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              content: Text('The last refresh failed: $error'),
              actions: [
                TextButton(onPressed: _loadRoute, child: const Text('Retry')),
              ],
            ),
          ],
          const SizedBox(height: 8),
          if (route.entries.isEmpty)
            const Padding(
              padding: EdgeInsets.all(24),
              child: Text(
                'No clients are assigned to this route.',
                textAlign: TextAlign.center,
              ),
            )
          else
            for (final group in areaGroups) ...[
              CollectorClientLedgerSection(
                group: group,
                expandedClients: _expandedClients,
                directPayBlockedReasonFor: (entry) =>
                    _directPayBlockedReason(loaded, entry),
                payingLoanIds: _payingLoanIds,
                pendingDirectLoanIds: _pendingPaymentLoanIds(),
                onToggleClient: _toggleClient,
                onRecord: (entry) => _payNow(loaded, entry),
                onRecordCombined: (client) => _payCombined(loaded, client),
                detailsBuilder: (entry) => _LoanDetails(
                  entry: entry,
                  blockedReason: _directPayBlockedReason(loaded, entry),
                  detailsBlockedReason: _detailsBlockedReason(loaded, entry),
                  correctionBlockedReason:
                      _correctionBlockedReason(loaded, entry),
                  onDetails: () => _openCollectionDetails(loaded, entry),
                  onEdit: () => _openCorrection(loaded, entry),
                ),
              ),
              const SizedBox(height: 8),
            ],
          const SizedBox(height: 4),
          Text(
            'One client stays on one Daily Collection row. TODAY keeps one-tap Pay. When Regular + 7x7 are both due, one tap is submitted as one atomic server operation: both official receipts save together or neither saves. Expand only for notes, receipts, covered dates/ADV, voluntary extra, correction or other exceptions. Offline routes remain view-only.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _LoanDetails extends StatelessWidget {
  const _LoanDetails({
    required this.entry,
    required this.blockedReason,
    required this.detailsBlockedReason,
    required this.correctionBlockedReason,
    required this.onDetails,
    required this.onEdit,
  });

  final CollectorRouteEntry entry;
  final String? blockedReason;
  final String? detailsBlockedReason;
  final String? correctionBlockedReason;
  final VoidCallback onDetails;
  final VoidCallback onEdit;

  @override
  Widget build(BuildContext context) {
    final lines = <String>[
      'Status: ${entry.status}',
      'Missed payments: ${entry.passCount}',
      if (entry.contractCollectionReady &&
          entry.contractTodayScheduledAmount > 0)
        'Scheduled today: ${_moneyCompact(entry.contractTodayScheduledAmount)}',
      if (entry.contractCollectionReady &&
          entry.contractTodayScheduledAmount > 0)
        'Still due today: ${_moneyCompact(entry.contractTodayUnpaidAmount)}',
      if (entry.lastPaymentDate != null)
        'Last payment: ${_date(entry.lastPaymentDate!)}',
      if (entry.todayReceipts.isEmpty &&
          entry.processedToday &&
          entry.todayAmount > 0)
        'Latest receipt: ${_moneyCompact(entry.todayAmount)}',
      if (entry.todayCoveredDates.isNotEmpty)
        'Exact covered dates: ${entry.todayCoveredDates.map(_date).join(', ')}',
      if (!entry.processedToday && entry.coveredDates.isNotEmpty)
        'Upcoming covered dates: ${entry.coveredDates.map(_date).join(', ')}',
      if (entry.processedToday) _todayResultLabel(entry.todayEntryType),
      if (entry.todayReceipts.isEmpty &&
          entry.processedToday &&
          entry.todayCollectorName.isNotEmpty)
        'Latest receipt recorded by: ${entry.todayCollectorName}',
      if (entry.todayReceipts.isEmpty &&
          entry.processedToday &&
          entry.todayIsLocked)
        'Latest receipt remittance status: Locked',
      if (entry.todayReceipts.isEmpty &&
          entry.processedToday &&
          entry.todayNote.isNotEmpty)
        'Latest receipt note: ${entry.todayNote}',
      if (!entry.processedToday && entry.note.isNotEmpty)
        'Reason / note: ${entry.note}',
      if (blockedReason != null && !entry.processedToday) blockedReason!,
      if (blockedReason == null && entry.collectionMessage.isNotEmpty)
        entry.collectionMessage,
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var index = 0; index < lines.length; index++) ...[
          if (index > 0) const SizedBox(height: 3),
          Text(lines[index], style: Theme.of(context).textTheme.bodySmall),
        ],
        if (entry.todayReceipts.isNotEmpty) ...[
          const SizedBox(height: 8),
          _TodayReceipts(receipts: entry.todayReceipts),
        ],
        const SizedBox(height: 8),
        if (detailsBlockedReason == null)
          OutlinedButton.icon(
            key: Key('collection-details-${entry.id}'),
            onPressed: onDetails,
            icon: const Icon(Icons.tune, size: 18),
            label: const Text('Payment details / other amount'),
          )
        else if (!entry.processedToday &&
            detailsBlockedReason != blockedReason)
          Text(
            detailsBlockedReason!,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        if (entry.processedToday) ...[
          const SizedBox(height: 8),
          if (correctionBlockedReason == null)
            OutlinedButton.icon(
              key: Key('edit-collection-${entry.todayTransactionId}'),
              onPressed: onEdit,
              icon: const Icon(Icons.edit_outlined, size: 18),
              label: const Text('Edit before remittance'),
            )
          else
            Text(
              correctionBlockedReason!,
              style: Theme.of(context).textTheme.bodySmall,
            ),
        ],
      ],
    );
  }
}

class _TodayReceipts extends StatelessWidget {
  const _TodayReceipts({required this.receipts});

  final List<CollectorRouteReceipt> receipts;

  @override
  Widget build(BuildContext context) {
    final total = receipts.fold<double>(
      0,
      (sum, receipt) => sum + receipt.amount,
    );
    return Column(
      key: const Key('today-receipts'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          "Today's receipts • ${receipts.length} • ${_moneyCompact(total)}",
          style: Theme.of(context).textTheme.labelMedium?.copyWith(
                fontWeight: FontWeight.w800,
              ),
        ),
        const SizedBox(height: 5),
        for (final receipt in receipts) ...[
          Container(
            key: Key('today-receipt-${receipt.transactionId}'),
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Receipt ${receipt.receiptNumber} • '
                  '${_moneyCompact(receipt.amount)} • '
                  '${receipt.collectorName}'
                  '${receipt.isLocked ? ' • Locked' : ''}',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                ),
                if (receipt.coveredDates.isNotEmpty)
                  Text(
                    'Covered: ${receipt.coveredDates.map(_date).join(', ')}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                if (receipt.note.isNotEmpty)
                  Text(
                    'Note: ${receipt.note}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

String _todayResultLabel(String value) {
  return switch (value.trim().toLowerCase()) {
    'pass' => 'Unable-to-pay reason recorded today.',
    'advance' => 'Covered-date payment recorded today.',
    _ => 'Payment receipt recorded today.',
  };
}

bool _isSevenBySevenLoan(String value) {
  final normalized = value.toLowerCase().replaceAll(' ', '');
  return normalized.contains('7x7') || normalized.contains('7×7');
}

DateTime _dateOnly(DateTime value) =>
    DateTime(value.year, value.month, value.day);

String _date(DateTime value) {
  final local = value.toLocal();
  return '${local.year.toString().padLeft(4, '0')}-'
      '${local.month.toString().padLeft(2, '0')}-'
      '${local.day.toString().padLeft(2, '0')}';
}

String _moneyCompact(double value) {
  final fixed = value.toStringAsFixed(2);
  final parts = fixed.split('.');
  return '₱${_groupDigits(parts.first)}.${parts.last}';
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

import 'package:gilbic_mobile/src/core/payments/request_money.dart';
import 'package:gilbic_mobile/src/core/management/general_journal.dart';
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_collection_location_repository.dart';
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
import 'package:gilbic_mobile/src/features/collector/collector_client_collection_location_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_client_ledger.dart';
import 'package:gilbic_mobile/src/features/collector/collector_client_schedule_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_client_tools_sheet.dart';
import 'package:gilbic_mobile/src/features/collector/collector_failure_guidance.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_header_cards.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_tree.dart';
import 'package:gilbic_mobile/src/features/shared/daily_workspace_widgets.dart';

class CollectorRoutePage extends StatefulWidget {
  const CollectorRoutePage({
    required this.session,
    required this.loader,
    this.onSignOut,
    this.paymentRepository,
    this.combinedPaymentRepository,
    this.correctionRepository,
    this.collectionLocationRepository,
    this.deviceIdentityProvider,
    this.deviceSequence,
    super.key,
  });

  final UserSession session;
  final CollectorRouteLoader loader;
  final Future<void> Function()? onSignOut;
  final PaymentSubmissionRepository? paymentRepository;
  final CombinedPaymentSubmissionRepository? combinedPaymentRepository;
  final CollectionCorrectionRepository? correctionRepository;
  final CollectorCollectionLocationRepository? collectionLocationRepository;
  final DeviceIdentityProvider? deviceIdentityProvider;
  final CollectionDeviceSequence? deviceSequence;

  @override
  State<CollectorRoutePage> createState() => _CollectorRoutePageState();
}

class _CollectorRoutePageState extends State<CollectorRoutePage> {
  late final PaymentSubmissionRepository _paymentRepository;
  late final CombinedPaymentSubmissionRepository _combinedPaymentRepository;
  late final CollectionCorrectionRepository _correctionRepository;
  late final CollectorCollectionLocationRepository
  _collectionLocationRepository;
  late final DeviceIdentityProvider _deviceIdentityProvider;
  late final CollectionDeviceSequence _deviceSequence;

  final Set<String> _expandedClients = <String>{};
  final Set<String> _expandedAreaUids = <String>{};
  final Set<String> _payingLoanIds = <String>{};
  final Map<String, PaymentSubmissionDraft> _pendingDirectDrafts =
      <String, PaymentSubmissionDraft>{};
  final Map<String, CombinedPaymentSubmissionDraft> _pendingCombinedDrafts =
      <String, CombinedPaymentSubmissionDraft>{};
  CollectorRouteLoadResult? _result;
  Object? _error;
  bool _loading = false;
  int _readGeneration = 0;
  ModalRoute<dynamic>? _clientToolsRoute;

  @override
  void initState() {
    super.initState();
    _paymentRepository =
        widget.paymentRepository ?? SpinaPaymentSubmissionRepository();
    _combinedPaymentRepository =
        widget.combinedPaymentRepository ??
        SpinaCombinedPaymentSubmissionRepository();
    _correctionRepository =
        widget.correctionRepository ?? SpinaCollectionCorrectionRepository();
    _collectionLocationRepository =
        widget.collectionLocationRepository ??
        SpinaCollectorCollectionLocationRepository();
    _deviceIdentityProvider =
        widget.deviceIdentityProvider ?? DeviceIdentityProvider();
    _deviceSequence = widget.deviceSequence ?? SecureCollectionDeviceSequence();
    _loadRoute();
  }

  Future<void> _loadRoute({bool supersede = false}) async {
    if (!mounted || (_loading && !supersede) || _readBlocked) return;
    final generation = ++_readGeneration;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await widget.loader.loadToday(widget.session);
      if (_currentRead(generation)) {
        setState(() => _result = result);
      }
    } on Object catch (error) {
      if (_currentRead(generation)) {
        setState(() {
          _error = error;
          if (isCollectorRouteAccessRejected(error)) {
            _result = null;
            // Denial hides private route data, but does not decide the outcome
            // or identity of an already submitted financial attempt.
            _expandedClients.clear();
            _expandedAreaUids.clear();
          }
        });
        if (_readBlocked) {
          final toolsRoute = _clientToolsRoute;
          if (toolsRoute != null && toolsRoute.isActive) {
            toolsRoute.navigator?.removeRoute(toolsRoute);
          }
        }
      }
    } finally {
      if (_currentRead(generation)) {
        setState(() => _loading = false);
      }
    }
  }

  bool get _readBlocked =>
      _error != null && isCollectorRouteAccessRejected(_error!);

  bool _currentRead(int generation) => mounted && generation == _readGeneration;

  @override
  void dispose() {
    _readGeneration++;
    super.dispose();
  }

  bool get _sessionRecovery =>
      widget.onSignOut != null &&
      (!_canLeaveRoute ||
          (_error as SpinaApiException).statusCode != 403 ||
          !Navigator.of(context).canPop());

  bool get _canRecoverRead =>
      !_readBlocked ||
      widget.onSignOut != null ||
      (_canLeaveRoute && Navigator.of(context).canPop());

  String get _recoveryLabel {
    if (!_readBlocked) return 'Retry';
    final status = (_error as SpinaApiException).statusCode;
    if (_sessionRecovery) {
      return status == 401 ? 'Sign in again' : 'Return to sign-in';
    }
    if (!_canLeaveRoute) {
      return 'Access unavailable. The unconfirmed payment is retained. Contact Management before leaving this session.';
    }
    if (Navigator.of(context).canPop()) return 'Back';
    return status == 426
        ? 'Update required'
        : status == 401
        ? 'Sign in again'
        : 'Access unavailable';
  }

  void _recoverRead() {
    if (!mounted) return;
    if (!_readBlocked) {
      _loadRoute();
    } else if (_sessionRecovery) {
      widget.onSignOut!();
    } else if (_canLeaveRoute && Navigator.of(context).canPop()) {
      Navigator.of(context).maybePop();
    }
  }

  String? _commonWriteBlockedReason(
    CollectorRouteLoadResult loaded,
    CollectorRouteEntry entry,
  ) {
    final error = _error;
    if (error != null && isCollectorRouteAccessRejected(error)) {
      return collectorFailureMessage(
        error,
        task: CollectorFailureTask.loadRoute,
      );
    }
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
        return 'No scheduled payment is due today. Open payment details for voluntary payment or other actions.';
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
    final canAddPartialContractReceipt =
        entry.contractCollectionReady && entry.contractTodayUnpaidAmount > 0;
    if (entry.processedToday && !canAddPartialContractReceipt) {
      return "Today's scheduled payment is already recorded. Use Edit for a correction before remittance.";
    }
    return null;
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
      amount: entry.suggestedPaymentAmount,
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
        payable.where((entry) => _isSevenBySevenLoan(entry.loanType)).length !=
            1) {
      throw const SpinaApiException(
        'Combined Pay requires exactly one payable Regular loan and one payable 7x7 loan.',
        code: 'combined_regular_7x7_required',
      );
    }
    final ordered = <CollectorRouteEntry>[
      ...payable.where((entry) => _isSevenBySevenLoan(entry.loanType)),
      ...payable.where((entry) => !_isSevenBySevenLoan(entry.loanType)),
    ];
    final identity = await _deviceIdentityProvider.load();
    final firstSequence = await _deviceSequence.reserve(3);
    final collectionDate = _dateOnly(loaded.route.routeDate ?? DateTime.now());
    return CombinedPaymentSubmissionDraft(
      idempotencyKey: SecureIdempotencyKeyGenerator().generate(),
      clientId: client.clientId,
      collectionDate: collectionDate,
      recordedAt: DateTime.now().toUtc(),
      deviceId: identity.installationId,
      deviceSequence: firstSequence,
      cashReceivedAmount: journalAmountFromCents(
        payable.fold<BigInt>(
          BigInt.zero,
          (sum, entry) =>
              sum + journalCents(requestMoney(entry.suggestedPaymentAmount)),
        ),
      ),
      legs: ordered
          .map(
            (entry) => CombinedPaymentLegDraft(
              routeEntryId: entry.id,
              loanId: entry.loanId,
              routeRevision: entry.routeRevision!,
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
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(blockedReason)));
      return;
    }
    if (_payingLoanIds.contains(entry.loanId)) {
      return;
    }

    setState(() => _payingLoanIds.add(entry.loanId));
    try {
      final draft =
          _pendingDirectDrafts[entry.loanId] ??
          await _buildDirectPaymentDraft(loaded, entry);
      if (!mounted || _readBlocked) return;
      _pendingDirectDrafts[entry.loanId] = draft;
      final result = await _paymentRepository.submit(widget.session, draft);
      if (!mounted || _readBlocked) {
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
        await _loadRoute(supersede: true);
        return;
      }

      _pendingDirectDrafts.remove(entry.loanId);
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(result.message)));
      await _loadRoute(supersede: true);
    } on SpinaApiException catch (error) {
      if (!mounted || _readBlocked) {
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
                : collectorFailureMessage(
                    error,
                    task: CollectorFailureTask.recordCollection,
                  ),
          ),
        ),
      );
    } on Object {
      if (!mounted || _readBlocked) {
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
        payable.where((entry) => _isSevenBySevenLoan(entry.loanType)).length !=
            1) {
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
      var draft = _pendingCombinedDrafts[client.clientId];
      if (draft == null) {
        final baseDraft = await _buildCombinedPaymentDraft(loaded, client);
        if (!mounted || _readBlocked) {
          return;
        }
        final preview = await _combinedPaymentRepository.preview(
          widget.session,
          baseDraft,
        );
        if (!mounted || _readBlocked) {
          return;
        }
        final cash = baseDraft.cashReceivedAmount;
        final exactNormal =
            preview.status == 'exact' &&
            !preview.requiresReview &&
            !preview.extraChoiceRequired &&
            !preview.regularPastDueFollowupRequired &&
            preview.shortAmount == 0 &&
            preview.extraAmount == 0 &&
            preview.cashReceivedAmountText == requestMoney(cash) &&
            preview.expectedTotalAmountText == requestMoney(cash);
        if (!exactNormal) {
          _pendingCombinedDrafts.remove(client.clientId);
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                '${preview.message} Use Payment details / other amount for this payment.',
              ),
            ),
          );
          return;
        }
        draft = baseDraft.withAllocationReview(
          cashReceivedAmount: cash,
          reviewedAllocationHash: preview.allocationHash,
        );
      }
      _pendingCombinedDrafts[client.clientId] = draft;
      final result = await _combinedPaymentRepository.submit(
        widget.session,
        draft,
      );
      if (!mounted || _readBlocked) {
        return;
      }
      if (result.requiresCashCustodyReview) {
        _pendingCombinedDrafts.remove(client.clientId);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('CASH CUSTODY REVIEW REQUIRED • ${result.message}'),
            duration: const Duration(seconds: 10),
          ),
        );
        await _loadRoute(supersede: true);
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
        await _loadRoute(supersede: true);
        return;
      }
      _pendingCombinedDrafts.remove(client.clientId);
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(result.message)));
      await _loadRoute(supersede: true);
    } on SpinaApiException catch (error) {
      if (!mounted || _readBlocked) {
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
                : collectorFailureMessage(
                    error,
                    task: CollectorFailureTask.recordCombinedCollection,
                  ),
          ),
        ),
      );
    } on Object {
      if (!mounted || _readBlocked) {
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
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(blockedReason)));
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
      await _loadRoute(supersede: true);
    }
  }

  Future<void> _openCorrection(
    CollectorRouteLoadResult loaded,
    CollectorRouteEntry entry,
  ) async {
    final blockedReason = _correctionBlockedReason(loaded, entry);
    if (blockedReason != null) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(blockedReason)));
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
      await _loadRoute(supersede: true);
    }
  }

  String? _correctionBlockedReason(
    CollectorRouteLoadResult loaded,
    CollectorRouteEntry entry,
  ) {
    if (_readBlocked) return collectorReadFailureMessage(_error!);
    if (loaded.isFromCache) {
      return 'Offline route copies are read-only. Reconnect and refresh before editing.';
    }
    if (!widget.session.permissions.contains(
      'collection.correct.own_unremitted',
    )) {
      return 'This account does not have collection correction permission.';
    }
    if (!entry.processedToday || entry.todayTransactionId == null) {
      return 'There is no collection entry to edit.';
    }
    if (entry.todayReceipts.any(
      (receipt) =>
          receipt.transactionId == entry.todayTransactionId &&
          receipt.isTreasuryFunded,
    )) {
      return 'Recipient funds were applied. Treasury reversals require authorized receipt review.';
    }
    if (entry.todayIsLocked) {
      return 'This collection is already remitted and permanently locked.';
    }
    if (!entry.canEditToday) {
      return 'This unremitted receipt is not available for correction from this route yet.';
    }
    return null;
  }

  void _toggleArea(String areaUid) {
    setState(() {
      if (!_expandedAreaUids.add(areaUid)) {
        _expandedAreaUids.remove(areaUid);
      }
    });
  }

  Future<void> _toggleClient(String clientId) async {
    final loaded = _result;
    if (loaded == null || !mounted) return;

    CollectorRouteClientGroup? client;
    for (final areaGroup in groupCollectorRoute(loaded.route)) {
      for (final candidate in areaGroup.clients) {
        if (candidate.clientId == clientId) {
          client = candidate;
          break;
        }
      }
      if (client != null) break;
    }
    final selectedClient = client;
    if (selectedClient == null) return;

    final selection = await showModalBottomSheet<CollectorClientToolSelection>(
      context: context,
      useSafeArea: true,
      isScrollControlled: true,
      builder: (context) {
        _clientToolsRoute = ModalRoute.of(context);
        return CollectorClientToolsSheet(
          client: selectedClient,
          directPayBlockedReasonFor: (entry) =>
              _directPayBlockedReason(loaded, entry),
          detailsBlockedReasonFor: (entry) =>
              _detailsBlockedReason(loaded, entry),
          correctionBlockedReasonFor: (entry) =>
              _correctionBlockedReason(loaded, entry),
        );
      },
    );
    _clientToolsRoute = null;
    if (!mounted || _readBlocked || selection == null) return;

    final entry = selection.entry;
    switch (selection.kind) {
      case CollectorClientToolKind.paymentDetails:
        if (entry != null) await _openCollectionDetails(loaded, entry);
      case CollectorClientToolKind.correction:
        if (entry != null) await _openCorrection(loaded, entry);
      case CollectorClientToolKind.schedule:
        await Navigator.of(context).push<void>(
          MaterialPageRoute<void>(
            builder: (context) => CollectorClientSchedulePage(
              session: widget.session,
              client: selectedClient,
            ),
          ),
        );
      case CollectorClientToolKind.collectionLocation:
        await Navigator.of(context).push<void>(
          MaterialPageRoute<void>(
            builder: (context) => CollectorClientCollectionLocationPage(
              session: widget.session,
              client: selectedClient,
              repository: _collectionLocationRepository,
            ),
          ),
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    return PopScope<void>(
      canPop: _canLeaveRoute,
      onPopInvokedWithResult: (didPop, _) {
        if (didPop) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'A payment is still in progress or not confirmed. Stay on this route and check the same payment before leaving.',
            ),
          ),
        );
      },
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Daily Collection'),
          actions: [
            IconButton(
              tooltip: 'Refresh route',
              onPressed: _loading || _readBlocked ? null : _loadRoute,
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
        body: SafeArea(child: _buildBody(context)),
      ),
    );
  }

  bool get _canLeaveRoute =>
      _payingLoanIds.isEmpty &&
      _pendingDirectDrafts.isEmpty &&
      _pendingCombinedDrafts.isEmpty;

  Widget _buildBody(BuildContext context) {
    final result = _result;
    if (_loading && result == null) {
      return const Center(child: CircularProgressIndicator());
    }

    final error = _error;
    if (error != null && result == null) {
      return Center(
        child: WorkspaceReadNotice(
          message: collectorReadFailureMessage(error),
          actionLabel: _recoveryLabel,
          onAction: _canRecoverRead ? _recoverRead : null,
        ),
      );
    }

    final loaded = result!;
    final route = loaded.route;
    final areaGroups = groupCollectorRoute(route);
    final areaTree = route.areaNodes.isEmpty
        ? const <CollectorRouteTreeNode>[]
        : buildCollectorRouteTree(route);
    final clientCount = areaGroups.fold<int>(
      0,
      (total, group) => total + group.clientCount,
    );

    return RefreshIndicator(
      onRefresh: _loadRoute,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(10, 8, 10, 12),
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
          if (loaded.isFromCache) ...[
            const SizedBox(height: 8),
            const _CollectorOfflineReadOnlyNotice(),
          ],
          if (loaded.warning != null && !loaded.isFromCache) ...[
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
            WorkspaceReadNotice(
              message: collectorReadFailureMessage(error),
              actionLabel: _recoveryLabel,
              onAction: _canRecoverRead ? _recoverRead : null,
              stale: true,
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
          else if (areaTree.isNotEmpty)
            CollectorRouteTree(
              roots: areaTree,
              expandedAreaUids: _expandedAreaUids,
              expandedClients: _expandedClients,
              directPayBlockedReasonFor: (entry) =>
                  _directPayBlockedReason(loaded, entry),
              payingLoanIds: _payingLoanIds,
              pendingDirectLoanIds: _pendingPaymentLoanIds(),
              onToggleArea: _toggleArea,
              onToggleClient: _toggleClient,
              onRecord: (entry) => _payNow(loaded, entry),
              onRecordCombined: (client) => _payCombined(loaded, client),
              detailsBuilder: (entry) => _LoanDetails(
                entry: entry,
                blockedReason: _directPayBlockedReason(loaded, entry),
                detailsBlockedReason: _detailsBlockedReason(loaded, entry),
                correctionBlockedReason: _correctionBlockedReason(
                  loaded,
                  entry,
                ),
                onDetails: () => _openCollectionDetails(loaded, entry),
                onEdit: () => _openCorrection(loaded, entry),
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
                  correctionBlockedReason: _correctionBlockedReason(
                    loaded,
                    entry,
                  ),
                  onDetails: () => _openCollectionDetails(loaded, entry),
                  onEdit: () => _openCorrection(loaded, entry),
                ),
              ),
              const SizedBox(height: 8),
            ],
        ],
      ),
    );
  }
}

class _CollectorOfflineReadOnlyNotice extends StatelessWidget {
  const _CollectorOfflineReadOnlyNotice();

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Card(
      key: const Key('collector-offline-read-only'),
      color: colors.secondaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.cloud_off_outlined, color: colors.onSecondaryContainer),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Offline copy — read-only',
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      color: colors.onSecondaryContainer,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    'You can review the saved route, but no payment is accepted or queued. Reconnect and refresh before collecting.',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: colors.onSecondaryContainer,
                    ),
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
        else if (!entry.processedToday && detailsBlockedReason != blockedReason)
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
          style: Theme.of(
            context,
          ).textTheme.labelMedium?.copyWith(fontWeight: FontWeight.w800),
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
                  '${receipt.isTreasuryFunded ? ' · Recipient funds applied; no Collector cash' : ''}'
                  '${receipt.isLocked ? ' • Locked' : ''}',
                  style: Theme.of(
                    context,
                  ).textTheme.bodySmall?.copyWith(fontWeight: FontWeight.w700),
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

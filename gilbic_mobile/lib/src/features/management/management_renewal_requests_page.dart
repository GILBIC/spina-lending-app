import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow.dart';
import 'package:gilbic_mobile/src/core/renewals/management_renewal_workflow.dart';
import 'package:gilbic_mobile/src/core/renewals/management_renewal_workflow_repository.dart';
import 'package:gilbic_mobile/src/core/time/spina_business_time.dart';

class ManagementRenewalRequestsPage extends StatefulWidget {
  const ManagementRenewalRequestsPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ManagementRenewalWorkflowRepository? repository;

  @override
  State<ManagementRenewalRequestsPage> createState() =>
      _ManagementRenewalRequestsPageState();
}

class _ManagementRenewalRequestsPageState
    extends State<ManagementRenewalRequestsPage> {
  late final ManagementRenewalWorkflowRepository _repository;
  List<ManagementRenewalWorkflowItem> _items = const [];
  String _status = 'pending';
  String? _deviceId;
  String? _errorMessage;
  String? _busyRequestId;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _repository =
        widget.repository ?? SpinaManagementRenewalWorkflowRepository();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final items = await _repository.list(
        widget.session,
        deviceId: identity.installationId,
        status: _status,
      );
      if (!mounted) return;
      setState(() {
        _deviceId = identity.installationId;
        _items = items;
      });
    } on SpinaApiException catch (error) {
      if (mounted) setState(() => _errorMessage = error.message);
    } on Object {
      if (mounted) {
        setState(
          () => _errorMessage = 'Management renewal workflow could not be loaded.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _submitTerms(ManagementRenewalWorkflowItem item) async {
    final draft = await showDialog<ManagementRenewalTermsDraft>(
      context: context,
      builder: (context) => _ManagementRenewalTermsDialog(item: item),
    );
    if (draft == null) return;
    await _runAction(
      item.request.requestId,
      successMessage: 'Management renewal terms recorded.',
      action: (deviceId) => _repository.submitTerms(
        widget.session,
        deviceId: deviceId,
        requestId: item.request.requestId,
        draft: draft,
      ),
    );
  }

  Future<void> _reject(ManagementRenewalWorkflowItem item) async {
    final note = await showDialog<String>(
      context: context,
      builder: (context) => _RejectRenewalDialog(request: item.request),
    );
    if (note == null) return;
    await _runAction(
      item.request.requestId,
      successMessage: 'Renewal request rejected.',
      action: (deviceId) => _repository.submitTerms(
        widget.session,
        deviceId: deviceId,
        requestId: item.request.requestId,
        draft: ManagementRenewalTermsDraft(
          decision: 'rejected',
          reviewNote: note,
          overrideReason: '',
          officeProcessingRequired: true,
          signers: const <ManagementRenewalSignerDraft>[],
        ),
      ),
    );
  }

  Future<void> _releaseToCollector(ManagementRenewalWorkflowItem item) {
    return _runAction(
      item.request.requestId,
      successMessage: 'Cash release to Collector recorded.',
      action: (deviceId) => _repository.releaseToCollector(
        widget.session,
        deviceId: deviceId,
        requestId: item.request.requestId,
      ),
    );
  }

  Future<void> _reviewProof(
    ManagementRenewalWorkflowItem item,
    String decision,
  ) async {
    final note = await showDialog<String>(
      context: context,
      builder: (context) => _ProofReviewDialog(decision: decision),
    );
    if (note == null) return;
    final message = switch (decision) {
      'approved' => 'Renewal handover proof approved.',
      'request_new_photo' => 'New handover photo requested.',
      _ => 'Renewal handover proof flagged for review.',
    };
    await _runAction(
      item.request.requestId,
      successMessage: message,
      action: (deviceId) => _repository.reviewProof(
        widget.session,
        deviceId: deviceId,
        requestId: item.request.requestId,
        decision: decision,
        note: note,
      ),
    );
  }

  Future<void> _activate(ManagementRenewalWorkflowItem item) {
    return _runAction(
      item.request.requestId,
      successMessage: 'Renewal activation check completed.',
      action: (deviceId) => _repository.activate(
        widget.session,
        deviceId: deviceId,
        requestId: item.request.requestId,
      ),
    );
  }

  Future<void> _runAction(
    String requestId, {
    required String successMessage,
    required Future<CollectorRenewalRequest> Function(String deviceId) action,
  }) async {
    final deviceId = _deviceId;
    if (deviceId == null || _busyRequestId != null) return;
    setState(() => _busyRequestId = requestId);
    try {
      await action(deviceId);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(successMessage)),
      );
      await _load();
    } on SpinaApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Renewal action could not be completed.')),
        );
      }
    } finally {
      if (mounted) setState(() => _busyRequestId = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Renewal Requests'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _loading || _busyRequestId != null ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
            children: [
              const _WorkflowPolicyCard(),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                key: const Key('renewal-status-filter'),
                initialValue: _status,
                decoration: const InputDecoration(labelText: 'Workflow status'),
                items: const [
                  DropdownMenuItem(value: 'pending', child: Text('Pending')),
                  DropdownMenuItem(value: 'approved', child: Text('Approved')),
                  DropdownMenuItem(value: 'rejected', child: Text('Rejected')),
                ],
                onChanged: _loading || _busyRequestId != null
                    ? null
                    : (value) {
                        if (value == null || value == _status) return;
                        setState(() => _status = value);
                        _load();
                      },
              ),
              const SizedBox(height: 16),
              if (_loading && _items.isEmpty)
                const Padding(
                  padding: EdgeInsets.all(32),
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (_errorMessage != null && _items.isEmpty)
                _ErrorCard(message: _errorMessage!, onRetry: _load)
              else if (_items.isEmpty)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Text(
                      'No $_status renewal workflow items.',
                      textAlign: TextAlign.center,
                    ),
                  ),
                )
              else
                for (final item in _items) ...[
                  _ManagementRenewalWorkflowCard(
                    item: item,
                    busy: _busyRequestId == item.request.requestId,
                    onTerms: () => _submitTerms(item),
                    onReject: () => _reject(item),
                    onRelease: () => _releaseToCollector(item),
                    onApproveProof: () => _reviewProof(item, 'approved'),
                    onRequestPhoto: () =>
                        _reviewProof(item, 'request_new_photo'),
                    onFlagProof: () => _reviewProof(item, 'flag_for_review'),
                    onActivate: () => _activate(item),
                  ),
                  const SizedBox(height: 10),
                ],
            ],
          ),
        ),
      ),
    );
  }
}

class _WorkflowPolicyCard extends StatelessWidget {
  const _WorkflowPolicyCard();

  @override
  Widget build(BuildContext context) {
    return const Card(
      child: Padding(
        padding: EdgeInsets.all(14),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.verified_user_outlined),
            SizedBox(width: 12),
            Expanded(
              child: Text(
                'Management sets the approved new principal only after the permanently assigned Collector recommendation. '
                'Approval does not itself create or release a loan. Old-balance settlement, cash custody, handover proof, '
                'client confirmation, and activation remain separate server-authoritative gates.',
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ManagementRenewalWorkflowCard extends StatelessWidget {
  const _ManagementRenewalWorkflowCard({
    required this.item,
    required this.busy,
    required this.onTerms,
    required this.onReject,
    required this.onRelease,
    required this.onApproveProof,
    required this.onRequestPhoto,
    required this.onFlagProof,
    required this.onActivate,
  });

  final ManagementRenewalWorkflowItem item;
  final bool busy;
  final VoidCallback onTerms;
  final VoidCallback onReject;
  final VoidCallback onRelease;
  final VoidCallback onApproveProof;
  final VoidCallback onRequestPhoto;
  final VoidCallback onFlagProof;
  final VoidCallback onActivate;

  @override
  Widget build(BuildContext context) {
    final request = item.request;
    final scheme = Theme.of(context).colorScheme;
    final recommendation = request.collectorRecommendation;
    final canRelease = request.approved &&
        request.clientDecision == 'accepted' &&
        !request.officeProcessingRequired &&
        request.cashReleasedToCollectorAt == null;
    final canReviewProof = request.approved &&
        request.handoverProofStatus == 'under_review' &&
        request.cashGivenToClientAt != null;
    final canTryActivation = request.approved &&
        request.activationStatus != 'active' &&
        request.handoverProofStatus == 'approved' &&
        request.clientCashConfirmedAt != null &&
        request.newLoanId != null;

    return Card(
      key: Key('management-renewal-${request.requestId}'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.autorenew),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        request.clientName,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text('${request.clientCode} • ${request.area}'),
                    ],
                  ),
                ),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: request.status == 'rejected'
                        ? scheme.errorContainer
                        : scheme.secondaryContainer,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(request.displayStatus),
                ),
              ],
            ),
            const Divider(height: 24),
            _LabelValue('Loan', '${request.loanTypeName} • ${request.loanNumber}'),
            _LabelValue('Current principal', _money(request.currentPrincipal)),
            _LabelValue('Remaining old balance', _money(request.remainingBalance)),
            _LabelValue('Contractual total', _money(request.contractualTotal)),
            _LabelValue(
              'Paid toward contractual total',
              '${_money(request.paidCash)} • ${request.paidPercent.toStringAsFixed(1)}%',
            ),
            _LabelValue('Client requested', _money(request.requestedAmount)),
            if (!request.isSevenBySeven)
              _LabelValue(
                'Regular 50% gate',
                request.regular50PercentEligible ? 'Eligible' : 'Below 50%',
              ),
            if (request.isSevenBySeven)
              const _LabelValue(
                '7x7 rule',
                'Management approval required regardless of paid %',
              ),
            if (request.clientMessage.isNotEmpty) ...[
              const Divider(height: 22),
              Text('Client message: ${request.clientMessage}'),
            ],
            const Divider(height: 22),
            Text(
              'Collector recommendation',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 6),
            if (recommendation == null)
              const Text('Waiting for the permanently assigned Collector.')
            else ...[
              _LabelValue(
                'Decision',
                recommendation == 'recommend'
                    ? 'Recommend'
                    : 'Do Not Recommend',
              ),
              if (request.collectorReasonCode.isNotEmpty)
                _LabelValue('Reason', request.collectorReasonCode),
              if (request.collectorComment.isNotEmpty)
                _LabelValue('Collector comment', request.collectorComment),
              if (request.recommendedAt != null)
                _LabelValue(
                  'Recommended',
                  formatSpinaBusinessDateTime(request.recommendedAt),
                ),
            ],
            if (request.approvedPrincipal != null ||
                request.status == 'approved') ...[
              const Divider(height: 22),
              Text(
                'Approved workflow',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const SizedBox(height: 6),
              if (request.approvedPrincipal != null)
                _LabelValue(
                  'Approved new principal',
                  _money(request.approvedPrincipal!),
                ),
              _LabelValue(
                'Client decision',
                request.clientDecision ?? 'Awaiting Client Accept & Continue',
              ),
              _LabelValue(
                'Processing path',
                request.officeProcessingRequired
                    ? 'Office processing required'
                    : 'Remote app workflow',
              ),
              _LabelValue(
                'Signer readiness',
                request.signerReadinessStatus.replaceAll('_', ' '),
              ),
              if (request.renewalOffsetAmount != null)
                _LabelValue(
                  'Renewal Offset — Settled from New Loan Proceeds',
                  _money(request.renewalOffsetAmount!),
                ),
              if (request.netReleaseAmount != null)
                _LabelValue(
                  'Net cash release',
                  _money(request.netReleaseAmount!),
                ),
              if (request.amountLockedAt != null)
                _LabelValue(
                  'Amount locked',
                  formatSpinaBusinessDateTime(request.amountLockedAt),
                ),
              if (request.signers.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text('Required signers',
                    style: Theme.of(context).textTheme.titleSmall),
                const SizedBox(height: 4),
                for (final signer in request.signers)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Text(
                      '${_partyRoleLabel(signer.partyRole)} • ${signer.fullName} • '
                      '${signer.hasApp ? 'app linked' : 'no app'} • '
                      '${signer.governmentIdVerified ? 'ID verified' : 'ID pending'} • '
                      '${signer.selfieVerified ? 'selfie verified' : 'selfie pending'} • '
                      '${signer.signed ? 'signed' : 'signature pending'}',
                    ),
                  ),
              ],
              const SizedBox(height: 8),
              _CustodyTimeline(request: request),
              _LabelValue(
                'Handover proof',
                request.handoverProofStatus.replaceAll('_', ' '),
              ),
              _LabelValue(
                'Activation',
                request.activationStatus.replaceAll('_', ' '),
              ),
              if (request.newLoanId != null)
                _LabelValue('Linked new loan', request.newLoanId!),
            ],
            if (request.reviewNote.isNotEmpty)
              _LabelValue('Management note', request.reviewNote),
            if (request.managementOverrideReason.isNotEmpty)
              _LabelValue('Override reason', request.managementOverrideReason),
            if (request.status == 'pending' && recommendation != null) ...[
              const SizedBox(height: 14),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      key: Key('reject-renewal-${request.requestId}'),
                      onPressed: busy ? null : onReject,
                      icon: const Icon(Icons.close),
                      label: const Text('Reject'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: FilledButton.icon(
                      key: Key('review-renewal-terms-${request.requestId}'),
                      onPressed: busy ? null : onTerms,
                      icon: const Icon(Icons.fact_check_outlined),
                      label: const Text('Set Terms'),
                    ),
                  ),
                ],
              ),
            ],
            if (request.status == 'pending' && recommendation == null) ...[
              const SizedBox(height: 12),
              const Text(
                'Management terms are locked until the permanently assigned Collector submits a recommendation.',
              ),
            ],
            if (request.approved && request.officeProcessingRequired) ...[
              const SizedBox(height: 12),
              const Text(
                'Office-only renewal: mobile cash release to a Collector is disabled. Complete the required signing and release controls in the office.',
              ),
            ],
            if (canRelease) ...[
              const SizedBox(height: 12),
              const Text(
                'The server will require authoritative renewal execution/disbursement evidence before it records cash release.',
              ),
              const SizedBox(height: 8),
              FilledButton.icon(
                key: Key('release-renewal-${request.requestId}'),
                onPressed: busy ? null : onRelease,
                icon: const Icon(Icons.payments_outlined),
                label: const Text('Release Cash to Collector'),
              ),
            ],
            if (canReviewProof) ...[
              const SizedBox(height: 14),
              Text('Handover proof review',
                  style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  FilledButton.icon(
                    key: Key('approve-proof-${request.requestId}'),
                    onPressed: busy ? null : onApproveProof,
                    icon: const Icon(Icons.check_circle_outline),
                    label: const Text('Approve Proof'),
                  ),
                  OutlinedButton.icon(
                    key: Key('request-photo-${request.requestId}'),
                    onPressed: busy ? null : onRequestPhoto,
                    icon: const Icon(Icons.add_a_photo_outlined),
                    label: const Text('Request New Photo'),
                  ),
                  OutlinedButton.icon(
                    key: Key('flag-proof-${request.requestId}'),
                    onPressed: busy ? null : onFlagProof,
                    icon: const Icon(Icons.flag_outlined),
                    label: const Text('Flag for Review'),
                  ),
                ],
              ),
            ],
            if (canTryActivation) ...[
              const SizedBox(height: 14),
              FilledButton.icon(
                key: Key('activate-renewal-${request.requestId}'),
                onPressed: busy ? null : onActivate,
                icon: const Icon(Icons.verified_outlined),
                label: Text(
                  request.readyForActivation
                      ? 'Activate New Loan'
                      : 'Retry Activation',
                ),
              ),
            ],
            if (busy) ...[
              const SizedBox(height: 12),
              const LinearProgressIndicator(),
            ],
          ],
        ),
      ),
    );
  }
}

class _ManagementRenewalTermsDialog extends StatefulWidget {
  const _ManagementRenewalTermsDialog({required this.item});

  final ManagementRenewalWorkflowItem item;

  @override
  State<_ManagementRenewalTermsDialog> createState() =>
      _ManagementRenewalTermsDialogState();
}

class _ManagementRenewalTermsDialogState
    extends State<_ManagementRenewalTermsDialog> {
  late final TextEditingController _principalController;
  final TextEditingController _noteController = TextEditingController();
  final TextEditingController _overrideController = TextEditingController();
  final TextEditingController _supportingNameController = TextEditingController();
  final TextEditingController _supportingUserIdController =
      TextEditingController();
  final List<ManagementRenewalSignerDraft> _supportingSigners = [];
  String _supportingRole = 'guarantor';
  String? _error;

  @override
  void initState() {
    super.initState();
    _principalController = TextEditingController(
      text: widget.item.request.requestedAmount.toStringAsFixed(2),
    );
  }

  @override
  void dispose() {
    _principalController.dispose();
    _noteController.dispose();
    _overrideController.dispose();
    _supportingNameController.dispose();
    _supportingUserIdController.dispose();
    super.dispose();
  }

  void _addSupportingSigner() {
    final fullName = _supportingNameController.text.trim();
    final userId = _supportingUserIdController.text.trim();
    if (fullName.length < 2) {
      setState(() => _error = 'Enter the supporting signer full name.');
      return;
    }
    setState(() {
      _supportingSigners.add(
        ManagementRenewalSignerDraft(
          partyRole: _supportingRole,
          fullName: fullName,
          userId: userId.isEmpty ? null : userId,
          governmentIdVerified: false,
          selfieVerified: false,
        ),
      );
      _supportingNameController.clear();
      _supportingUserIdController.clear();
      _error = null;
    });
  }

  void _submit() {
    final principal = double.tryParse(_principalController.text.trim());
    if (principal == null || principal <= 0) {
      setState(() => _error = 'Enter the approved new principal.');
      return;
    }
    final request = widget.item.request;
    final overrideReason = _overrideController.text.trim();
    if (request.collectorRecommendation == 'do_not_recommend' &&
        overrideReason.length < 3) {
      setState(
        () => _error =
            'Management override reason is required after Do Not Recommend.',
      );
      return;
    }

    final signers = <ManagementRenewalSignerDraft>[
      ManagementRenewalSignerDraft(
        partyRole: 'borrower',
        fullName: request.clientName,
        userId: widget.item.borrowerUserId,
        governmentIdVerified: false,
        selfieVerified: false,
      ),
      ..._supportingSigners,
    ];

    Navigator.pop(
      context,
      ManagementRenewalTermsDraft(
        decision: 'approved',
        approvedPrincipal: principal,
        reviewNote: _noteController.text.trim(),
        overrideReason: overrideReason,
        // Remote signing remains fail-closed until SPINA has an authoritative
        // government-ID + selfie evidence source. Management UI must not create
        // identity-verification timestamps from manual checkboxes.
        officeProcessingRequired: true,
        signers: signers,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final request = widget.item.request;
    return AlertDialog(
      title: const Text('Set Management renewal terms'),
      content: SizedBox(
        width: 560,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('${request.clientName} • ${request.loanTypeName}'),
              const SizedBox(height: 4),
              Text(
                'Client requested ${_money(request.requestedAmount)}. Management alone sets the approved principal.',
              ),
              const SizedBox(height: 14),
              TextField(
                key: const Key('renewal-approved-principal'),
                controller: _principalController,
                keyboardType:
                    const TextInputType.numberWithOptions(decimal: true),
                decoration:
                    const InputDecoration(labelText: 'Approved new principal'),
              ),
              const SizedBox(height: 10),
              TextField(
                key: const Key('renewal-management-note'),
                controller: _noteController,
                maxLength: 1000,
                maxLines: 3,
                decoration:
                    const InputDecoration(labelText: 'Management note (optional)'),
              ),
              if (request.collectorRecommendation == 'do_not_recommend') ...[
                const SizedBox(height: 8),
                TextField(
                  key: const Key('renewal-override-reason'),
                  controller: _overrideController,
                  maxLength: 1000,
                  maxLines: 3,
                  decoration: const InputDecoration(
                    labelText: 'Mandatory Management override reason',
                  ),
                ),
              ],
              const SizedBox(height: 8),
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(12),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.lock_outline),
                      SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          'Office processing is required for now. Remote signing stays fail-closed until authoritative government-ID and selfie verification evidence is connected. Manual Management checkboxes cannot mark identity as verified.',
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 12),
              Text('Required borrower signer',
                  style: Theme.of(context).textTheme.titleSmall),
              Text(
                '${request.clientName} • ${widget.item.borrowerUserId == null ? 'no linked app account' : 'app account linked'}',
              ),
              const SizedBox(height: 14),
              Text('Supporting party (optional)',
                  style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 6),
              DropdownButtonFormField<String>(
                key: const Key('renewal-supporting-role'),
                initialValue: _supportingRole,
                decoration: const InputDecoration(labelText: 'Party role'),
                items: const [
                  DropdownMenuItem(
                    value: 'guarantor',
                    child: Text('Guarantor'),
                  ),
                  DropdownMenuItem(
                    value: 'solidary_co_maker',
                    child: Text('Solidary co-maker'),
                  ),
                  DropdownMenuItem(value: 'surety', child: Text('Surety')),
                ],
                onChanged: (value) {
                  if (value != null) setState(() => _supportingRole = value);
                },
              ),
              const SizedBox(height: 8),
              TextField(
                key: const Key('renewal-supporting-name'),
                controller: _supportingNameController,
                decoration: const InputDecoration(labelText: 'Full name'),
              ),
              const SizedBox(height: 8),
              TextField(
                key: const Key('renewal-supporting-user-id'),
                controller: _supportingUserIdController,
                decoration: const InputDecoration(
                  labelText: 'Linked app user ID (optional)',
                  helperText: 'Leave blank when the supporting party has no app.',
                ),
              ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                key: const Key('add-renewal-supporting-signer'),
                onPressed: _addSupportingSigner,
                icon: const Icon(Icons.person_add_alt_1),
                label: const Text('Add Supporting Party'),
              ),
              if (_supportingSigners.isNotEmpty) ...[
                const SizedBox(height: 8),
                for (var index = 0;
                    index < _supportingSigners.length;
                    index += 1)
                  ListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    title: Text(_supportingSigners[index].fullName),
                    subtitle: Text(
                      _partyRoleLabel(_supportingSigners[index].partyRole),
                    ),
                    trailing: IconButton(
                      tooltip: 'Remove',
                      onPressed: () => setState(
                        () => _supportingSigners.removeAt(index),
                      ),
                      icon: const Icon(Icons.remove_circle_outline),
                    ),
                  ),
              ],
              if (_error != null) ...[
                const SizedBox(height: 8),
                Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Back'),
        ),
        FilledButton(
          key: const Key('confirm-renewal-terms'),
          onPressed: _submit,
          child: const Text('Record Terms'),
        ),
      ],
    );
  }
}

class _RejectRenewalDialog extends StatefulWidget {
  const _RejectRenewalDialog({required this.request});

  final CollectorRenewalRequest request;

  @override
  State<_RejectRenewalDialog> createState() => _RejectRenewalDialogState();
}

class _RejectRenewalDialogState extends State<_RejectRenewalDialog> {
  final TextEditingController _controller = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _submit() {
    final note = _controller.text.trim();
    if (note.length < 3) {
      setState(() => _error = 'Enter the Management rejection reason.');
      return;
    }
    Navigator.pop(context, note);
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Reject renewal request?'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(widget.request.clientName),
          const SizedBox(height: 10),
          TextField(
            key: const Key('renewal-rejection-note'),
            controller: _controller,
            maxLength: 1000,
            maxLines: 4,
            decoration: InputDecoration(
              labelText: 'Management rejection reason',
              errorText: _error,
              alignLabelWithHint: true,
            ),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Back'),
        ),
        FilledButton(
          key: const Key('confirm-renewal-rejection'),
          onPressed: _submit,
          child: const Text('Reject Request'),
        ),
      ],
    );
  }
}

class _ProofReviewDialog extends StatefulWidget {
  const _ProofReviewDialog({required this.decision});

  final String decision;

  @override
  State<_ProofReviewDialog> createState() => _ProofReviewDialogState();
}

class _ProofReviewDialogState extends State<_ProofReviewDialog> {
  final TextEditingController _controller = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _submit() {
    final note = _controller.text.trim();
    if (widget.decision != 'approved' && note.length < 3) {
      setState(() => _error = 'Enter the proof-review reason.');
      return;
    }
    Navigator.pop(context, note);
  }

  @override
  Widget build(BuildContext context) {
    final title = switch (widget.decision) {
      'approved' => 'Approve handover proof?',
      'request_new_photo' => 'Request a new handover photo?',
      _ => 'Flag handover proof for review?',
    };
    return AlertDialog(
      title: Text(title),
      content: TextField(
        key: const Key('renewal-proof-review-note'),
        controller: _controller,
        maxLength: 1000,
        maxLines: 4,
        decoration: InputDecoration(
          labelText: widget.decision == 'approved'
              ? 'Management note (optional)'
              : 'Reason',
          errorText: _error,
          alignLabelWithHint: true,
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Back'),
        ),
        FilledButton(
          key: const Key('confirm-renewal-proof-review'),
          onPressed: _submit,
          child: const Text('Confirm'),
        ),
      ],
    );
  }
}

class _CustodyTimeline extends StatelessWidget {
  const _CustodyTimeline({required this.request});

  final CollectorRenewalRequest request;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Cash custody', style: Theme.of(context).textTheme.titleSmall),
        _LabelValue(
          'Management → Collector',
          _eventStatus(request.cashReleasedToCollectorAt),
        ),
        _LabelValue(
          'Collector received',
          _eventStatus(request.collectorCashReceivedAt),
        ),
        _LabelValue(
          'Collector → Client',
          _eventStatus(request.cashGivenToClientAt),
        ),
        _LabelValue(
          'Client confirmed',
          _eventStatus(request.clientCashConfirmedAt),
        ),
      ],
    );
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 12),
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

class _LabelValue extends StatelessWidget {
  const _LabelValue(this.label, this.value);

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: Text(label)),
          const SizedBox(width: 12),
          Flexible(child: Text(value, textAlign: TextAlign.right)),
        ],
      ),
    );
  }
}

String _eventStatus(DateTime? value) {
  return value == null ? 'Pending' : formatSpinaBusinessDateTime(value);
}

String _partyRoleLabel(String role) {
  return switch (role) {
    'borrower' => 'Borrower',
    'guarantor' => 'Guarantor',
    'solidary_co_maker' => 'Solidary co-maker',
    'surety' => 'Surety',
    _ => role.replaceAll('_', ' '),
  };
}

String _money(double value) {
  final fixed = value.toStringAsFixed(2);
  final negative = fixed.startsWith('-');
  final unsigned = negative ? fixed.substring(1) : fixed;
  final parts = unsigned.split('.');
  final digits = parts.first;
  final buffer = StringBuffer();
  for (var index = 0; index < digits.length; index += 1) {
    if (index > 0 && (digits.length - index) % 3 == 0) buffer.write(',');
    buffer.write(digits[index]);
  }
  return '${negative ? '-' : ''}₱$buffer.${parts.last}';
}

import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow_repository.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';
import 'package:image_picker/image_picker.dart';

class CollectorRenewalRequestsPage extends StatefulWidget {
  const CollectorRenewalRequestsPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.imagePicker,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final CollectorRenewalWorkflowRepository? repository;
  final ImagePicker? imagePicker;

  @override
  State<CollectorRenewalRequestsPage> createState() =>
      _CollectorRenewalRequestsPageState();
}

class _CollectorRenewalRequestsPageState
    extends State<CollectorRenewalRequestsPage> {
  late final CollectorRenewalWorkflowRepository _repository;
  late final ImagePicker _imagePicker;
  List<CollectorRenewalRequest> _requests = const <CollectorRenewalRequest>[];
  String? _deviceId;
  String? _error;
  bool _loading = true;
  final Set<String> _busy = <String>{};

  @override
  void initState() {
    super.initState();
    _repository =
        widget.repository ?? SpinaCollectorRenewalWorkflowRepository();
    _imagePicker = widget.imagePicker ?? ImagePicker();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final requests = await _repository.list(
        widget.session,
        deviceId: identity.installationId,
      );
      if (!mounted) return;
      setState(() {
        _deviceId = identity.installationId;
        _requests = requests;
      });
    } on SpinaApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) {
        setState(() => _error = 'Renewal requests could not be loaded.');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _recommend(
    CollectorRenewalRequest request,
    String recommendation,
  ) async {
    final result = await showDialog<_RecommendationDraft>(
      context: context,
      builder: (context) => _RecommendationDialog(
        recommendation: recommendation,
      ),
    );
    if (result == null) return;
    final deviceId = _deviceId;
    if (deviceId == null) return;
    await _run(
      request.requestId,
      () => _repository.recommend(
        widget.session,
        deviceId: deviceId,
        requestId: request.requestId,
        recommendation: recommendation,
        reasonCode: result.reasonCode,
        comment: result.comment,
      ),
      successMessage: recommendation == 'recommend'
          ? 'Recommendation sent to Management.'
          : 'Non-recommendation sent to Management.',
    );
  }

  Future<void> _confirmCashReceived(CollectorRenewalRequest request) async {
    if (!await _confirm(
      title: 'Confirm cash received?',
      message:
          'Confirm only after you physically receive the locked ${_money(request.netReleaseAmount ?? 0)} from Management.',
      action: 'Confirm Received',
    )) {
      return;
    }
    final deviceId = _deviceId;
    if (deviceId == null) return;
    await _run(
      request.requestId,
      () => _repository.confirmCashReceived(
        widget.session,
        deviceId: deviceId,
        requestId: request.requestId,
      ),
      successMessage: 'Cash custody transferred to you.',
    );
  }

  Future<void> _confirmCashGiven(CollectorRenewalRequest request) async {
    if (!await _confirm(
      title: 'Confirm cash given to client?',
      message:
          'Confirm only after you physically hand the locked ${_money(request.netReleaseAmount ?? 0)} to ${request.clientName}. The client must still confirm independently.',
      action: 'Cash Given',
    )) {
      return;
    }
    final deviceId = _deviceId;
    if (deviceId == null) return;
    await _run(
      request.requestId,
      () => _repository.confirmCashGiven(
        widget.session,
        deviceId: deviceId,
        requestId: request.requestId,
      ),
      successMessage: 'Cash handover recorded. Client confirmation is still required.',
    );
  }

  Future<void> _captureProof(CollectorRenewalRequest request) async {
    final deviceId = _deviceId;
    if (deviceId == null || _busy.contains(request.requestId)) return;
    final source = await showModalBottomSheet<ImageSource>(
      context: context,
      builder: (context) => SafeArea(
        child: Wrap(
          children: [
            ListTile(
              leading: const Icon(Icons.camera_alt_outlined),
              title: const Text('Take handover photo'),
              onTap: () => Navigator.pop(context, ImageSource.camera),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_outlined),
              title: const Text('Choose from gallery'),
              onTap: () => Navigator.pop(context, ImageSource.gallery),
            ),
          ],
        ),
      ),
    );
    if (source == null) return;
    try {
      final image = await _imagePicker.pickImage(
        source: source,
        imageQuality: 75,
        maxWidth: 1600,
        maxHeight: 1600,
        requestFullMetadata: false,
      );
      if (image == null || !mounted) return;
      final bytes = await image.readAsBytes();
      final draft = RenewalHandoverPhotoDraft.fromBytes(
        filename: image.name,
        bytes: Uint8List.fromList(bytes),
        suggestedContentType: image.mimeType,
      );
      final validation = draft.validate();
      if (validation != null) {
        _message(validation);
        return;
      }
      setState(() => _busy.add(request.requestId));
      await _repository.uploadHandoverPhoto(
        widget.session,
        deviceId: deviceId,
        requestId: request.requestId,
        draft: draft,
      );
      if (!mounted) return;
      _message('Handover proof submitted for Management review.');
      await _load();
    } on SpinaApiException catch (error) {
      if (mounted) _message(error.message);
    } on Object {
      if (mounted) _message('The renewal handover photo could not be saved.');
    } finally {
      if (mounted) setState(() => _busy.remove(request.requestId));
    }
  }

  Future<void> _run(
    String requestId,
    Future<CollectorRenewalRequest> Function() action, {
    required String successMessage,
  }) async {
    if (_busy.contains(requestId)) return;
    setState(() => _busy.add(requestId));
    try {
      await action();
      if (!mounted) return;
      _message(successMessage);
      await _load();
    } on SpinaApiException catch (error) {
      if (mounted) _message(error.message);
    } on Object {
      if (mounted) _message('The renewal action could not be completed.');
    } finally {
      if (mounted) setState(() => _busy.remove(requestId));
    }
  }

  Future<bool> _confirm({
    required String title,
    required String message,
    required String action,
  }) async {
    return await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: Text(title),
            content: Text(message),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: Text(action),
              ),
            ],
          ),
        ) ??
        false;
  }

  void _message(String value) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(value)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Renewal Requests'),
        actions: [
          IconButton(
            tooltip: 'Refresh renewals',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(12),
          children: [
            const _PolicyCard(),
            const SizedBox(height: 10),
            if (_loading && _requests.isEmpty)
              const Padding(
                padding: EdgeInsets.all(36),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_error != null && _requests.isEmpty)
              _MessageCard(
                icon: Icons.error_outline,
                message: _error!,
                action: TextButton(onPressed: _load, child: const Text('Retry')),
              )
            else if (_requests.isEmpty)
              const _MessageCard(
                icon: Icons.fact_check_outlined,
                message: 'No assigned-client renewal requests need your attention.',
              )
            else
              for (final request in _requests) ...[
                _RenewalCard(
                  request: request,
                  busy: _busy.contains(request.requestId),
                  onRecommend: () => _recommend(request, 'recommend'),
                  onDoNotRecommend: () =>
                      _recommend(request, 'do_not_recommend'),
                  onCashReceived: () => _confirmCashReceived(request),
                  onCashGiven: () => _confirmCashGiven(request),
                  onProof: () => _captureProof(request),
                ),
                const SizedBox(height: 10),
              ],
          ],
        ),
      ),
    );
  }
}

class _PolicyCard extends StatelessWidget {
  const _PolicyCard();

  @override
  Widget build(BuildContext context) {
    return Card(
      color: SpinaTheme.brandPinkSoft,
      child: const Padding(
        padding: EdgeInsets.all(14),
        child: Text(
          'Only the permanently assigned Collector recommends a renewal. Collector never chooses the approved principal. Remote renewal requires every required signer to use their own app and complete identity verification/signing. Cash custody and client confirmation are separate, audited steps.',
        ),
      ),
    );
  }
}

class _RenewalCard extends StatelessWidget {
  const _RenewalCard({
    required this.request,
    required this.busy,
    required this.onRecommend,
    required this.onDoNotRecommend,
    required this.onCashReceived,
    required this.onCashGiven,
    required this.onProof,
  });

  final CollectorRenewalRequest request;
  final bool busy;
  final VoidCallback onRecommend;
  final VoidCallback onDoNotRecommend;
  final VoidCallback onCashReceived;
  final VoidCallback onCashGiven;
  final VoidCallback onProof;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: Key('renewal-request-${request.requestId}'),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        request.clientName,
                        style: Theme.of(context)
                            .textTheme
                            .titleMedium
                            ?.copyWith(fontWeight: FontWeight.w900),
                      ),
                      Text('${request.clientCode} • ${request.area}'),
                    ],
                  ),
                ),
                _StatusPill(request.displayStatus),
              ],
            ),
            const Divider(height: 20),
            Text(
              '${request.isSevenBySeven ? '7x7' : request.loanTypeName} • ${request.loanNumber}',
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
            Text(
              'Current principal ${_money(request.currentPrincipal)} • Remaining ${_money(request.remainingBalance)}',
            ),
            Text(
              'Total contractual ${_money(request.contractualTotal)} • Paid ${request.paidPercent.toStringAsFixed(1)}%',
            ),
            if (!request.isSevenBySeven && !request.regular50PercentEligible)
              const Text(
                'Below normal 50% Regular threshold — only a controlled Management override may approve.',
              ),
            if (request.isSevenBySeven)
              const Text('7x7 request requires Management approval at every paid percentage.'),
            const SizedBox(height: 6),
            Text('Client requested: ${_money(request.requestedAmount)}'),
            if (request.clientMessage.isNotEmpty)
              Text('Client note: ${request.clientMessage}'),
            if (request.needsCollectorRecommendation) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: FilledButton.icon(
                      key: Key('renewal-recommend-${request.requestId}'),
                      onPressed: busy ? null : onRecommend,
                      icon: const Icon(Icons.thumb_up_alt_outlined),
                      label: const Text('Recommend'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: OutlinedButton.icon(
                      key: Key('renewal-do-not-recommend-${request.requestId}'),
                      onPressed: busy ? null : onDoNotRecommend,
                      icon: const Icon(Icons.thumb_down_alt_outlined),
                      label: const Text('Do Not'),
                    ),
                  ),
                ],
              ),
            ] else if (request.collectorRecommendation != null) ...[
              const SizedBox(height: 10),
              Text(
                request.collectorRecommendation == 'recommend'
                    ? 'Collector recommendation: Recommend'
                    : 'Collector recommendation: Do Not Recommend',
                style: const TextStyle(fontWeight: FontWeight.w800),
              ),
              if (request.collectorReasonCode.isNotEmpty)
                Text('Reason: ${request.collectorReasonCode}'),
              if (request.collectorComment.isNotEmpty)
                Text('Comment: ${request.collectorComment}'),
            ],
            if (request.approvedPrincipal != null) ...[
              const Divider(height: 22),
              Text(
                'Management approved principal: ${_money(request.approvedPrincipal!)}',
                style: const TextStyle(fontWeight: FontWeight.w900),
              ),
              if (request.amountLockedAt == null)
                Text(
                  'Estimated net release: ${_money((request.approvedPrincipal! - request.remainingBalance).clamp(0, double.infinity))} before final same-day settlement.',
                )
              else ...[
                Text('Renewal offset: ${_money(request.renewalOffsetAmount ?? 0)}'),
                Text(
                  'LOCKED cash release: ${_money(request.netReleaseAmount ?? 0)}',
                  style: const TextStyle(fontWeight: FontWeight.w900),
                ),
              ],
              if (request.clientDecision == null)
                const Text('Waiting for client: Accept & Continue / Decline.')
              else
                Text('Client decision: ${request.clientDecision}'),
            ],
            if (request.signers.isNotEmpty || request.officeProcessingRequired) ...[
              const Divider(height: 22),
              const Text(
                'Required signers',
                style: TextStyle(fontWeight: FontWeight.w900),
              ),
              if (request.officeProcessingRequired)
                const Text(
                  'OFFICE PROCESSING REQUIRED — at least one required signer cannot complete the remote app flow.',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
              for (final signer in request.signers)
                _SignerRow(signer: signer),
            ],
            if (request.cashReleasedToCollectorAt != null ||
                request.collectorCashReceivedAt != null ||
                request.cashGivenToClientAt != null) ...[
              const Divider(height: 22),
              const Text(
                'Cash custody',
                style: TextStyle(fontWeight: FontWeight.w900),
              ),
              _Step('Management released cash', request.cashReleasedToCollectorAt != null),
              _Step('Collector received cash', request.collectorCashReceivedAt != null),
              _Step('Collector gave cash to client', request.cashGivenToClientAt != null),
              _Step('Client confirmed cash received', request.clientCashConfirmedAt != null),
            ],
            if (request.canConfirmCashReceived) ...[
              const SizedBox(height: 10),
              FilledButton.icon(
                key: Key('renewal-cash-received-${request.requestId}'),
                onPressed: busy ? null : onCashReceived,
                icon: const Icon(Icons.inventory_2_outlined),
                label: Text(
                  'Confirm Cash Received ${_money(request.netReleaseAmount ?? 0)}',
                ),
              ),
            ],
            if (request.canConfirmCashGiven) ...[
              const SizedBox(height: 10),
              FilledButton.icon(
                key: Key('renewal-cash-given-${request.requestId}'),
                onPressed: busy ? null : onCashGiven,
                icon: const Icon(Icons.handshake_outlined),
                label: Text(
                  'Confirm Cash Given ${_money(request.netReleaseAmount ?? 0)}',
                ),
              ),
            ],
            if (request.cashGivenToClientAt != null) ...[
              const SizedBox(height: 10),
              Text(
                'Proof: ${_proofLabel(request.handoverProofStatus)}',
                style: const TextStyle(fontWeight: FontWeight.w800),
              ),
              if (request.needsPhoto)
                OutlinedButton.icon(
                  key: Key('renewal-proof-${request.requestId}'),
                  onPressed: busy ? null : onProof,
                  icon: const Icon(Icons.add_a_photo_outlined),
                  label: Text(
                    request.handoverProofStatus == 'correction_required'
                        ? 'Submit New Handover Photo'
                        : 'Submit Handover Photo',
                  ),
                ),
              if (request.clientCashConfirmedAt == null)
                const Text(
                  'Awaiting Client Confirmation — Collector cannot confirm for the client.',
                ),
            ],
            if (request.activationStatus == 'released_pending_management') ...[
              const SizedBox(height: 8),
              const Text(
                'Released — Pending Management Verification. This new loan must not become collectible until the activation gate is complete.',
              ),
            ],
            if (request.reviewNote.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('Management note: ${request.reviewNote}'),
            ],
            if (busy) ...[
              const SizedBox(height: 8),
              const LinearProgressIndicator(),
            ],
          ],
        ),
      ),
    );
  }
}

class _SignerRow extends StatelessWidget {
  const _SignerRow({required this.signer});

  final CollectorRenewalSigner signer;

  @override
  Widget build(BuildContext context) {
    final checks = <String>[
      signer.hasApp ? 'App ✓' : 'No app',
      signer.governmentIdVerified ? 'ID ✓' : 'ID pending',
      signer.selfieVerified ? 'Selfie ✓' : 'Selfie pending',
      signer.signed ? 'Signed ✓' : 'Signature pending',
    ];
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            signer.ready ? Icons.verified_outlined : Icons.pending_outlined,
            size: 18,
          ),
          const SizedBox(width: 7),
          Expanded(
            child: Text(
              '${_roleLabel(signer.partyRole)}: ${signer.fullName}\n${checks.join(' • ')}',
            ),
          ),
        ],
      ),
    );
  }
}

class _Step extends StatelessWidget {
  const _Step(this.label, this.done);

  final String label;
  final bool done;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Row(
        children: [
          Icon(done ? Icons.check_circle : Icons.radio_button_unchecked, size: 18),
          const SizedBox(width: 7),
          Expanded(child: Text(label)),
        ],
      ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  const _StatusPill(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(maxWidth: 128),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
      decoration: BoxDecoration(
        color: SpinaTheme.brandPinkSoft,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        textAlign: TextAlign.center,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: SpinaTheme.brandPinkDark,
              fontWeight: FontWeight.w900,
            ),
      ),
    );
  }
}

class _MessageCard extends StatelessWidget {
  const _MessageCard({required this.icon, required this.message, this.action});

  final IconData icon;
  final String message;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            Icon(icon, size: 42),
            const SizedBox(height: 8),
            Text(message, textAlign: TextAlign.center),
            if (action != null) action!,
          ],
        ),
      ),
    );
  }
}

class _RecommendationDraft {
  const _RecommendationDraft({required this.reasonCode, required this.comment});

  final String reasonCode;
  final String comment;
}

class _RecommendationDialog extends StatefulWidget {
  const _RecommendationDialog({required this.recommendation});

  final String recommendation;

  @override
  State<_RecommendationDialog> createState() => _RecommendationDialogState();
}

class _RecommendationDialogState extends State<_RecommendationDialog> {
  late String _reason;
  final TextEditingController _comment = TextEditingController();

  List<String> get _reasons => widget.recommendation == 'recommend'
      ? const <String>[
          'Good payment history',
          'Near or fully completed term',
          'Stable field collection pattern',
          'Good client history',
          'Other',
        ]
      : const <String>[
          'Frequent missed payments',
          'Payment capacity concern',
          'Field verification concern',
          'Client conduct concern',
          'Other',
        ];

  @override
  void initState() {
    super.initState();
    _reason = _reasons.first;
  }

  @override
  void dispose() {
    _comment.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final nonRecommend = widget.recommendation == 'do_not_recommend';
    return AlertDialog(
      title: Text(nonRecommend ? 'Do Not Recommend' : 'Recommend Renewal'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          DropdownButtonFormField<String>(
            initialValue: _reason,
            decoration: const InputDecoration(labelText: 'Reason'),
            items: _reasons
                .map((value) => DropdownMenuItem(value: value, child: Text(value)))
                .toList(growable: false),
            onChanged: (value) {
              if (value != null) setState(() => _reason = value);
            },
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _comment,
            maxLines: 3,
            maxLength: 1000,
            decoration: InputDecoration(
              labelText: nonRecommend || _reason == 'Other'
                  ? 'Explanation (required)'
                  : 'Comment (optional)',
            ),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () {
            final comment = _comment.text.trim();
            if ((nonRecommend || _reason == 'Other') && comment.length < 3) {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Add the required explanation.')),
              );
              return;
            }
            Navigator.pop(
              context,
              _RecommendationDraft(reasonCode: _reason, comment: comment),
            );
          },
          child: const Text('Submit'),
        ),
      ],
    );
  }
}

String _money(double value) => '₱${value.toStringAsFixed(2)}';

String _roleLabel(String value) => switch (value) {
      'solidary_co_maker' => 'Solidary co-maker',
      'surety' => 'Surety',
      'guarantor' => 'Guarantor',
      _ => 'Borrower',
    };

String _proofLabel(String value) => switch (value) {
      'under_review' => 'Under Management Review',
      'approved' => 'Approved',
      'correction_required' => 'Correction Required',
      'flagged' => 'Flagged for Review',
      _ => 'Not Submitted',
    };

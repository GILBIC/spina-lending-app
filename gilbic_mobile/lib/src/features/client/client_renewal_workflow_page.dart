import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart'
    show staffAccessRejected;
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/renewals/client_renewal_workflow_repository.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

class ClientRenewalWorkflowPage extends StatefulWidget {
  const ClientRenewalWorkflowPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ClientRenewalWorkflowRepository? repository;

  @override
  State<ClientRenewalWorkflowPage> createState() =>
      _ClientRenewalWorkflowPageState();
}

class _ClientRenewalWorkflowPageState extends State<ClientRenewalWorkflowPage> {
  late ClientRenewalWorkflowRepository _repository;
  List<CollectorRenewalRequest> _requests = const <CollectorRenewalRequest>[];
  String? _deviceId;
  String? _error;
  bool _loading = true;
  final Set<String> _busy = <String>{};

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaClientRenewalWorkflowRepository();
    _load();
  }

  int _epoch = 0;
  int _request = 0;
  bool _denied = false;
  bool _active(int epoch) => mounted && !_denied && epoch == _epoch;
  bool _current(int epoch, int request) =>
      _active(epoch) && request == _request;

  void _clearPrivate() {
    _requests = const [];
    _deviceId = null;
    _busy.clear();
  }

  void _dismissPrivateRoutes() {
    final route = ModalRoute.of(context);
    final navigator = Navigator.of(context);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && route != null && route.isActive && !route.isCurrent) {
        navigator.popUntil((candidate) => candidate == route);
      }
    });
  }

  bool _deny(SpinaApiException error, int epoch) {
    if (!_active(epoch) || !staffAccessRejected(error)) return false;
    _epoch++;
    setState(() {
      _denied = true;
      _clearPrivate();
      _loading = false;
      _error = '${error.message} Sign in again before continuing.';
    });
    _dismissPrivateRoutes();
    return true;
  }

  @override
  void didUpdateWidget(ClientRenewalWorkflowPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    final scopeChanged =
        oldWidget.session.authorizationScopeKey !=
        widget.session.authorizationScopeKey;
    if (scopeChanged ||
        oldWidget.deviceIdentityProvider != widget.deviceIdentityProvider ||
        oldWidget.repository != widget.repository) {
      _epoch++;
      if (scopeChanged) _denied = false;
      _clearPrivate();
      _repository = widget.repository ?? SpinaClientRenewalWorkflowRepository();
      _dismissPrivateRoutes();
      if (!_denied) _load();
    }
  }

  Future<void> _load() async {
    if (_denied) return;
    final epoch = _epoch;
    final request = ++_request;
    final session = widget.session;
    final repository = _repository;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      if (!_current(epoch, request)) return;
      final requests = await repository.list(
        session,
        deviceId: identity.installationId,
      );
      if (!_current(epoch, request)) return;
      setState(() {
        _deviceId = identity.installationId;
        _requests = requests;
      });
    } on SpinaApiException catch (error) {
      if (_deny(error, epoch)) return;
      if (_current(epoch, request)) setState(() => _error = error.message);
    } on Object {
      if (_current(epoch, request)) {
        setState(() => _error = 'Renewal workflow could not be loaded.');
      }
    } finally {
      if (_current(epoch, request)) setState(() => _loading = false);
    }
  }

  Future<void> _decision(
    CollectorRenewalRequest request,
    String decision,
  ) async {
    final epoch = _epoch;
    if (!_active(epoch)) return;
    final session = widget.session;
    final label = decision == 'accepted'
        ? 'Accept & Continue'
        : 'Decline Renewal';
    final confirmed = await _confirm(
      title: label,
      message: decision == 'accepted'
          ? 'You are accepting Management-approved renewal terms. This does not by itself release cash or activate the new loan. Required identity checks and signatures still apply.'
          : 'Declining stops this approved renewal workflow. No new loan will be released from this approval.',
      action: label,
    );
    if (!confirmed || !_active(epoch)) return;
    await _run(
      request.requestId,
      () => _repository.decide(
        session,
        deviceId: _deviceId!,
        requestId: request.requestId,
        decision: decision,
      ),
      decision == 'accepted'
          ? 'Renewal accepted. Complete your required signer steps next.'
          : 'Renewal declined.',
    );
  }

  Future<void> _sign(
    CollectorRenewalRequest request,
    CollectorRenewalSigner signer,
  ) async {
    final epoch = _epoch;
    if (!_active(epoch)) return;
    final session = widget.session;
    if (!signer.governmentIdVerified || !signer.selfieVerified) {
      _message(
        'Government ID and selfie/photo identity verification must be completed before signing.',
      );
      return;
    }
    final confirmed = await _confirm(
      title: 'Sign Renewal',
      message:
          'You are signing this renewal from your own GILBIC account as ${_roleLabel(signer.partyRole)}. Never sign for another person.',
      action: 'Sign',
    );
    if (!confirmed || !_active(epoch)) return;
    await _run(
      request.requestId,
      () => _repository.sign(
        session,
        deviceId: _deviceId!,
        requestId: request.requestId,
        signerId: signer.signerId,
      ),
      'Your renewal signature was recorded.',
    );
  }

  Future<void> _confirmCash(CollectorRenewalRequest request) async {
    final epoch = _epoch;
    if (!_active(epoch)) return;
    final session = widget.session;
    final confirmed = await _confirm(
      title: 'Confirm Cash Received',
      message:
          'Confirm only if you personally received the locked ${_money(request.netReleaseAmount ?? 0)} from the Collector. The Collector cannot confirm this for you.',
      action: 'I Received the Cash',
    );
    if (!confirmed || !_active(epoch)) return;
    await _run(
      request.requestId,
      () => _repository.confirmCashReceived(
        session,
        deviceId: _deviceId!,
        requestId: request.requestId,
      ),
      'Cash receipt confirmed.',
    );
  }

  Future<void> _run(
    String requestId,
    Future<Object> Function() action,
    String successMessage,
  ) async {
    final epoch = _epoch;
    if (!_active(epoch)) return;
    final deviceId = _deviceId;
    if (deviceId == null || _busy.contains(requestId)) return;
    setState(() => _busy.add(requestId));
    try {
      await action();
      if (!_active(epoch)) return;
      _message(successMessage);
      await _load();
    } on SpinaApiException catch (error) {
      if (_deny(error, epoch)) return;
      if (_active(epoch)) _message(error.message);
    } on Object {
      if (_active(epoch)) {
        _message('The renewal action could not be completed.');
      }
    } finally {
      if (_active(epoch)) setState(() => _busy.remove(requestId));
    }
  }

  Future<bool> _confirm({
    required String title,
    required String message,
    required String action,
  }) async {
    final epoch = _epoch;
    if (!_active(epoch)) return false;
    final confirmed =
        await showDialog<bool>(
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
    return _active(epoch) && confirmed;
  }

  void _message(String value) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(value)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Renewal Progress'),
        actions: [
          IconButton(
            tooltip: 'Refresh renewal progress',
            onPressed: _loading || _denied ? null : _load,
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
            Card(
              color: SpinaTheme.brandPinkSoft,
              child: const Padding(
                padding: EdgeInsets.all(14),
                child: Text(
                  'Approval is not the same as release. Review the approved principal, accept or decline yourself, complete only your own identity/signature step, and independently confirm cash only after you actually receive it. Any other required signer must use their own SPINA account.',
                ),
              ),
            ),
            const SizedBox(height: 10),
            if (_loading && _requests.isEmpty)
              const Padding(
                padding: EdgeInsets.all(36),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_error != null && _requests.isEmpty)
              _MessageCard(message: _error!, onRetry: _denied ? null : _load)
            else if (_requests.isEmpty)
              const _MessageCard(
                message: 'You do not have an active renewal workflow.',
              )
            else
              for (final request in _requests) ...[
                _ClientRenewalCard(
                  request: request,
                  busy: _busy.contains(request.requestId),
                  onAccept: () => _decision(request, 'accepted'),
                  onDecline: () => _decision(request, 'declined'),
                  onSign: (signer) => _sign(request, signer),
                  onCashConfirm: () => _confirmCash(request),
                ),
                const SizedBox(height: 10),
              ],
          ],
        ),
      ),
    );
  }
}

class _ClientRenewalCard extends StatelessWidget {
  const _ClientRenewalCard({
    required this.request,
    required this.busy,
    required this.onAccept,
    required this.onDecline,
    required this.onSign,
    required this.onCashConfirm,
  });

  final CollectorRenewalRequest request;
  final bool busy;
  final VoidCallback onAccept;
  final VoidCallback onDecline;
  final void Function(CollectorRenewalSigner signer) onSign;
  final VoidCallback onCashConfirm;

  @override
  Widget build(BuildContext context) {
    final borrowerSigner = _borrowerSigner(request);
    return Card(
      key: Key('client-renewal-workflow-${request.requestId}'),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    '${request.isSevenBySeven ? '7x7' : request.loanTypeName} Renewal',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
                _StatusPill(request.displayStatus),
              ],
            ),
            Text(request.loanNumber),
            const Divider(height: 20),
            Text('Current balance ${_money(request.remainingBalance)}'),
            Text('Requested ${_money(request.requestedAmount)}'),
            if (request.approvedPrincipal != null) ...[
              const SizedBox(height: 8),
              Text(
                'Management approved ${_money(request.approvedPrincipal!)}',
                style: const TextStyle(fontWeight: FontWeight.w900),
              ),
              if (request.amountLockedAt == null)
                const Text('Final net cash is not locked yet.')
              else ...[
                Text(
                  'Old-loan settlement ${_money(request.renewalOffsetAmount ?? 0)}',
                ),
                Text(
                  'Locked net cash ${_money(request.netReleaseAmount ?? 0)}',
                  style: const TextStyle(fontWeight: FontWeight.w900),
                ),
              ],
            ],
            if (request.status == 'approved' &&
                request.clientDecision == null) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: FilledButton(
                      key: Key('client-renewal-accept-${request.requestId}'),
                      onPressed: busy ? null : onAccept,
                      child: const Text('Accept & Continue'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: OutlinedButton(
                      key: Key('client-renewal-decline-${request.requestId}'),
                      onPressed: busy ? null : onDecline,
                      child: const Text('Decline'),
                    ),
                  ),
                ],
              ),
            ],
            if (request.clientDecision == 'accepted') ...[
              const Divider(height: 22),
              const Text(
                'Your signer step',
                style: TextStyle(fontWeight: FontWeight.w900),
              ),
              if (request.officeProcessingRequired)
                const Text(
                  'Office Processing Required — remote signature is disabled for this renewal.',
                  style: TextStyle(fontWeight: FontWeight.w800),
                )
              else if (borrowerSigner == null)
                const Text(
                  'Waiting for Management to register your borrower signer requirement.',
                )
              else ...[
                _SignerState(signer: borrowerSigner),
                if (!borrowerSigner.signed)
                  FilledButton.icon(
                    key: Key('client-renewal-sign-${request.requestId}'),
                    onPressed:
                        busy ||
                            !borrowerSigner.governmentIdVerified ||
                            !borrowerSigner.selfieVerified
                        ? null
                        : () => onSign(borrowerSigner),
                    icon: const Icon(Icons.draw_outlined),
                    label: const Text('Sign Renewal'),
                  ),
              ],
            ],
            if (request.cashGivenToClientAt != null &&
                request.clientCashConfirmedAt == null) ...[
              const Divider(height: 22),
              Text(
                'Collector marked ${_money(request.netReleaseAmount ?? 0)} as given to you.',
              ),
              FilledButton.icon(
                key: Key('client-renewal-cash-confirm-${request.requestId}'),
                onPressed: busy ? null : onCashConfirm,
                icon: const Icon(Icons.payments_outlined),
                label: const Text('I Received the Cash'),
              ),
              const Text(
                'Press only after you personally receive the cash. The Collector cannot do this confirmation for you.',
              ),
            ],
            if (request.clientCashConfirmedAt != null) ...[
              const Divider(height: 22),
              const Text(
                'Cash received: Confirmed by you',
                style: TextStyle(fontWeight: FontWeight.w900),
              ),
              Text(
                'Handover proof: ${_proofLabel(request.handoverProofStatus)}',
              ),
              Text('Activation: ${_activationLabel(request.activationStatus)}'),
              if (request.activationStatus != 'active')
                const Text(
                  'Your renewed loan is not collectible yet while Management verification remains pending.',
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

class _SignerState extends StatelessWidget {
  const _SignerState({required this.signer});

  final CollectorRenewalSigner signer;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Text(
        'Own app ${signer.hasApp ? '✓' : '—'} • Government ID ${signer.governmentIdVerified ? '✓' : 'Pending'} • Selfie ${signer.selfieVerified ? '✓' : 'Pending'} • Signature ${signer.signed ? '✓' : 'Pending'}',
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
      constraints: const BoxConstraints(maxWidth: 140),
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
  const _MessageCard({required this.message, this.onRetry});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            Text(message, textAlign: TextAlign.center),
            if (onRetry != null)
              TextButton(onPressed: onRetry, child: const Text('Retry')),
          ],
        ),
      ),
    );
  }
}

CollectorRenewalSigner? _borrowerSigner(CollectorRenewalRequest request) {
  for (final signer in request.signers) {
    if (signer.partyRole == 'borrower') return signer;
  }
  return null;
}

String _money(num value) => '₱${value.toStringAsFixed(2)}';

String _roleLabel(String value) => switch (value) {
  'guarantor' => 'Guarantor',
  'surety' => 'Surety',
  'solidary_co_maker' => 'Solidary co-maker',
  _ => 'Borrower',
};

String _proofLabel(String value) => switch (value) {
  'approved' => 'Approved',
  'under_review' => 'Under Management Review',
  'correction_required' => 'Proof Correction Required',
  'flagged' => 'Flagged for Review',
  _ => 'Not Submitted',
};

String _activationLabel(String value) => switch (value) {
  'active' => 'Active',
  'released_pending_management' => 'Released — Pending Management Verification',
  _ => 'Not Activated',
};

import 'dart:math';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/media/image_recovery_controller.dart';
import 'package:gilbic_mobile/src/features/shared/image_recovery_scope.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_saver.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/client_payment_proof_repository.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_photo.dart';
import 'package:gilbic_mobile/src/features/client/client_document_download_button.dart';
import 'package:image_picker/image_picker.dart';

const _proofNotice =
    'Payment proof is evidence for SPINA review. Uploading, correcting, or reviewing it does not post a payment or change your balance. Check Payments for official posted transactions.';

class ClientPaymentProofsPage extends StatefulWidget {
  const ClientPaymentProofsPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.loanRepository,
    this.imagePicker,
    this.saver = saveClientDocument,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ClientPaymentProofRepository? repository;
  final ClientLoanRepository? loanRepository;
  final ImagePicker? imagePicker;
  final ClientDocumentSaver saver;
  @override
  State<ClientPaymentProofsPage> createState() =>
      _ClientPaymentProofsPageState();
}

class _ClientPaymentProofsPageState extends State<ClientPaymentProofsPage> {
  late final ClientPaymentProofRepository _repository;
  PaymentProofList? _result;
  final List<ClientPaymentProof> _proofs = [];
  String? _error;
  bool _loading = true;
  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaClientPaymentProofRepository();
    _load();
  }

  Future<void> _load({bool more = false}) async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final result = await _repository.list(
        widget.session,
        deviceId: identity.installationId,
        offset: more ? _proofs.length : 0,
      );
      if (mounted) {
        setState(() {
          _result = result;
          if (!more) _proofs.clear();
          _proofs.addAll(result.proofs);
        });
      }
    } on SpinaApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) {
        setState(() => _error = 'Payment proofs could not be loaded.');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _create() async {
    final capability = _result;
    if (capability == null || !capability.uploadAvailable) return;
    final submitted = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => ClientPaymentProofUploadPage(
          session: widget.session,
          deviceIdentityProvider: widget.deviceIdentityProvider,
          repository: _repository,
          capability: capability,
          loanRepository: widget.loanRepository,
          imagePicker: widget.imagePicker,
        ),
      ),
    );
    if (mounted && submitted == true) await _load();
  }

  Future<void> _open(ClientPaymentProof proof) async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => ClientPaymentProofDetailPage(
          session: widget.session,
          deviceIdentityProvider: widget.deviceIdentityProvider,
          proofId: proof.proofId,
          repository: _repository,
          capability: _result!,
          imagePicker: widget.imagePicker,
          saver: widget.saver,
        ),
      ),
    );
    if (mounted) await _load();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Payment proofs'),
      actions: [
        IconButton(
          tooltip: 'Refresh proofs',
          onPressed: _loading ? null : _load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: _loading && _result == null
        ? const Center(child: CircularProgressIndicator())
        : RefreshIndicator(
            onRefresh: _load,
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(16),
              children: [
                const Text(_proofNotice),
                const SizedBox(height: 12),
                if (_error != null) ...[
                  Text(_error!),
                  OutlinedButton(
                    onPressed: _loading ? null : _load,
                    child: const Text('Try again'),
                  ),
                ],
                if (_result != null) ...[
                  Text(_result!.message),
                  if (_result!.uploadAvailable)
                    Align(
                      alignment: Alignment.centerLeft,
                      child: FilledButton.icon(
                        key: const Key('new-payment-proof'),
                        onPressed: _loading ? null : _create,
                        icon: const Icon(Icons.upload_file),
                        label: const Text('Upload payment proof'),
                      ),
                    ),
                  const SizedBox(height: 12),
                  if (_proofs.isEmpty)
                    const Text('No payment proof has been submitted yet.'),
                  for (final proof in _proofs)
                    Card(
                      child: ListTile(
                        key: Key('payment-proof-${proof.proofId}'),
                        title: Text(
                          '${proof.loanNumber} · ${proof.loanTypeName}',
                        ),
                        subtitle: Text(
                          '${paymentProofStatusLabel(proof.status)} · Version ${proof.currentVersion.versionNumber}${proof.latestReview?.reason.isNotEmpty == true ? '\n${proof.latestReview!.reason}' : ''}',
                        ),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => _open(proof),
                      ),
                    ),
                  if (_result!.hasMore)
                    OutlinedButton(
                      onPressed: _loading ? null : () => _load(more: true),
                      child: const Text('Load more proofs'),
                    ),
                ],
                if (_loading) const LinearProgressIndicator(),
              ],
            ),
          ),
  );
}

class ClientPaymentProofDetailPage extends StatefulWidget {
  const ClientPaymentProofDetailPage({
    required this.session,
    required this.deviceIdentityProvider,
    required this.proofId,
    required this.repository,
    required this.capability,
    this.imagePicker,
    this.saver = saveClientDocument,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final String proofId;
  final ClientPaymentProofRepository repository;
  final PaymentProofList capability;
  final ImagePicker? imagePicker;
  final ClientDocumentSaver saver;
  @override
  State<ClientPaymentProofDetailPage> createState() =>
      _ClientPaymentProofDetailPageState();
}

class _ClientPaymentProofDetailPageState
    extends State<ClientPaymentProofDetailPage> {
  PaymentProofDetail? _detail;
  String? _error;
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
      final identity = await widget.deviceIdentityProvider.load();
      final detail = await widget.repository.load(
        widget.session,
        deviceId: identity.installationId,
        proofId: widget.proofId,
      );
      if (mounted) setState(() => _detail = detail);
    } on SpinaApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) {
        setState(() => _error = 'Payment proof history could not be loaded.');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _correct() async {
    final submitted = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => ClientPaymentProofUploadPage(
          session: widget.session,
          deviceIdentityProvider: widget.deviceIdentityProvider,
          repository: widget.repository,
          capability: widget.capability,
          proof: _detail!.proof,
          imagePicker: widget.imagePicker,
        ),
      ),
    );
    if (mounted && submitted == true) await _load();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Proof status and history'),
      actions: [
        IconButton(
          onPressed: _loading ? null : _load,
          tooltip: 'Refresh proof',
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: _loading
        ? const Center(child: CircularProgressIndicator())
        : ListView(
            padding: const EdgeInsets.all(16),
            children: [
              const Text(_proofNotice),
              const SizedBox(height: 12),
              if (_error != null) ...[
                Text(_error!),
                OutlinedButton(
                  onPressed: _load,
                  child: const Text('Try again'),
                ),
              ],
              if (_detail != null) ...[
                Text(
                  _detail!.proof.loanNumber,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                Text(paymentProofStatusLabel(_detail!.proof.status)),
                if (_detail!.proof.latestReview != null)
                  Text(_detail!.proof.latestReview!.reason),
                if (widget.capability.uploadAvailable &&
                    _detail!.proof.canReupload)
                  Align(
                    alignment: Alignment.centerLeft,
                    child: FilledButton.icon(
                      key: const Key('correct-payment-proof'),
                      onPressed: _error == null ? _correct : null,
                      icon: const Icon(Icons.upload_file),
                      label: const Text('Upload corrected proof'),
                    ),
                  ),
                const SizedBox(height: 16),
                Text(
                  'Version history',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                for (final entry in _detail!.history)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Version ${entry.version.versionNumber}',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          Text('Uploaded: ${entry.version.uploadedAt}'),
                          if (entry.version.note?.isNotEmpty == true)
                            Text(entry.version.note!),
                          for (final review in entry.reviews)
                            Padding(
                              padding: const EdgeInsets.only(top: 8),
                              child: Text(
                                '${paymentProofStatusLabel(review.decision)}\n${review.reason}\n${review.reviewedAt}',
                              ),
                            ),
                          ClientDocumentDownloadButton(
                            label:
                                'Download proof version ${entry.version.versionNumber}',
                            saver: widget.saver,
                            load: () async {
                              final identity = await widget
                                  .deviceIdentityProvider
                                  .load();
                              return widget.repository.download(
                                widget.session,
                                deviceId: identity.installationId,
                                proofId: widget.proofId,
                                version: entry.version,
                              );
                            },
                          ),
                        ],
                      ),
                    ),
                  ),
              ],
            ],
          ),
  );
}

class ClientPaymentProofUploadPage extends StatefulWidget {
  const ClientPaymentProofUploadPage({
    required this.session,
    required this.deviceIdentityProvider,
    required this.repository,
    required this.capability,
    this.proof,
    this.loanRepository,
    this.imagePicker,
    this.requestIdGenerator,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ClientPaymentProofRepository repository;
  final PaymentProofList capability;
  final ClientPaymentProof? proof;
  final ClientLoanRepository? loanRepository;
  final ImagePicker? imagePicker;
  final String Function()? requestIdGenerator;
  @override
  State<ClientPaymentProofUploadPage> createState() =>
      _ClientPaymentProofUploadPageState();
}

class _ClientPaymentProofUploadPageState
    extends State<ClientPaymentProofUploadPage> {
  final _note = TextEditingController();
  List<ClientLoan> _loans = [];
  String? _loanId;
  String? _error;
  PaymentProofDraft? _draft;
  String? _requestId;
  bool _loading = false;
  bool _busy = false;
  bool _uncertain = false;
  bool _conflict = false;
  @override
  void initState() {
    super.initState();
    _loanId = widget.proof?.loanId;
    if (widget.proof == null) _loadLoans();
  }

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  Future<void> _loadLoans() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final portfolio =
          await (widget.loanRepository ?? SpinaClientLoanRepository())
              .loadPortfolio(widget.session, deviceId: identity.installationId);
      if (mounted) {
        setState(() {
          _loans = [...portfolio.activeLoans, ...portfolio.previousLoans];
          if (_loans.length == 1) _loanId = _loans.single.loanId;
        });
      }
    } on SpinaApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) setState(() => _error = 'Your loans could not be loaded.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _pick(ImageSource source) async {
    if (_busy || _uncertain || _conflict) return;
    final loanId = _loanId;
    if (loanId == null) {
      setState(() => _error = 'Choose the loan before selecting a photo.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final proof = widget.proof;
      final file = await pickRecoverableImage(
        context,
        recoveryContext: ImagePickContext(
          purpose: 'client_payment_proof',
          target: jsonEncode({
            'loan_id': loanId,
            'proof_id': proof?.proofId,
            'version': proof?.currentVersion.versionNumber,
          }),
          label: proof == null ? 'Payment proof' : 'Correct payment proof',
        ),
        pick: () => (widget.imagePicker ?? ImagePicker()).pickImage(
          source: source,
          requestFullMetadata: false,
        ),
      );
      if (file == null || !mounted) return;
      if (await file.length() > widget.capability.maxBytes) {
        throw const SpinaApiException(
          'The image exceeds the upload size allowed by SPINA.',
        );
      }
      final bytes = await file.readAsBytes();
      final type = RemittancePhotoDraft.detectContentType(bytes);
      if (bytes.isEmpty ||
          type == null ||
          !widget.capability.allowedMediaTypes.contains(type)) {
        throw const SpinaApiException('Choose a supported JPEG or PNG image.');
      }
      if (mounted) {
        setState(() {
          _draft = PaymentProofDraft(
            filename: file.name,
            mediaType: type,
            bytes: bytes,
          );
          _requestId = null;
        });
      }
    } on SpinaApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) {
        setState(
          () => _error = 'The image could not be opened. Try another photo.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _submit() async {
    final draft = _draft;
    final loanId = _loanId;
    if (_busy ||
        _conflict ||
        draft == null ||
        loanId == null ||
        !widget.capability.uploadAvailable) {
      return;
    }
    _requestId ??= (widget.requestIdGenerator ?? _newRequestId)();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final proof = widget.proof;
      if (proof == null) {
        await widget.repository.upload(
          widget.session,
          deviceId: identity.installationId,
          loanId: loanId,
          requestId: _requestId!,
          note: _note.text.trim(),
          draft: draft,
        );
      } else {
        await widget.repository.reupload(
          widget.session,
          deviceId: identity.installationId,
          proofId: proof.proofId,
          requestId: _requestId!,
          expectedVersion: proof.currentVersion.versionNumber,
          note: _note.text.trim(),
          draft: draft,
        );
      }
      if (mounted) Navigator.of(context).pop(true);
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() {
          _error = error.message;
          _uncertain = error.statusCode == null || error.statusCode! >= 500;
          _conflict = error.statusCode == 409;
          if (!_uncertain) _requestId = null;
        });
      }
    } on Object {
      if (mounted) {
        setState(() {
          _uncertain = true;
          _error =
              'The upload result could not be confirmed. Retry this same upload before making changes.';
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final locked = _busy || _uncertain || _conflict;
    return PopScope(
      canPop: !_busy,
      child: Scaffold(
        appBar: AppBar(
          title: Text(
            widget.proof == null
                ? 'Upload payment proof'
                : 'Correct payment proof',
          ),
        ),
        body: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const Text(_proofNotice),
            const SizedBox(height: 16),
            if (!widget.capability.uploadAvailable)
              Text(widget.capability.message)
            else ...[
              if (_loading) const LinearProgressIndicator(),
              if (widget.proof != null)
                Text('Loan: ${widget.proof!.loanNumber}')
              else if (!_loading && _loans.isEmpty) ...[
                const Text('No loan is available for a payment proof.'),
                OutlinedButton(
                  onPressed: _loadLoans,
                  child: const Text('Reload loans'),
                ),
              ] else
                DropdownButtonFormField<String>(
                  key: const Key('proof-loan'),
                  initialValue: _loanId,
                  decoration: const InputDecoration(labelText: 'Loan'),
                  isExpanded: true,
                  items: _loans
                      .map(
                        (loan) => DropdownMenuItem(
                          value: loan.loanId,
                          child: Text(
                            '${loan.loanNumber} · ${loan.loanTypeName}',
                          ),
                        ),
                      )
                      .toList(),
                  onChanged: locked
                      ? null
                      : (value) => setState(() {
                          _loanId = value;
                          _requestId = null;
                        }),
                ),
              const SizedBox(height: 12),
              TextField(
                key: const Key('proof-note'),
                controller: _note,
                enabled: !locked,
                maxLength: 1000,
                maxLines: 3,
                decoration: const InputDecoration(
                  labelText: 'Note or correction (optional)',
                  helperText:
                      'Include details that help SPINA identify your payment.',
                ),
                onChanged: (_) => _requestId = null,
              ),
              Wrap(
                spacing: 8,
                children: [
                  OutlinedButton.icon(
                    key: const Key('proof-gallery'),
                    onPressed: locked ? null : () => _pick(ImageSource.gallery),
                    icon: const Icon(Icons.photo_library_outlined),
                    label: const Text('Choose image'),
                  ),
                  OutlinedButton.icon(
                    onPressed: locked ? null : () => _pick(ImageSource.camera),
                    icon: const Icon(Icons.camera_alt_outlined),
                    label: const Text('Take photo'),
                  ),
                ],
              ),
              if (_draft != null) Text('Selected: ${_draft!.filename}'),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              if (_uncertain)
                const Text(
                  'The same file, note, loan and request will be retried to avoid duplicate proof versions. If you leave, refresh the proof list before starting another upload.',
                ),
              if (_conflict)
                const Text(
                  'Return to the proof list and refresh the latest version before correcting it again.',
                ),
              const SizedBox(height: 12),
              FilledButton.icon(
                key: const Key('submit-payment-proof'),
                onPressed:
                    _busy ||
                        _loading ||
                        _conflict ||
                        _draft == null ||
                        _loanId == null
                    ? null
                    : _submit,
                icon: _busy
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.upload),
                label: Text(
                  _uncertain
                      ? 'Retry same upload'
                      : widget.proof == null
                      ? 'Submit proof for review'
                      : 'Submit corrected proof',
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

String _newRequestId() {
  final random = Random.secure();
  final bytes = List<int>.generate(16, (_) => random.nextInt(256));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  final hex = bytes
      .map((value) => value.toRadixString(16).padLeft(2, '0'))
      .join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
}

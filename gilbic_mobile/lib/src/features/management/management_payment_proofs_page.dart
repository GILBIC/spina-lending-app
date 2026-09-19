import 'dart:math';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_saver.dart';
import 'package:gilbic_mobile/src/core/management/management_payment_proof_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/client_payment_proof_repository.dart'
    show paymentProofStatusLabel;
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

class ManagementPaymentProofsPage extends StatefulWidget {
  const ManagementPaymentProofsPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.saver = saveClientDocument,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ManagementPaymentProofRepository? repository;
  final ClientDocumentSaver saver;
  @override
  State<ManagementPaymentProofsPage> createState() =>
      _ManagementPaymentProofsPageState();
}

class _ManagementPaymentProofsPageState
    extends State<ManagementPaymentProofsPage> {
  late final ManagementPaymentProofRepository _repository;
  final _reason = TextEditingController();
  final _proofs = <ManagementPaymentProof>[];
  ManagementProofDetail? _detail;
  ManagementProofReviewAttempt? _attempt;
  String _decision = 'reviewed';
  String? _message;
  bool _busy = false;
  bool _confirming = false;
  bool _hasMore = false;
  int _offset = 0;
  int _generation = 0;
  bool get _authorized =>
      widget.session.role == AppRole.management &&
      widget.session.hasPermission('client_payment_proof.review');

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaManagementPaymentProofRepository();
    if (_authorized) _load();
  }

  @override
  void dispose() {
    _generation++;
    _reason.dispose();
    super.dispose();
  }

  Future<String> _device() async =>
      (await widget.deviceIdentityProvider.load()).installationId;

  void _error(Object error) {
    if (!mounted) return;
    setState(() {
      _message = error is SpinaApiException
          ? error.message
          : 'The result could not be confirmed. Refresh or retry the same review.';
      if (error is SpinaApiException &&
          [401, 403, 426].contains(error.statusCode)) {
        _generation++;
        _proofs.clear();
        _detail = null;
        _attempt = null;
        _hasMore = false;
        _offset = 0;
        _reason.clear();
      }
    });
  }

  Future<void> _load({bool more = false}) async {
    if (_busy || _attempt != null || !_authorized) return;
    final generation = ++_generation;
    setState(() {
      _busy = true;
      _message = null;
      if (!more) _detail = null;
    });
    try {
      final page = await _repository.list(
        widget.session,
        deviceId: await _device(),
        offset: more ? _offset : 0,
      );
      if (!mounted || generation != _generation) return;
      setState(() {
        if (!more) {
          _proofs.clear();
          _offset = 0;
        }
        _offset += page.proofs.length;
        for (final proof in page.proofs) {
          final index = _proofs.indexWhere(
            (item) => item.proofId == proof.proofId,
          );
          if (index < 0) {
            _proofs.add(proof);
          } else {
            _proofs[index] = proof;
          }
        }
        _hasMore = page.hasMore;
      });
    } on Object catch (error) {
      if (generation == _generation) _error(error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _open(ManagementPaymentProof proof) async {
    if (_busy || _attempt != null) return;
    final generation = ++_generation;
    setState(() {
      _busy = true;
      _detail = null;
      _message = null;
      _reason.clear();
      _decision = 'reviewed';
    });
    try {
      final detail = await _repository.load(
        widget.session,
        deviceId: await _device(),
        proofId: proof.proofId,
      );
      if (mounted && generation == _generation) {
        setState(() => _detail = detail);
      }
    } on Object catch (error) {
      if (generation == _generation) _error(error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _download(ManagementProofVersion version) async {
    final detail = _detail;
    if (_busy || detail == null) return;
    final generation = _generation;
    setState(() => _busy = true);
    try {
      final file = await _repository.download(
        widget.session,
        deviceId: await _device(),
        proofId: detail.proof.proofId,
        version: version,
      );
      if (!mounted || generation != _generation) return;
      final saved = await widget.saver(file);
      if (mounted && generation == _generation && saved) {
        setState(() => _message = 'Evidence file saved.');
      }
    } on Object catch (error) {
      if (generation == _generation) _error(error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _submit() async {
    final detail = _detail;
    if (_busy || detail == null || !_authorized) return;
    if (_attempt == null) {
      final reason = _reason.text.trim();
      if ((_decision != 'reviewed' && reason.isEmpty) || reason.length > 1000) {
        setState(
          () => _message =
              'Enter a reason of at most 1000 characters for correction or rejection.',
        );
        return;
      }
      final proof = detail.proof;
      final decision = _decision;
      final generation = _generation;
      setState(() {
        _busy = true;
        _confirming = true;
      });
      late final bool confirmed;
      try {
        confirmed = await showManagementReviewConfirmation(
          context,
          ManagementReviewPresentation.validated(
            binding: ManagementMutationBinding.paymentProof,
            recordLabel: 'Borrower',
            recordValue: '${proof.clientName} • ${proof.clientCode}',
            statusLabel: paymentProofStatusLabel(proof.status),
            facts: [
              ManagementReviewFact(
                label: 'Loan',
                value: '${proof.loanNumber} • ${proof.loanTypeName}',
              ),
              ManagementReviewFact(
                label: 'Evidence version',
                value: '${proof.currentVersion.number}',
              ),
              ManagementReviewFact(
                label: 'Decision',
                value: paymentProofStatusLabel(decision),
              ),
              if (reason.isNotEmpty)
                ManagementReviewFact(label: 'Reason', value: reason),
            ],
            nextActionLabel: 'Record evidence review',
            consequence:
                'Only the review of this evidence version will be recorded. No payment will be posted and no official balance will change.',
          ),
        );
      } finally {
        if (mounted) {
          setState(() {
            _busy = false;
            _confirming = false;
          });
        }
      }
      if (!mounted ||
          !confirmed ||
          generation != _generation ||
          !identical(detail, _detail) ||
          _attempt != null) {
        return;
      }
      _attempt = ManagementProofReviewAttempt(
        proofId: proof.proofId,
        requestId: _requestId(),
        expectedVersion: proof.currentVersion.number,
        expectedReviewId: proof.latestReview?.reviewId,
        decision: decision,
        reason: reason,
      );
    }
    final generation = _generation;
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      final result = await _repository.review(
        widget.session,
        deviceId: await _device(),
        attempt: _attempt!,
      );
      if (!mounted || generation != _generation) return;
      setState(() {
        _detail = result;
        _attempt = null;
        _reason.clear();
        final index = _proofs.indexWhere(
          (proof) => proof.proofId == result.proof.proofId,
        );
        if (index >= 0) _proofs[index] = result.proof;
        _message = 'Evidence review saved. No payment was posted.';
      });
    } on Object catch (error) {
      if (!mounted || generation != _generation) return;
      _error(error);
      if (error is SpinaApiException && error.statusCode == 409) {
        setState(() {
          _attempt = null;
          _detail = null;
          _reason.clear();
          _message =
              'The evidence changed. Open it again and review the latest version before recording another decision.';
        });
      } else if (error is SpinaApiException &&
          error.statusCode != null &&
          error.statusCode! < 500) {
        setState(() => _attempt = null);
      } else if (_attempt != null) {
        setState(
          () => _message =
              'The review result is uncertain. Retry the same review to confirm it safely.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Payment evidence review'),
      actions: [
        IconButton(
          tooltip: 'Refresh payment evidence',
          onPressed: _busy || _attempt != null || !_authorized ? null : _load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: SafeArea(
      child: !_authorized
          ? const Center(
              child: Text('Payment evidence review permission is required.'),
            )
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                const Text(
                  'Payment proof is evidence for review. Reviewing it never posts a payment or changes an official balance.',
                ),
                if (_message != null)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    child: Text(_message!, semanticsLabel: _message),
                  ),
                if (_busy && !_confirming) const LinearProgressIndicator(),
                if (!_busy && _proofs.isEmpty)
                  const Padding(
                    padding: EdgeInsets.all(16),
                    child: Text('No payment evidence is available.'),
                  ),
                for (final proof in _proofs)
                  Card(
                    child: ListTile(
                      key: Key('management-proof-${proof.proofId}'),
                      title: Text('${proof.clientName} • ${proof.clientCode}'),
                      subtitle: Text(
                        '${proof.loanNumber} • ${proof.loanTypeName}\n${paymentProofStatusLabel(proof.status)} • Version ${proof.currentVersion.number}',
                      ),
                      isThreeLine: true,
                      onTap: _busy || _attempt != null
                          ? null
                          : () => _open(proof),
                    ),
                  ),
                if (_hasMore)
                  TextButton(
                    key: const Key('more-management-proofs'),
                    onPressed: _busy || _attempt != null
                        ? null
                        : () => _load(more: true),
                    child: const Text('Load more evidence'),
                  ),
                if (_detail case final detail?) ...[
                  const Divider(height: 28),
                  Text(
                    '${detail.proof.clientName} — ${detail.proof.loanNumber}',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  Text(paymentProofStatusLabel(detail.proof.status)),
                  for (final entry in detail.history)
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Version ${entry.version.number}',
                              style: Theme.of(context).textTheme.titleMedium,
                            ),
                            Text('Uploaded ${entry.version.uploadedAt}'),
                            if (entry.version.note.isNotEmpty)
                              Text(entry.version.note),
                            OutlinedButton.icon(
                              key: Key(
                                'download-management-proof-${entry.version.number}',
                              ),
                              onPressed: _busy
                                  ? null
                                  : () => _download(entry.version),
                              icon: const Icon(Icons.download_outlined),
                              label: const Text('Download submitted evidence'),
                            ),
                            if (entry.reviews.isEmpty)
                              const Text(
                                'No review recorded for this version.',
                              ),
                            for (final review in entry.reviews) ...[
                              Text(
                                '${paymentProofStatusLabel(review.decision)} • ${review.reviewedAt}',
                              ),
                              if (review.reason.isNotEmpty) Text(review.reason),
                            ],
                          ],
                        ),
                      ),
                    ),
                  DropdownButtonFormField<String>(
                    key: const Key('management-proof-decision'),
                    initialValue: _decision,
                    decoration: const InputDecoration(
                      labelText: 'Review decision',
                    ),
                    items: managementProofDecisions
                        .map(
                          (decision) => DropdownMenuItem(
                            value: decision,
                            child: Text(paymentProofStatusLabel(decision)),
                          ),
                        )
                        .toList(),
                    onChanged: _busy || _attempt != null
                        ? null
                        : (value) {
                            if (value != null) {
                              setState(() => _decision = value);
                            }
                          },
                  ),
                  TextField(
                    key: const Key('management-proof-reason'),
                    controller: _reason,
                    enabled: !_busy && _attempt == null,
                    maxLength: 1000,
                    maxLines: 3,
                    decoration: const InputDecoration(
                      labelText:
                          'Reason (required for correction or rejection)',
                    ),
                  ),
                  FilledButton(
                    key: const Key('submit-management-proof-review'),
                    onPressed: _busy ? null : _submit,
                    child: Text(
                      _attempt != null
                          ? 'Retry same review'
                          : 'Review decision',
                    ),
                  ),
                ],
              ],
            ),
    ),
  );
}

String _requestId() {
  final random = Random.secure();
  final bytes = List<int>.generate(16, (_) => random.nextInt(256));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  final hex = bytes
      .map((value) => value.toRadixString(16).padLeft(2, '0'))
      .join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
}

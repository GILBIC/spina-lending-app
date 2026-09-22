import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/media/image_recovery_controller.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/office/office_repository.dart';
import 'package:gilbic_mobile/src/features/office/office_widgets.dart';

class OfficeReviewCapturePage extends StatefulWidget {
  const OfficeReviewCapturePage({
    required this.actor,
    required this.repository,
    required this.clientId,
    required this.source,
    this.privacy = false,
    this.picker,
    super.key,
  });
  final OfficeIdentity actor;
  final OfficeRepository repository;
  final String clientId;
  final OfficeRecord source;
  final bool privacy;
  final OfficePhotoPicker? picker;
  @override
  State<OfficeReviewCapturePage> createState() =>
      _OfficeReviewCapturePageState();
}

class _OfficeReviewCapturePageState
    extends OfficeScreenState<OfficeReviewCapturePage> {
  OfficeRecord? review;
  OfficeRecord? captured;
  OfficePhoto? photo;
  bool optional = false;
  bool witnessed = false;
  String requestId = officeRequestId();
  int selection = 0;
  _CaptureAttempt? attempt;
  bool get recovering =>
      attempt != null && operation.blocked && operation.lastStatus != 409;
  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void clearPrivate() {
    review = null;
    captured = null;
    photo = null;
    attempt = null;
    witnessed = false;
    optional = false;
    selection++;
  }

  @override
  void dispose() {
    clearPrivate();
    super.dispose();
  }

  Future<void> _load() async {
    if (recovering) return;
    setState(() {
      review = null;
      captured = null;
      photo = null;
      witnessed = false;
      attempt = null;
      selection++;
    });
    final value = await operation.run(
      () => widget.privacy
          ? widget.repository.privacyContext(
              widget.actor,
              widget.clientId,
              widget.source['cif_version_id'],
              optional,
            )
          : widget.repository.reviewContext(
              widget.actor,
              widget.clientId,
              widget.source,
            ),
      reconcile: true,
    );
    if (mounted && value != null) setState(() => review = value);
  }

  Future<void> _capture() async {
    if (!operation.canWrite) return;
    final context = review;
    final image = photo;
    if (context == null || image == null || !witnessed) return;
    attempt = _CaptureAttempt(
      source: {
        ...widget.source,
        if (widget.privacy) 'optional_service_communications': optional,
      },
      context: stringMap(jsonDecode(jsonEncode(context))),
      requestId: requestId,
      photo: OfficePhoto(Uint8List.fromList(image.bytes), image.mediaType),
    );
    await _recover();
  }

  Future<void> _recover() async {
    final pending = attempt;
    if (pending == null) return;
    final saved = await operation.run(
      () async {
        final evidence =
            pending.evidence ??
            await widget.repository.captureReview(
              widget.actor,
              widget.clientId,
              source: pending.source,
              snapshotHash: pending.context['snapshot_sha256'],
              requestId: pending.requestId,
              bytes: pending.photo.bytes,
              mediaType: pending.photo.mediaType,
            );
        pending.evidence = evidence;
        if (!mounted || !identical(pending, attempt)) return evidence;
        if (widget.privacy) {
          await widget.repository.acknowledgePrivacy(
            widget.actor,
            widget.clientId,
            pending.context,
            evidence,
          );
        }
        return evidence;
      },
      mutation: true,
      reconcile: true,
      idempotentRetry: true,
    );
    if (mounted && saved != null) {
      setState(() {
        captured = saved;
        attempt = null;
        photo = null;
        witnessed = false;
        selection++;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final current = review;
    final evidence = captured;
    return screen(
      widget.privacy ? 'Privacy acknowledgment' : 'Exact review signature',
      [
        if (widget.privacy) ...[
          const Text(
            'Privacy consent is separate from application confirmation and final loan signing.',
          ),
          CheckboxListTile(
            title: const Text(
              'Optional service communications beyond necessary loan servicing',
            ),
            subtitle: const Text(
              'Optional. This choice is not required for a loan.',
            ),
            value: optional,
            onChanged: !operation.canWrite
                ? null
                : (value) {
                    setState(() {
                      optional = value == true;
                      review = null;
                      captured = null;
                      photo = null;
                      witnessed = false;
                      attempt = null;
                      selection++;
                      operation.invalidate();
                    });
                  },
          ),
        ],
        officeButton(
          'Load current review',
          operation.busy || recovering ? null : _load,
        ),
        if (recovering) ...[
          const Text(
            'Recover the same signed capture before selecting another image. This uses the original request and does not create a replacement capture.',
          ),
          officeButton(
            'Recover exact signed capture',
            operation.busy ? null : _recover,
            primary: true,
          ),
        ],
        if (current != null) ...[
          if (current['detail'] != null) Text(current['detail'].toString()),
          if (current['acknowledgment'] is Map)
            ExpansionTile(
              title: const Text('Recorded privacy acknowledgment'),
              children: [OfficeFacts(stringMap(current['acknowledgment']))],
            ),
          OfficeFacts(stringMap(current['review_snapshot'])),
          if (widget.privacy && current['issuable'] == true)
            for (final kind in ['notice', 'consent'])
              officeButton(
                'Download privacy $kind',
                operation.busy
                    ? null
                    : () => saveDownload(
                        () => widget.repository.downloadPrivacy(
                          widget.actor,
                          widget.clientId,
                          widget.source['cif_version_id'],
                          kind,
                          stringMap(
                            stringMap(current['review_snapshot'])[kind],
                          )['sha256'],
                        ),
                      ),
              ),
          if (!widget.privacy || current['issuable'] == true)
            if (evidence == null) ...[
              const Text(
                'Review the saved facts with the applicant, witness the wet signature, then attach the signed paper copy.',
              ),
              OfficeEvidencePicker(
                key: ValueKey(selection),
                enabled: operation.canWrite,
                recoveryContext: ImagePickContext(
                  purpose: widget.source['purpose'] as String,
                  target: jsonEncode({
                    'client_id': widget.clientId,
                    'cif_version_id': widget.source['cif_version_id'],
                    'application_id': widget.source['application_id'],
                    'application_version_id':
                        widget.source['application_version_id'],
                    'snapshot_sha256': current['snapshot_sha256'],
                    if (widget.privacy)
                      'optional_service_communications': optional,
                  }),
                  label: widget.privacy
                      ? 'Signed privacy acknowledgment'
                      : 'Signed information review',
                ),
                picker: widget.picker,
                onChanged: (value) => setState(() {
                  photo = value;
                  requestId = officeRequestId();
                  witnessed = false;
                }),
              ),
              CheckboxListTile(
                title: Text(
                  widget.privacy
                      ? 'I witnessed the applicant review these exact privacy documents and sign with the optional choice shown.'
                      : 'I witnessed the applicant sign this exact information review.',
                ),
                value: witnessed,
                onChanged: operation.canWrite
                    ? (value) => setState(() => witnessed = value == true)
                    : null,
              ),
              officeButton(
                widget.privacy
                    ? 'Record privacy acknowledgment'
                    : 'Save signed review evidence',
                operation.canWrite && photo != null && witnessed
                    ? _capture
                    : null,
                primary: true,
              ),
            ] else ...[
              Text(
                widget.privacy
                    ? 'Privacy acknowledgment recorded.'
                    : 'Signed evidence saved for this exact version.',
              ),
              officeButton(
                'Download saved signed copy',
                operation.busy
                    ? null
                    : () => saveDownload(
                        () => widget.repository.downloadEvidence(
                          widget.actor,
                          widget.clientId,
                          evidence,
                        ),
                      ),
              ),
              officeButton(
                'Continue',
                operation.busy
                    ? null
                    : () => Navigator.of(context).pop(evidence),
                primary: true,
              ),
            ],
        ],
      ],
      reload: recovering ? _recover : _load,
    );
  }
}

class _CaptureAttempt {
  _CaptureAttempt({
    required this.source,
    required this.context,
    required this.requestId,
    required this.photo,
  });
  final OfficeRecord source;
  final OfficeRecord context;
  final String requestId;
  final OfficePhoto photo;
  OfficeRecord? evidence;
}

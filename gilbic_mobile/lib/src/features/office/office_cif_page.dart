import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/office/office_repository.dart';
import 'package:gilbic_mobile/src/features/office/office_review_capture_page.dart';
import 'package:gilbic_mobile/src/features/office/office_widgets.dart';

class OfficeCifPage extends StatefulWidget {
  const OfficeCifPage({
    required this.actor,
    required this.repository,
    required this.clientId,
    super.key,
  });
  final OfficeIdentity actor;
  final OfficeRepository repository;
  final String clientId;
  @override
  State<OfficeCifPage> createState() => _OfficeCifPageState();
}

class _OfficeCifPageState extends OfficeScreenState<OfficeCifPage> {
  final fields = OfficeFields();
  final form = GlobalKey<FormState>();
  OfficeRecord? review;
  OfficeRecord? evidence;
  bool missing = false;
  bool editing = false;
  bool baselinePassed = false;
  String? success;
  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void clearPrivate() {
    fields.clear();
    review = null;
    evidence = null;
    missing = false;
    editing = false;
    baselinePassed = false;
    success = null;
  }

  @override
  void dispose() {
    fields.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      review = null;
      evidence = null;
      missing = false;
      editing = false;
      fields.clear();
      baselinePassed = false;
    });
    final value = await operation.run(() async {
      try {
        return await widget.repository.loadCif(widget.actor, widget.clientId);
      } on SpinaApiException catch (error) {
        if ([404, 409].contains(error.statusCode)) {
          return <String, dynamic>{
            'unavailable': true,
            'detail': error.message,
          };
        }
        rethrow;
      }
    }, reconcile: true);
    if (mounted && value != null) {
      setState(() {
        missing = value['unavailable'] == true;
        review = missing ? null : value;
        if (missing) success = value['detail'];
      });
    }
  }

  Future<void> _write(
    Future<OfficeRecord> Function() action,
    String message,
  ) async {
    evidence = null;
    final result = await operation.run(action, mutation: true);
    if (mounted && result != null) {
      setState(() => success = message);
      await _load();
    }
  }

  void _edit() {
    final current = review!;
    fields.clear();
    for (final entry in cifInformation(current).entries) {
      if (entry.value is! Map) {
        fields.controller(entry.key).text = entry.value?.toString() ?? '';
      }
    }
    final identity = stringMap(current['identity_information']);
    for (final key in [
      'birth_date',
      'birth_place',
      'civil_status',
      'citizenship',
    ]) {
      fields.controller(key).text = identity[key]?.toString() ?? '';
    }
    setState(() {
      editing = true;
      evidence = null;
      success = null;
    });
  }

  Future<void> _correct() async {
    if (!form.currentState!.validate()) return;
    final current = review!;
    final identity = {
      for (final key in [
        'birth_date',
        'birth_place',
        'civil_status',
        'citizenship',
      ])
        key: fields.optional(key),
    };
    final corrected = <String, dynamic>{
      for (final key in ['full_name', 'phone_number', 'present_address'])
        key: fields.text(key),
      'email': fields.optional('email'),
      if (current['identity_information'] != null ||
          identity.values.any((value) => value != null))
        'identity_information': identity,
    };
    await _write(
      () => widget.repository.correctCif(
        widget.actor,
        current,
        corrected,
        fields.text('reason'),
        successor: current['can_correct_information'] != true,
      ),
      'Corrected information saved. Review and confirm this version again.',
    );
  }

  Future<void> _capture({bool privacy = false}) async {
    final selected = review;
    if (!operation.canWrite || selected == null) return;
    final result = await Navigator.of(context).push<OfficeRecord>(
      MaterialPageRoute(
        builder: (_) => OfficeReviewCapturePage(
          actor: widget.actor,
          repository: widget.repository,
          clientId: widget.clientId,
          privacy: privacy,
          source: {
            'purpose': privacy ? 'privacy_acknowledgment' : 'cif_review',
            'cif_version_id': selected['cif_version_id'],
          },
        ),
      ),
    );
    if (mounted && widget.actor.accessDenied) {
      denyAccess();
      return;
    }
    if (!mounted || !identical(selected, review) || result == null) return;
    setState(() {
      if (privacy) {
        success = 'Privacy acknowledgment recorded.';
      } else {
        evidence = result;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final current = review;
    return screen('CIF review', [
      if (success != null)
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Text(success!),
        ),
      if (missing)
        officeButton(
          'Begin CIF draft',
          operation.canWrite
              ? () => _write(
                  () =>
                      widget.repository.beginCif(widget.actor, widget.clientId),
                  'CIF draft started.',
                )
              : null,
          primary: true,
        ),
      if (current != null && editing) ...[
        officeHeading(
          current['can_correct_information'] == true
              ? 'Correct draft information'
              : 'Start a successor CIF review',
        ),
        const Text(
          'Earlier records remain available. This change requires a fresh review and confirmation.',
        ),
        Form(
          key: form,
          child: Column(
            children: [
              for (final field in {
                'full_name': 'Full name',
                'phone_number': 'Phone number',
                'email': 'Email (optional)',
                'present_address': 'Present address',
                'birth_date': 'Birth date (YYYY-MM-DD, optional)',
                'birth_place': 'Birth place (optional)',
                'civil_status': 'Civil status (optional)',
                'citizenship': 'Citizenship (optional)',
                'reason': 'Reason for correction',
              }.entries)
                officeField(
                  fields,
                  field.key,
                  field.value,
                  enabled: operation.canWrite,
                  required: [
                    'full_name',
                    'phone_number',
                    'present_address',
                    'reason',
                  ].contains(field.key),
                  multiline: ['present_address', 'reason'].contains(field.key),
                ),
              officeButton(
                'Save corrected information',
                operation.canWrite ? _correct : null,
                primary: true,
              ),
              officeButton('Cancel correction', operation.busy ? null : _load),
            ],
          ),
        ),
      ] else if (current != null) ...[
        OfficeFacts(current),
        officeButton('Correct information', operation.canWrite ? _edit : null),
        officeHeading('Applicant information confirmation'),
        const Text(
          'Confirm only this saved version with the applicant. This is separate from privacy consent and loan signing.',
        ),
        officeButton(
          'Capture signed CIF review',
          operation.canWrite ? _capture : null,
        ),
        if (evidence != null) ...[
          const Text('Exact-version signed evidence is ready.'),
          officeButton(
            'Confirm this CIF information',
            operation.canWrite
                ? () {
                    final reference = evidence!['evidence_reference'] as String;
                    _write(
                      () => widget.repository.confirmCif(
                        widget.actor,
                        current,
                        reference,
                      ),
                      'CIF information confirmation recorded.',
                    );
                  }
                : null,
            primary: true,
          ),
        ],
        officeButton(
          'Privacy notice and consent',
          operation.canWrite ? () => _capture(privacy: true) : null,
        ),
        if (current['status'] == 'draft') ...[
          officeHeading('Controlled baseline verification'),
          const Text(
            'Record the approved face and liveness provider result. This form does not perform a face scan.',
          ),
          officeField(
            fields,
            'baseline_reference',
            'Provider evidence reference',
            enabled: operation.canWrite,
          ),
          CheckboxListTile(
            title: const Text(
              'Baseline face and liveness verification passed.',
            ),
            value: baselinePassed,
            onChanged: operation.canWrite
                ? (value) => setState(() => baselinePassed = value == true)
                : null,
          ),
          officeButton(
            'Record verified baseline',
            operation.canWrite && baselinePassed
                ? () => _write(
                    () => widget.repository.recordBaseline(
                      widget.actor,
                      current,
                      fields.text('baseline_reference'),
                    ),
                    'Verified baseline recorded.',
                  )
                : null,
          ),
          if (widget.actor.session.role == AppRole.management)
            officeButton(
              'Activate verified CIF',
              operation.canWrite
                  ? () => _write(
                      () =>
                          widget.repository.activateCif(widget.actor, current),
                      'CIF activated.',
                    )
                  : null,
              primary: true,
            )
          else
            const Text(
              'Management activates the CIF after the required review and verification.',
            ),
        ],
      ],
    ], reload: _load);
  }
}

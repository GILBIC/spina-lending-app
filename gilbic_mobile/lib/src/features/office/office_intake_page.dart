import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/office/office_repository.dart';
import 'package:gilbic_mobile/src/features/office/office_widgets.dart';

class OfficeIntakePage extends StatefulWidget {
  const OfficeIntakePage({
    required this.actor,
    required this.repository,
    this.reference,
    super.key,
  });
  final OfficeIdentity actor;
  final OfficeRepository repository;
  final String? reference;
  @override
  State<OfficeIntakePage> createState() => _OfficeIntakePageState();
}

class _OfficeIntakePageState extends OfficeScreenState<OfficeIntakePage> {
  final fields = OfficeFields();
  final form = GlobalKey<FormState>();
  OfficeRecord? record;
  bool privacy = false;
  bool accuracy = false;
  final decisions = <String, String?>{};
  final bypass = <String>{};
  @override
  void initState() {
    super.initState();
    fields.controller('reference', widget.reference);
    if (widget.reference?.isNotEmpty == true) _load();
  }

  @override
  void clearPrivate() {
    fields.clear();
    record = null;
    decisions.clear();
    bypass.clear();
    privacy = false;
    accuracy = false;
  }

  @override
  void dispose() {
    fields.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final reference = fields.text('reference');
    if (reference.isEmpty) return;
    setState(() {
      record = null;
      decisions.clear();
      bypass.clear();
      operation.blocked = true;
    });
    final value = await operation.run(
      () => widget.repository.loadIntake(widget.actor, reference),
      reconcile: true,
    );
    if (mounted && value != null) {
      setState(() {
        record = value;
        decisions.clear();
        bypass.clear();
      });
    }
  }

  Future<void> _submit() async {
    if (!form.currentState!.validate() || !privacy || !accuracy) return;
    final body = <String, dynamic>{
      for (final field in [
        'full_name',
        'phone_number',
        'present_address',
        'national_id_egov_evidence_reference',
        'tin_id_egov_evidence_reference',
        'meralco_bill_evidence_reference',
      ])
        field: fields.text(field),
      'email': fields.optional('email'),
      'privacy_consent': true,
      'accuracy_declaration': true,
    };
    final value = await operation.run(
      () => widget.repository.submitIntake(widget.actor, body),
      mutation: true,
    );
    if (!mounted || value == null) return;
    fields.clear();
    fields.controller('reference').text = value['application_reference'];
    setState(() {
      privacy = false;
      accuracy = false;
    });
    await _load();
  }

  Future<void> _write(Future<OfficeRecord> Function() action) async {
    final value = await operation.run(action, mutation: true);
    if (mounted && value != null) await _load();
  }

  @override
  Widget build(BuildContext context) {
    final saved = record;
    final requirements = stringMap(saved?['requirements']);
    final missing = ['national_id', 'tin_id', 'meralco_bill', 'collector_visit']
        .where((key) => stringMap(requirements[key])['status'] != 'passed')
        .toList();
    return screen('Office intake', [
      officeField(
        fields,
        'reference',
        'Existing office intake reference',
        enabled: !operation.busy,
        onChanged: (_) {
          setState(() {
            operation.invalidate();
            record = null;
          });
        },
      ),
      officeButton('Open office intake', operation.busy ? null : _load),
      if (saved != null) ...[
        OfficeFacts(saved),
        if (saved['status'] != 'eligible_for_cif') ...[
          officeHeading('Review document requirements'),
          for (final name in ['national_id', 'tin_id', 'meralco_bill'])
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: DropdownButtonFormField<String>(
                key: ValueKey('${saved['applicant_id']}-$name'),
                initialValue: decisions[name],
                decoration: InputDecoration(labelText: officeLabel(name)),
                items: const [
                  DropdownMenuItem(value: 'passed', child: Text('Passed')),
                  DropdownMenuItem(value: 'failed', child: Text('Failed')),
                ],
                onChanged: operation.canWrite
                    ? (value) => setState(() => decisions[name] = value)
                    : null,
              ),
            ),
          officeButton(
            'Save document review',
            operation.canWrite &&
                    decisions.values.whereType<String>().length == 3
                ? () => _write(
                    () => widget.repository.reviewRequirements(
                      widget.actor,
                      saved['applicant_id'],
                      {
                        for (final entry in decisions.entries)
                          '${entry.key}_status': entry.value,
                      },
                    ),
                  )
                : null,
          ),
          const Text(
            'Normal CIF eligibility requires all three documents and the Collector residence visit to pass.',
          ),
          officeButton(
            'Approve CIF eligibility',
            operation.canWrite && missing.isEmpty
                ? () => _write(
                    () => widget.repository.approveEligibility(
                      widget.actor,
                      saved['applicant_id'],
                    ),
                  )
                : null,
            primary: true,
          ),
          if (widget.actor.can('client_onboarding.bypass', management: true) &&
              missing.isNotEmpty) ...[
            officeHeading('Management requirement bypass'),
            const Text(
              'Select every currently non-passed requirement and record the authorized reason. Original decisions remain recorded.',
            ),
            for (final name in missing)
              CheckboxListTile(
                title: Text(officeLabel(name)),
                value: bypass.contains(name),
                onChanged: operation.canWrite
                    ? (value) => setState(() {
                        if (value == true) {
                          bypass.add(name);
                        } else {
                          bypass.remove(name);
                        }
                      })
                    : null,
              ),
            officeField(
              fields,
              'bypass_reason',
              'Bypass reason',
              enabled: operation.canWrite,
              multiline: true,
              maxLength: 500,
            ),
            officeButton(
              'Approve requirement bypass',
              operation.canWrite
                  ? () => _write(
                      () => widget.repository.approveEligibility(
                        widget.actor,
                        saved['applicant_id'],
                        bypass: {
                          'bypassed_requirements': bypass.toList(),
                          'reason': fields.text('bypass_reason'),
                        },
                      ),
                    )
                  : null,
            ),
          ],
        ] else
          const Text(
            'Eligible for CIF. Use the office intake reference to continue CIF review. Eligibility does not create a loan or credentials.',
          ),
      ] else ...[
        officeHeading('New office intake'),
        const Text(
          'Enter references from the approved external verification process. Recording a reference does not verify a document.',
        ),
        Form(
          key: form,
          child: Column(
            children: [
              officeField(
                fields,
                'full_name',
                'Full name',
                enabled: operation.canWrite,
                required: true,
                maxLength: 200,
              ),
              officeField(
                fields,
                'phone_number',
                'Phone number',
                enabled: operation.canWrite,
                required: true,
                maxLength: 40,
              ),
              officeField(
                fields,
                'email',
                'Email (optional)',
                enabled: operation.canWrite,
                maxLength: 320,
              ),
              officeField(
                fields,
                'present_address',
                'Present address',
                enabled: operation.canWrite,
                required: true,
                multiline: true,
                maxLength: 500,
              ),
              for (final field in {
                'national_id_egov_evidence_reference':
                    'National ID / eGov evidence reference',
                'tin_id_egov_evidence_reference':
                    'TIN ID / eGov evidence reference',
                'meralco_bill_evidence_reference':
                    'Meralco bill evidence reference',
              }.entries)
                officeField(
                  fields,
                  field.key,
                  field.value,
                  enabled: operation.canWrite,
                  required: true,
                  maxLength: 500,
                ),
              CheckboxListTile(
                title: const Text(
                  'The applicant’s required privacy consent has been recorded.',
                ),
                value: privacy,
                onChanged: operation.canWrite
                    ? (value) => setState(() => privacy = value == true)
                    : null,
              ),
              CheckboxListTile(
                title: const Text(
                  'The applicant declared the intake information accurate.',
                ),
                value: accuracy,
                onChanged: operation.canWrite
                    ? (value) => setState(() => accuracy = value == true)
                    : null,
              ),
              officeButton(
                'Record office intake',
                operation.canWrite && privacy && accuracy ? _submit : null,
                primary: true,
              ),
            ],
          ),
        ),
      ],
    ], reload: _load);
  }
}

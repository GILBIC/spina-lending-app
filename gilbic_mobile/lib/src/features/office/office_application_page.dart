import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/office/office_repository.dart';
import 'package:gilbic_mobile/src/features/office/office_review_capture_page.dart';
import 'package:gilbic_mobile/src/features/office/office_widgets.dart';

const _requestFields = {
  'purpose': 'Purpose',
  'requested_amount': 'Requested amount (PHP)',
  'requested_payment_arrangement': 'Requested payment arrangement',
  'requested_term': 'Requested term',
  'preferred_first_payment_date': 'Preferred first payment date (YYYY-MM-DD)',
};
const _repaymentFields = {
  'repayment_source': 'Repayment source',
  'source_details': 'Source details',
  'monthly_gross_income': 'Monthly gross income (PHP)',
  'monthly_net_income': 'Monthly net income (PHP)',
};
const _obligationFields = {
  'creditor': 'Creditor',
  'outstanding_balance': 'Outstanding balance (PHP)',
  'periodic_payment_amount': 'Periodic payment amount (PHP)',
  'payment_frequency': 'Payment frequency',
  'notes': 'Notes',
};
const _employmentFields = {
  'employer_or_business_name': 'Employer or business name',
  'position_or_business_nature': 'Position or business nature',
  'length_of_employment_or_operation': 'Length of employment or operation',
  'employer_or_business_address': 'Employer or business address',
  'contact_number': 'Employer or business contact number',
};
const _referenceFields = {
  'full_name': 'Name',
  'relationship': 'Relationship',
  'phone_number': 'Phone number',
  'address': 'Address',
};

class OfficeApplicationPage extends StatefulWidget {
  const OfficeApplicationPage({
    required this.actor,
    required this.repository,
    required this.clientId,
    this.applicationReference = '',
    super.key,
  });
  final OfficeIdentity actor;
  final OfficeRepository repository;
  final String clientId;
  final String applicationReference;
  @override
  State<OfficeApplicationPage> createState() => _OfficeApplicationPageState();
}

class _OfficeApplicationPageState
    extends OfficeScreenState<OfficeApplicationPage> {
  final fields = OfficeFields();
  final obligations = <OfficeFields>[];
  final references = <OfficeFields>[];
  OfficeRecord? entry;
  OfficeRecord? review;
  OfficeRecord? evidence;
  String? product;
  bool? hasObligations;
  bool editing = false;
  String? success;
  int formVersion = 0;
  @override
  void initState() {
    super.initState();
    fields.controller('application_reference', widget.applicationReference);
    if (widget.applicationReference.isNotEmpty) _load();
  }

  void _clearRows() {
    for (final row in [...obligations, ...references]) {
      row.dispose();
    }
    obligations.clear();
    references.clear();
  }

  @override
  void clearPrivate() {
    fields.clear();
    _clearRows();
    entry = null;
    review = null;
    evidence = null;
    product = null;
    hasObligations = null;
    editing = false;
    success = null;
  }

  @override
  void dispose() {
    fields.dispose();
    _clearRows();
    super.dispose();
  }

  Future<void> _load() async {
    final reference = fields.text('application_reference');
    if (reference.isEmpty) return;
    setState(() {
      review = null;
      entry = null;
      evidence = null;
      editing = false;
    });
    final result = await operation.run(() async {
      final context = await widget.repository.applicationContext(
        widget.actor,
        widget.clientId,
      );
      OfficeRecord? saved;
      try {
        saved = await widget.repository.loadApplication(
          widget.actor,
          widget.clientId,
          reference,
        );
      } on SpinaApiException catch (error) {
        if (error.statusCode != 404) rethrow;
      }
      return {'entry': context, 'review': saved};
    }, reconcile: true);
    if (!mounted || result == null) return;
    setState(() {
      entry = stringMap(result['entry']);
      review = result['review'] == null ? null : stringMap(result['review']);
    });
  }

  void _edit() {
    final saved = review;
    final information = stringMap(saved?['information']);
    final request = stringMap(information['request']);
    final repayment = stringMap(information['repayment']);
    final details = stringMap(information['details']);
    final employment = stringMap(details['employment']);
    for (final name in _requestFields.keys) {
      fields.controller('request.$name').text = request[name]?.toString() ?? '';
    }
    for (final name in _repaymentFields.keys) {
      fields.controller('repayment.$name').text =
          repayment[name]?.toString() ?? '';
    }
    for (final name in _employmentFields.keys) {
      fields.controller('employment.$name').text =
          employment[name]?.toString() ?? '';
    }
    _clearRows();
    for (final value
        in repayment['obligations'] is List
            ? repayment['obligations'] as List
            : []) {
      final row = OfficeFields();
      for (final name in _obligationFields.keys) {
        row.controller(name, stringMap(value)[name]);
      }
      obligations.add(row);
    }
    for (final value
        in details['references'] is List ? details['references'] as List : []) {
      final row = OfficeFields();
      for (final name in _referenceFields.keys) {
        row.controller(name, stringMap(value)[name]);
      }
      references.add(row);
    }
    setState(() {
      product = request['requested_loan_type_id'];
      hasObligations = repayment['has_existing_obligations'];
      editing = true;
      evidence = null;
      success = null;
      formVersion++;
    });
  }

  Future<void> _save() async {
    final context = entry;
    if (context == null) return;
    final information = <String, dynamic>{
      'request': {
        'requested_loan_type_id': product,
        for (final key in _requestFields.keys)
          key: fields.optional('request.$key'),
      },
      'repayment': {
        for (final key in _repaymentFields.keys)
          key: fields.optional('repayment.$key'),
        'has_existing_obligations': hasObligations,
        'obligations': hasObligations == false
            ? <Object>[]
            : [
                for (final row in obligations)
                  {
                    for (final key in _obligationFields.keys)
                      key: row.optional(key),
                  },
              ],
      },
      'details': {
        'schema_version': 1,
        'employment': {
          for (final key in _employmentFields.keys)
            key: fields.optional('employment.$key'),
        },
        'references': [
          for (final row in references)
            {for (final key in _referenceFields.keys) key: row.optional(key)},
        ],
      },
    };
    final result = await operation.run(
      () => widget.repository.saveApplication(
        widget.actor,
        widget.clientId,
        reference: fields.text('application_reference'),
        cifVersionId: context['cif_version_id'],
        information: information,
        applicationId: review?['application_id'],
        expectedVersion: review?['version_number'],
      ),
      mutation: true,
    );
    if (mounted && result != null) {
      setState(
        () => success =
            'Application information saved. Review this version with the applicant.',
      );
      await _load();
    }
  }

  Future<void> _capture() async {
    final selected = review;
    if (!operation.canWrite || selected == null) return;
    final value = await Navigator.of(context).push<OfficeRecord>(
      MaterialPageRoute(
        builder: (_) => OfficeReviewCapturePage(
          actor: widget.actor,
          repository: widget.repository,
          clientId: widget.clientId,
          source: {
            'purpose': 'application_review',
            'cif_version_id': selected['cif_version_id'],
            'application_id': selected['application_id'],
            'application_version_id': selected['application_version_id'],
          },
        ),
      ),
    );
    if (mounted && widget.actor.accessDenied) {
      denyAccess();
      return;
    }
    if (mounted && identical(selected, review) && value != null) {
      setState(() => evidence = value);
    }
  }

  Future<void> _confirm() async {
    if (evidence == null || review == null) return;
    final selected = review!;
    final reference = evidence!['evidence_reference'] as String;
    final result = await operation.run(
      () => widget.repository.confirmApplication(
        widget.actor,
        selected,
        reference,
      ),
      mutation: true,
    );
    if (mounted && result != null) {
      setState(
        () => success =
            'Exact application information confirmed. Management approval and loan signing remain separate.',
      );
      await _load();
    }
  }

  Widget _row(
    OfficeFields row,
    Map<String, String> labels,
    VoidCallback remove,
  ) => Card(
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: Column(
        children: [
          for (final field in labels.entries)
            officeField(
              row,
              field.key,
              field.value,
              enabled: operation.canWrite,
              money: field.value.contains('(PHP)'),
            ),
          officeButton('Remove row', operation.canWrite ? remove : null),
        ],
      ),
    ),
  );
  @override
  Widget build(BuildContext context) {
    final current = review;
    final products = entry == null
        ? <OfficeRecord>[]
        : officeRecords(entry!['loan_types']);
    return screen('Loan application', [
      officeField(
        fields,
        'application_reference',
        'Loan application reference',
        enabled: !operation.busy && !editing,
        onChanged: (_) => setState(() {
          operation.invalidate();
          entry = null;
          review = null;
          evidence = null;
          editing = false;
          success = null;
        }),
      ),
      officeButton(
        'Open application',
        operation.busy || editing ? null : _load,
      ),
      if (success != null) Text(success!),
      if (!editing && entry != null) ...[
        if (current == null)
          const Text(
            'No application exists for this reference. You may create its first draft.',
          )
        else ...[
          OfficeFacts(current),
          if ((current['missing_fields'] as List).isNotEmpty)
            const Text(
              'This draft has missing information. Saving a draft does not approve a loan.',
            ),
        ],
        officeButton(
          current == null
              ? 'Create application draft'
              : 'Correct application information',
          operation.canWrite ? _edit : null,
        ),
        if (current != null) ...[
          officeButton(
            'Capture signed application review',
            operation.canWrite ? _capture : null,
          ),
          if (evidence != null)
            officeButton(
              'Confirm exact application information',
              operation.canWrite ? _confirm : null,
              primary: true,
            ),
        ],
      ],
      if (editing && entry != null) ...[
        Text(
          'Linked current CIF version ${entry!['cif_version_number']}. This form records the applicant’s request; Management decides approved terms separately.',
        ),
        officeHeading('Requested loan'),
        DropdownButtonFormField<String>(
          key: ValueKey('product-$formVersion'),
          initialValue: product,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'Requested product'),
          items: [
            const DropdownMenuItem<String>(
              value: null,
              child: Text('Not recorded'),
            ),
            for (final item in products)
              DropdownMenuItem<String>(
                value: item['id'],
                child: Text(item['name']),
              ),
            if (product != null &&
                !products.any((item) => item['id'] == product))
              DropdownMenuItem(
                value: product,
                child: const Text('Previously recorded product'),
              ),
          ],
          onChanged: operation.canWrite
              ? (value) => setState(() => product = value)
              : null,
        ),
        const SizedBox(height: 12),
        for (final field in _requestFields.entries)
          officeField(
            fields,
            'request.${field.key}',
            field.value,
            enabled: operation.canWrite,
            money: field.value.contains('(PHP)'),
          ),
        officeHeading('Repayment information'),
        for (final field in _repaymentFields.entries)
          officeField(
            fields,
            'repayment.${field.key}',
            field.value,
            enabled: operation.canWrite,
            money: field.value.contains('(PHP)'),
          ),
        DropdownButtonFormField<bool>(
          key: ValueKey('obligations-$formVersion'),
          initialValue: hasObligations,
          decoration: const InputDecoration(labelText: 'Existing obligations'),
          items: const [
            DropdownMenuItem<bool>(value: null, child: Text('Not recorded')),
            DropdownMenuItem(value: false, child: Text('No')),
            DropdownMenuItem(value: true, child: Text('Yes')),
          ],
          onChanged: operation.canWrite
              ? (value) => setState(() => hasObligations = value)
              : null,
        ),
        if (hasObligations != false) ...[
          for (final row in obligations)
            _row(
              row,
              _obligationFields,
              () => setState(() {
                obligations.remove(row);
                row.dispose();
              }),
            ),
          officeButton(
            'Add declared obligation',
            operation.canWrite
                ? () => setState(() {
                    obligations.add(OfficeFields());
                    hasObligations = true;
                    formVersion++;
                  })
                : null,
          ),
        ],
        officeHeading('Employment or business'),
        for (final field in _employmentFields.entries)
          officeField(
            fields,
            'employment.${field.key}',
            field.value,
            enabled: operation.canWrite,
          ),
        officeHeading('References'),
        for (final row in references)
          _row(
            row,
            _referenceFields,
            () => setState(() {
              references.remove(row);
              row.dispose();
            }),
          ),
        officeButton(
          'Add reference',
          operation.canWrite
              ? () => setState(() => references.add(OfficeFields()))
              : null,
        ),
        officeButton(
          'Save application draft',
          operation.canWrite ? _save : null,
          primary: true,
        ),
        officeButton(
          'Cancel editing and reload',
          operation.busy ? null : _load,
        ),
      ],
    ], reload: _load);
  }
}

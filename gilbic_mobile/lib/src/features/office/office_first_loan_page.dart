import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/office/office_repository.dart';
import 'package:gilbic_mobile/src/features/office/office_widgets.dart';

class OfficeFirstLoanPage extends StatefulWidget {
  const OfficeFirstLoanPage({
    required this.actor,
    required this.repository,
    required this.clientId,
    required this.applicationReference,
    super.key,
  });
  final OfficeIdentity actor;
  final OfficeRepository repository;
  final String clientId;
  final String applicationReference;
  @override
  State<OfficeFirstLoanPage> createState() => _OfficeFirstLoanPageState();
}

class _OfficeFirstLoanPageState extends OfficeScreenState<OfficeFirstLoanPage> {
  final fields = OfficeFields();
  OfficeRecord? application;
  OfficeRecord? options;
  OfficeRecord? loan;
  OfficeRecord? credentials;
  List<OfficeRecord> decisions = [];
  String? product;
  String? template;
  String frequency = 'daily';
  OfficePhoto? contractPhoto;
  OfficePhoto? cashPhoto;
  String contractRequest = officeRequestId();
  String cashRequest = officeRequestId();
  bool witnessed = false;
  bool borrowerConfirmed = false;
  bool revealPassword = false;
  int captureGeneration = 0;
  final complianceChecks = <String, bool>{};
  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void clearPrivate() {
    fields.clear();
    application = null;
    options = null;
    loan = null;
    credentials = null;
    decisions = [];
    product = null;
    template = null;
    contractPhoto = null;
    cashPhoto = null;
    witnessed = false;
    borrowerConfirmed = false;
    revealPassword = false;
    complianceChecks.clear();
    captureGeneration++;
  }

  @override
  void dispose() {
    credentials = null;
    contractPhoto = null;
    cashPhoto = null;
    fields.dispose();
    super.dispose();
  }

  Future<void> _load({bool preserveCredentials = false}) async {
    setState(() {
      if (!preserveCredentials) {
        credentials = null;
        revealPassword = false;
      }
      application = null;
      options = null;
      loan = null;
      decisions = [];
      contractPhoto = null;
      cashPhoto = null;
      witnessed = false;
      borrowerConfirmed = false;
      captureGeneration++;
    });
    final result = await operation.run(() async {
      final review = await widget.repository.loadApplication(
        widget.actor,
        widget.clientId,
        widget.applicationReference,
      );
      final context = await widget.repository.firstLoanContext(widget.actor);
      final loans = await widget.repository.firstLoans(widget.actor, review);
      return {'application': review, 'options': context, 'records': loans};
    }, reconcile: true);
    if (!mounted || result == null) return;
    final current = stringMap(result['records']);
    final loans = officeRecords(current['loans']);
    final active = loans.where((row) => row['status'] != 'cancelled');
    setState(() {
      application = stringMap(result['application']);
      options = stringMap(result['options']);
      if (!officeRecords(
        options!['products'],
      ).any((item) => item['id'] == product)) {
        product = null;
      }
      if (!officeRecords(
        options!['templates'],
      ).any((item) => item['version'] == template)) {
        template = null;
      }
      loan = active.isNotEmpty
          ? active.first
          : loans.isEmpty
          ? null
          : loans.first;
      decisions = current['decisions'] == null
          ? []
          : officeRecords(current['decisions']);
      contractPhoto = null;
      cashPhoto = null;
      witnessed = false;
      borrowerConfirmed = false;
      captureGeneration++;
      fields.controller('principal').text =
          stringMap(
            stringMap(application!['information'])['request'],
          )['requested_amount']?.toString() ??
          '';
      fields.controller('basis_date').text =
          options!['server_business_date']?.toString() ?? '';
      fields.controller('first_date').text =
          stringMap(
            stringMap(application!['information'])['request'],
          )['preferred_first_payment_date']?.toString() ??
          '';
      fields.controller('semi_days', '15,30');
    });
  }

  Future<void> _write(
    Future<OfficeRecord> Function() action, {
    bool credentialResult = false,
  }) async {
    setState(() {
      credentials = null;
      revealPassword = false;
    });
    final value = await operation.run(action, mutation: true);
    if (!mounted || value == null) return;
    setState(() {
      if (credentialResult) {
        credentials = value;
      } else if (value['credentials'] is Map) {
        credentials = stringMap(value['credentials']);
      }
      operation.blocked = true;
    });
    await _load(preserveCredentials: true);
  }

  List<List<String>> _lines(String name, int count) {
    final rows = fields
        .text(name)
        .split('\n')
        .where((line) => line.trim().isNotEmpty)
        .map((line) => line.split('|').map((cell) => cell.trim()).toList())
        .toList();
    if (rows.any(
      (row) => row.length != count || row.any((cell) => cell.isEmpty),
    )) {
      throw const SpinaApiException(
        'Complete every value in each custom schedule or deduction row.',
        statusCode: 422,
      );
    }
    return rows;
  }

  Future<void> _approve() async {
    final current = application;
    if (current == null ||
        options == null ||
        product == null ||
        template == null) {
      return;
    }
    OfficeRecord terms;
    try {
      final selected = officeRecords(
        options!['products'],
      ).firstWhere((item) => item['id'] == product);
      final seven = selected['calculation_mode'] == 'seven_by_seven';
      final count = fields.text('count');
      final semi = fields
          .text('semi_days')
          .split(',')
          .map((value) => int.parse(value.trim()))
          .toList();
      terms = {
        'loan_type_id': product,
        'product_code': seven ? 'seven_by_seven' : 'regular',
        'principal': fields.text('principal'),
        'contractual_interest': seven ? null : fields.text('interest'),
        'interest_rate_percent': seven ? null : fields.text('interest_rate'),
        'daily_interest_per_1000': seven
            ? selected['daily_interest_per_1000']
            : null,
        'payment_frequency': frequency,
        'schedule_basis_date': fields.text('basis_date'),
        'first_due_date': fields.text('first_date'),
        'installment_amount': fields.text('installment'),
        'installment_count': seven || count.isEmpty ? null : int.parse(count),
        'semi_monthly_days': semi,
        'custom_installments': [
          for (final row in _lines('custom_rows', 2))
            {'due_date': row[0], 'amount': row[1]},
        ],
        'deductions': [
          for (final row in _lines('deductions', 3))
            {'code': row[0], 'amount': row[1], 'authority_reference': row[2]},
        ],
        'pricing_review_reference': fields.text('pricing_reference'),
        'account_email': fields.text('account_email'),
      };
    } on Object catch (error) {
      setState(
        () => operation.error = error is SpinaApiException
            ? error.message
            : 'Enter whole installment counts and comma-separated payment days.',
      );
      return;
    }
    await _write(
      () => widget.repository.approveLoan(
        widget.actor,
        current,
        terms,
        template!,
        officeRequestId(),
      ),
    );
  }

  Future<void> _packetAction(String action) async {
    final current = loan!;
    final body = <String, dynamic>{
      if (action != 'documents') 'request_id': officeRequestId(),
      if (action != 'revoke-release') 'packet_hash': current['packet_hash'],
      if (action == 'revoke-release')
        'authorization_id': stringMap(current['authorization'])['id'],
      if (['revoke-release', 'cancel-approval'].contains(action))
        'reason': fields.text('decision_reason'),
    };
    await _write(
      () => widget.repository.packetAction(widget.actor, current, action, body),
    );
  }

  Future<void> _capture(bool contract) async {
    final selected = loan;
    final image = contract ? contractPhoto : cashPhoto;
    if (selected == null || image == null || (contract && !witnessed)) return;
    await _write(
      () => widget.repository.captureLoan(
        widget.actor,
        selected,
        purpose: contract
            ? 'borrower_contract_signed'
            : 'borrower_cash_received',
        bytes: image.bytes,
        mediaType: image.mediaType,
        requestId: contract ? contractRequest : cashRequest,
        witnessed: contract && witnessed,
      ),
    );
  }

  Future<void> _release() async {
    final selected = loan;
    if (selected == null || !borrowerConfirmed || application == null) return;
    final evidence = stringMap(selected['evidence']);
    final contract = stringMap(
      evidence['borrower_contract_signed'],
    )['evidence_reference'];
    final cash = stringMap(
      evidence['borrower_cash_received'],
    )['evidence_reference'];
    if (contract is! String || cash is! String) return;
    await _write(
      () => widget.repository.releaseLoan(
        widget.actor,
        selected,
        application!,
        contractEvidence: contract,
        cashEvidence: cash,
        cashAmount: fields.text('cash_amount'),
        requestId: officeRequestId(),
      ),
    );
  }

  Future<void> _pricing() async {
    final current = loan!;
    final packet = stringMap(current['packet']);
    final terms = stringMap(packet['terms']);
    final body = <String, dynamic>{
      'loan_id': current['loan_id'],
      'payment_frequency': terms['payment_frequency'],
      'contract_reference': packet['contract_reference'],
      'contract_signed_date': terms['schedule_basis_date'],
      'effective_from': terms['schedule_basis_date'],
      'grace_days': terms['grace_days'],
      'first_due_date': terms['first_due_date'],
      'agreed_daily_payment': terms['installment_amount'],
      for (final key in [
        'applicability_review_ready',
        'pricing_cap_review_ready',
        'disclosure_ready',
        'total_cost_cap_review_ready',
      ])
        key: complianceChecks[key] == true,
      'penalty_policy_version': fields.text('policy_version'),
      'penalty_monthly_rate': fields.text('penalty_rate'),
      'penalty_proration_days': 30,
      'penalty_rate_ceiling': fields.text('rate_ceiling'),
      'lifetime_nonprincipal_cost_ceiling': fields.text('lifetime_ceiling'),
      'counted_nonprincipal_cost_at_contract_lock': fields.text('counted_cost'),
      'evidence_reference': fields.text('compliance_evidence'),
      'review_note': fields.text('compliance_note'),
    };
    await _write(() => widget.repository.reviewPricing(widget.actor, body));
  }

  List<Widget> _approval() => [
    officeHeading('Management exact-term approval'),
    const Text(
      'Review the exact product, approved pricing, payment dates, schedule and authorized deductions. Approval leaves the loan pending office release.',
    ),
    DropdownButtonFormField<String>(
      initialValue: product,
      isExpanded: true,
      decoration: const InputDecoration(labelText: 'Approved product'),
      items: [
        for (final item in officeRecords(options!['products']))
          DropdownMenuItem<String>(
            value: item['id'],
            child: Text(item['name']),
          ),
      ],
      onChanged: operation.canWrite
          ? (value) => setState(() => product = value)
          : null,
    ),
    const SizedBox(height: 12),
    for (final field in {
      'principal': 'Approved principal (PHP)',
      'interest_rate': 'Regular: total-contract interest rate (%)',
      'interest': 'Regular: exact contractual interest (PHP)',
      'installment': 'Agreed payment amount (PHP)',
    }.entries)
      officeField(
        fields,
        field.key,
        field.value,
        enabled: operation.canWrite,
        money: true,
      ),
    DropdownButtonFormField<String>(
      initialValue: frequency,
      decoration: const InputDecoration(labelText: 'Payment frequency'),
      items: [
        for (final value in [
          'daily',
          'weekly',
          'semi_monthly',
          'monthly',
          'balloon',
          'custom',
        ])
          DropdownMenuItem(value: value, child: Text(officeLabel(value))),
      ],
      onChanged: operation.canWrite
          ? (value) => setState(() => frequency = value!)
          : null,
    ),
    const SizedBox(height: 12),
    for (final field in {
      'count': 'Regular: installment count',
      'basis_date': 'Approved release-date basis (YYYY-MM-DD)',
      'first_date': 'First contractual payment date (YYYY-MM-DD)',
      'semi_days': 'Semi-monthly payment days (for example 15,30)',
    }.entries)
      officeField(fields, field.key, field.value, enabled: operation.canWrite),
    officeField(
      fields,
      'custom_rows',
      'Custom installments: date | amount, one per line',
      enabled: operation.canWrite,
      multiline: true,
    ),
    officeField(
      fields,
      'deductions',
      'Deductions: code | amount | authority reference, one per line',
      enabled: operation.canWrite,
      multiline: true,
    ),
    officeField(
      fields,
      'pricing_reference',
      'Approved pricing review reference',
      enabled: operation.canWrite,
    ),
    officeField(
      fields,
      'account_email',
      'Selected Client account email',
      enabled: operation.canWrite,
    ),
    DropdownButtonFormField<String>(
      initialValue: template,
      isExpanded: true,
      decoration: const InputDecoration(
        labelText: 'Controlled contractual template',
      ),
      items: [
        for (final item in officeRecords(options!['templates']))
          DropdownMenuItem<String>(
            value: item['version'],
            child: Text(
              '${item['version']}${item['approved_for_execution'] == true ? '' : ' — execution approval pending'}',
            ),
          ),
      ],
      onChanged: operation.canWrite
          ? (value) => setState(() => template = value)
          : null,
    ),
    const Padding(
      padding: EdgeInsets.symmetric(vertical: 12),
      child: Text(
        '7x7 uses the catalog daily-interest basis and the server-generated maturity. Exact compliance review remains required before signing.',
      ),
    ),
    officeButton(
      'Approve exact terms',
      operation.canWrite && product != null && template != null
          ? _approve
          : null,
      primary: true,
    ),
    officeField(
      fields,
      'rejection_reason',
      'Management rejection reason',
      enabled: operation.canWrite,
    ),
    officeButton(
      'Reject application',
      operation.canWrite
          ? () => _write(
              () => widget.repository.rejectLoan(
                widget.actor,
                application!,
                fields.text('rejection_reason'),
                officeRequestId(),
              ),
            )
          : null,
    ),
  ];
  Widget _compliance() => ExpansionTile(
    title: const Text('Exact 7x7 pricing and disclosure review'),
    children: [
      const Text(
        'Record existing approved compliance evidence for this locked packet. A proposed signature-date basis does not record the borrower’s signature.',
      ),
      for (final item in {
        'applicability_review_ready': 'Legal applicability reviewed',
        'pricing_cap_review_ready': 'Pricing caps reviewed',
        'disclosure_ready': 'Disclosures ready',
        'total_cost_cap_review_ready': 'Total-cost caps reviewed',
      }.entries)
        CheckboxListTile(
          title: Text(item.value),
          value: complianceChecks[item.key] == true,
          onChanged: operation.canWrite
              ? (value) =>
                    setState(() => complianceChecks[item.key] = value == true)
              : null,
        ),
      for (final item in {
        'policy_version': 'Approved penalty policy version',
        'penalty_rate': 'Contractual monthly penalty rate',
        'rate_ceiling': 'Approved applicable penalty-rate ceiling',
        'lifetime_ceiling':
            'Approved lifetime non-principal cost ceiling (PHP)',
        'counted_cost': 'Counted non-principal cost at contract lock (PHP)',
        'compliance_evidence': 'Pricing and compliance evidence reference',
        'compliance_note': 'Review note',
      }.entries)
        officeField(
          fields,
          item.key,
          item.value,
          enabled: operation.canWrite,
          initial: item.key == 'penalty_rate' ? '0.030000' : null,
        ),
      officeButton(
        'Record exact 7x7 compliance review',
        operation.canWrite ? _pricing : null,
      ),
    ],
  );
  @override
  Widget build(BuildContext context) {
    final current = loan;
    final packet = stringMap(current?['packet']);
    final authorization = stringMap(current?['authorization']);
    final evidence = stringMap(current?['evidence']);
    final released = current?['status'] == 'released';
    final pending = current?['status'] == 'approved_pending_release';
    final signed =
        stringMap(evidence['borrower_contract_signed'])['evidence_reference']
            is String;
    final cash =
        stringMap(evidence['borrower_cash_received'])['evidence_reference']
            is String;
    final authorized =
        officeUuid(authorization['id']) && authorization['revoked'] == false;
    final credentialValues = stringMap(credentials?['credentials']);
    return screen('First loan', [
      Text(
        'Application ${widget.applicationReference}. CIF/application confirmation, loan signing and actual cash acknowledgment remain separate.',
      ),
      if (application != null)
        ExpansionTile(
          title: Text(
            'Saved application version ${application!['version_number']}',
          ),
          children: [OfficeFacts(application!)],
        ),
      if (current == null && options != null)
        const Text(
          'No first-loan approval has been recorded for this application.',
        ),
      if (current != null) ...[
        officeHeading(
          '${current['loan_number']} · ${officeLabel(current['status'])}',
        ),
        OfficeFacts({
          'borrower': packet['borrower'],
          'product': packet['product_name'],
          'approved_terms': packet['terms'],
          'authorized_cash': packet['net_cash'],
          'locked_payment_schedule': packet['schedule'],
        }),
        if (current['document'] != null)
          officeButton(
            'Download locked PDF packet',
            operation.busy
                ? null
                : () => saveDownload(
                    () =>
                        widget.repository.downloadPacket(widget.actor, current),
                  ),
          )
        else
          const Text(
            'The exact populated PDF packet must be generated before signing or release.',
          ),
        if (pending) ...[
          if (widget.actor.manager) ...[
            if (stringMap(packet['terms'])['product_code'] == 'seven_by_seven')
              if (widget.actor.can(
                'lending.contract_schedule.manage',
                management: true,
              ))
                _compliance()
              else
                const Text(
                  'Management contract schedule permission is required for exact 7x7 compliance review.',
                ),
            if (current['document'] == null)
              officeButton(
                'Generate locked PDF packet',
                operation.canWrite ? () => _packetAction('documents') : null,
              ),
            if (current['document'] != null)
              officeButton(
                'Authorize exact office release',
                operation.canWrite
                    ? () => _packetAction('authorize-release')
                    : null,
              ),
            officeField(
              fields,
              'decision_reason',
              'Reason for revocation or approval cancellation',
              enabled: operation.canWrite,
            ),
            if (authorized)
              officeButton(
                'Revoke release authorization',
                operation.canWrite
                    ? () => _packetAction('revoke-release')
                    : null,
              ),
            officeButton(
              'Cancel unreleased approval',
              operation.canWrite
                  ? () => _packetAction('cancel-approval')
                  : null,
            ),
          ],
          Text(
            'Management release authorization: ${authorized
                ? 'Recorded'
                : authorization.isEmpty
                ? 'Required'
                : 'Revoked'}',
          ),
          if (widget.actor.releaser && current['document'] != null) ...[
            officeHeading('Borrower contract signing'),
            Text(
              signed
                  ? 'Your exact contract signing evidence is recorded.'
                  : 'Record the named borrower’s actual signature on this exact packet.',
            ),
            OfficeEvidencePicker(
              key: ValueKey('contract-$captureGeneration'),
              enabled: operation.canWrite,
              onChanged: (value) => setState(() {
                contractPhoto = value;
                contractRequest = officeRequestId();
                witnessed = false;
              }),
            ),
            CheckboxListTile(
              title: const Text(
                'I witnessed the named borrower sign this exact printed packet at the office.',
              ),
              value: witnessed,
              onChanged: operation.canWrite
                  ? (value) => setState(() => witnessed = value == true)
                  : null,
            ),
            officeButton(
              'Record borrower contract signature',
              operation.canWrite && contractPhoto != null && witnessed
                  ? () => _capture(true)
                  : null,
            ),
            if (authorized) ...[
              officeHeading('Actual cash acknowledgment'),
              Text(
                cash
                    ? 'Your exact cash-receipt evidence is recorded.'
                    : 'Attach the borrower’s actual cash-receipt acknowledgment.',
              ),
              OfficeEvidencePicker(
                key: ValueKey('cash-$captureGeneration'),
                enabled: operation.canWrite,
                onChanged: (value) => setState(() {
                  cashPhoto = value;
                  cashRequest = officeRequestId();
                }),
              ),
              officeButton(
                'Record actual cash acknowledgment',
                operation.canWrite && cashPhoto != null
                    ? () => _capture(false)
                    : null,
              ),
              officeField(
                fields,
                'cash_amount',
                'Actual cash personally received by the named borrower (PHP)',
                enabled: operation.canWrite,
                money: true,
              ),
              CheckboxListTile(
                title: const Text(
                  'The named borrower confirmed receiving this exact cash at the office.',
                ),
                value: borrowerConfirmed,
                onChanged: operation.canWrite
                    ? (value) =>
                          setState(() => borrowerConfirmed = value == true)
                    : null,
              ),
              officeButton(
                'Record completed office release',
                operation.canWrite && signed && cash && borrowerConfirmed
                    ? _release
                    : null,
                primary: true,
              ),
            ],
          ],
        ],
        if (released) ...[
          officeHeading('Completed office release'),
          OfficeFacts({
            'release': current['release'],
            'client_account': current['credential_intent'],
          }),
          if (widget.actor.can('client.credential.manage'))
            officeButton(
              'Retry account setup',
              operation.canWrite
                  ? () => _write(
                      () => widget.repository.credentials(
                        widget.actor,
                        current['loan_id'],
                      ),
                      credentialResult: true,
                    )
                  : null,
            ),
        ],
      ],
      if (decisions.isNotEmpty)
        ExpansionTile(
          title: const Text('Recorded Management decisions'),
          children: [for (final decision in decisions) OfficeFacts(decision)],
        ),
      if (options != null &&
          application != null &&
          widget.actor.manager &&
          (current == null || current['status'] == 'cancelled'))
        ..._approval(),
      if (credentials != null) ...[
        officeHeading('Borrower account handoff'),
        if (credentials!['status'] == 'completed' &&
            credentialValues['username'] is String &&
            credentialValues['password'] is String) ...[
          const Text('Provide these one-time credentials to the borrower now.'),
          Text('Username: ${credentialValues['username']}'),
          Row(
            children: [
              Expanded(
                child: Text(
                  revealPassword
                      ? credentialValues['password']
                      : '••••••••••••',
                  key: const Key('office-issued-password'),
                ),
              ),
              IconButton(
                tooltip: revealPassword ? 'Hide password' : 'Show password',
                onPressed: () =>
                    setState(() => revealPassword = !revealPassword),
                icon: Icon(
                  revealPassword ? Icons.visibility_off : Icons.visibility,
                ),
              ),
            ],
          ),
          Text(stringMap(credentials!['delivery'])['detail']?.toString() ?? ''),
        ] else
          Text(
            credentials!['detail']?.toString() ??
                'Account setup status: ${credentials!['status']}',
          ),
        officeButton(
          'Clear credentials',
          () => setState(() {
            credentials = null;
            revealPassword = false;
          }),
        ),
      ],
    ], reload: _load);
  }
}

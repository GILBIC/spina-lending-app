enum ManagementAlertsAuditDomain {
  paymentUpdates('payment_updates', 'Payment updates'),
  approvals('approvals', 'Approvals'),
  remittanceCustody('remittance_custody', 'Remittance & custody'),
  financial('financial', 'Financial');

  const ManagementAlertsAuditDomain(this.serverValue, this.label);

  final String serverValue;
  final String label;
}

enum ManagementAlertsAuditSeverity {
  info('info'),
  review('review'),
  attention('attention'),
  critical('critical');

  const ManagementAlertsAuditSeverity(this.serverValue);

  final String serverValue;
}

enum ManagementAlertsAuditNavigation {
  paymentUpdates('payment_updates'),
  staffDevices('staff_devices'),
  clientRegistrations('client_registrations'),
  renewals('renewals'),
  support('support'),
  remittanceReview('remittance_review'),
  financialAccounting('financial_accounting');

  const ManagementAlertsAuditNavigation(this.serverValue);

  final String serverValue;
}

enum ManagementAlertCode {
  paymentUpdatesUnread('payment_updates_unread'),
  assignedRemittances('assigned_remittances'),
  unresolvedRejectedRemittances('unresolved_rejected_remittances'),
  renewalRequests('renewal_requests'),
  staffRegistrations('staff_registrations'),
  clientRegistrations('client_registrations'),
  staffDevices('staff_devices'),
  supportRequests('support_requests'),
  protectedFinancialAuditGaps('protected_financial_audit_gaps');

  const ManagementAlertCode(this.serverValue);

  final String serverValue;
}

enum ManagementAuditAction {
  accountInvite('account.invite'),
  accountRoleChange('account.role_change'),
  accountStatusChange('account.status_change'),
  clientRegistrationApprove('client_registration.approve'),
  clientRegistrationReject('client_registration.reject'),
  deviceReplacementAutoRevoke('device.replacement_auto_revoke'),
  deviceStatusChange('device.status_change'),
  renewalRejected('renewal.rejected'),
  renewalManagementApproved('renewal.management.approved'),
  renewalManagementRejected('renewal.management.rejected'),
  renewalActivationCompleted('renewal.activation.completed'),
  supportAnswered('support.answered'),
  supportResolved('support.resolved'),
  remittanceSubmitted('remittance.submitted'),
  remittanceReceived('remittance.received'),
  remittanceRejected('remittance.rejected'),
  financialDraftCreated('financial.draft_created'),
  financialDraftUpdated('financial.draft_updated'),
  financialPosted('financial.posted'),
  financialReversalCreated('financial.reversal_created');

  const ManagementAuditAction(this.serverValue);

  final String serverValue;
}

class ManagementAlert {
  const ManagementAlert({
    required this.code,
    required this.domain,
    required this.title,
    required this.count,
    required this.amount,
    required this.severity,
    required this.navigation,
  });

  final ManagementAlertCode code;
  final ManagementAlertsAuditDomain domain;
  final String title;
  final int count;
  final String? amount;
  final ManagementAlertsAuditSeverity severity;
  final ManagementAlertsAuditNavigation navigation;
}

class ManagementAuditEvent {
  const ManagementAuditEvent({
    required this.eventKey,
    required this.domain,
    required this.action,
    required this.title,
    required this.severity,
    required this.navigation,
    required this.occurredAt,
    required this.businessDate,
    required this.recordId,
    required this.reference,
    required this.currentState,
    required this.actorName,
    required this.checkerName,
    required this.sourceType,
    required this.sourceLabel,
    required this.reason,
  });

  final String eventKey;
  final ManagementAlertsAuditDomain domain;
  final ManagementAuditAction action;
  final String title;
  final ManagementAlertsAuditSeverity severity;
  final ManagementAlertsAuditNavigation navigation;
  final DateTime occurredAt;
  final DateTime businessDate;
  final String recordId;
  final String reference;
  final String currentState;
  final String actorName;
  final String? checkerName;
  final String? sourceType;
  final String? sourceLabel;
  final String? reason;
}

class ManagementAlertsAuditSnapshot {
  const ManagementAlertsAuditSnapshot({
    required this.generatedAt,
    required this.windowDays,
    required this.limit,
    required this.visibleDomains,
    required this.alerts,
    required this.events,
    required this.eventTotalCount,
    required this.notice,
  });

  factory ManagementAlertsAuditSnapshot.fromPayload(
    Map<String, dynamic> payload,
  ) {
    _requireExactFields(payload, const <String>{
      'generated_at',
      'window_days',
      'limit',
      'currency',
      'visible_domains',
      'alerts',
      'events',
      'event_total_count',
      'notice',
    });
    if (payload['currency'] != 'PHP') {
      throw const FormatException('Invalid alerts and audit currency.');
    }
    final windowDays = _integer(
      payload['window_days'],
      minimum: 1,
      maximum: 90,
    );
    final limit = _integer(payload['limit'], minimum: 1, maximum: 200);
    final eventTotalCount = _integer(payload['event_total_count']);
    final visibleDomains = _domainList(payload['visible_domains']);
    final visibleSet = visibleDomains.toSet();
    final rawAlerts = _objectList(payload['alerts'], name: 'alerts');
    final alerts = <ManagementAlert>[];
    final alertCodes = <ManagementAlertCode>{};
    for (final raw in rawAlerts) {
      final alert = _parseAlert(raw);
      if (!alertCodes.add(alert.code) || !visibleSet.contains(alert.domain)) {
        throw const FormatException('Invalid alerts and audit alert.');
      }
      alerts.add(alert);
    }
    final rawEvents = _objectList(payload['events'], name: 'events');
    final events = <ManagementAuditEvent>[];
    final eventKeys = <String>{};
    for (final raw in rawEvents) {
      final event = _parseEvent(raw);
      if (!eventKeys.add(event.eventKey) ||
          !visibleSet.contains(event.domain)) {
        throw const FormatException('Invalid alerts and audit event.');
      }
      events.add(event);
    }
    if (events.length > eventTotalCount) {
      throw const FormatException('Invalid alerts and audit total.');
    }
    return ManagementAlertsAuditSnapshot(
      generatedAt: _timestamp(payload['generated_at']),
      windowDays: windowDays,
      limit: limit,
      visibleDomains: List<ManagementAlertsAuditDomain>.unmodifiable(
        visibleDomains,
      ),
      alerts: List<ManagementAlert>.unmodifiable(alerts),
      events: List<ManagementAuditEvent>.unmodifiable(events),
      eventTotalCount: eventTotalCount,
      notice: _text(payload['notice'], maximum: 500),
    );
  }

  final DateTime generatedAt;
  final int windowDays;
  final int limit;
  final List<ManagementAlertsAuditDomain> visibleDomains;
  final List<ManagementAlert> alerts;
  final List<ManagementAuditEvent> events;
  final int eventTotalCount;
  final String notice;
}

class _AlertSpec {
  const _AlertSpec(
    this.domain,
    this.title,
    this.severity,
    this.navigation, {
    this.hasAmount = false,
  });

  final ManagementAlertsAuditDomain domain;
  final String title;
  final ManagementAlertsAuditSeverity severity;
  final ManagementAlertsAuditNavigation navigation;
  final bool hasAmount;
}

class _EventSpec {
  const _EventSpec(
    this.domain,
    this.title,
    this.severity,
    this.navigation, {
    this.financial = false,
  });

  final ManagementAlertsAuditDomain domain;
  final String title;
  final ManagementAlertsAuditSeverity severity;
  final ManagementAlertsAuditNavigation navigation;
  final bool financial;
}

const _alertSpecs = <ManagementAlertCode, _AlertSpec>{
  ManagementAlertCode.paymentUpdatesUnread: _AlertSpec(
    ManagementAlertsAuditDomain.paymentUpdates,
    'Unread payment updates',
    ManagementAlertsAuditSeverity.info,
    ManagementAlertsAuditNavigation.paymentUpdates,
  ),
  ManagementAlertCode.assignedRemittances: _AlertSpec(
    ManagementAlertsAuditDomain.remittanceCustody,
    'Remittances assigned for review',
    ManagementAlertsAuditSeverity.review,
    ManagementAlertsAuditNavigation.remittanceReview,
    hasAmount: true,
  ),
  ManagementAlertCode.unresolvedRejectedRemittances: _AlertSpec(
    ManagementAlertsAuditDomain.remittanceCustody,
    'Rejected remittances awaiting correction',
    ManagementAlertsAuditSeverity.attention,
    ManagementAlertsAuditNavigation.remittanceReview,
  ),
  ManagementAlertCode.renewalRequests: _AlertSpec(
    ManagementAlertsAuditDomain.approvals,
    'Renewal requests awaiting review',
    ManagementAlertsAuditSeverity.review,
    ManagementAlertsAuditNavigation.renewals,
  ),
  ManagementAlertCode.staffRegistrations: _AlertSpec(
    ManagementAlertsAuditDomain.approvals,
    'Staff registrations awaiting review',
    ManagementAlertsAuditSeverity.review,
    ManagementAlertsAuditNavigation.staffDevices,
  ),
  ManagementAlertCode.clientRegistrations: _AlertSpec(
    ManagementAlertsAuditDomain.approvals,
    'Client registrations awaiting review',
    ManagementAlertsAuditSeverity.review,
    ManagementAlertsAuditNavigation.clientRegistrations,
  ),
  ManagementAlertCode.staffDevices: _AlertSpec(
    ManagementAlertsAuditDomain.approvals,
    'Staff devices awaiting review',
    ManagementAlertsAuditSeverity.review,
    ManagementAlertsAuditNavigation.staffDevices,
  ),
  ManagementAlertCode.supportRequests: _AlertSpec(
    ManagementAlertsAuditDomain.approvals,
    'Client support awaiting review',
    ManagementAlertsAuditSeverity.review,
    ManagementAlertsAuditNavigation.support,
  ),
  ManagementAlertCode.protectedFinancialAuditGaps: _AlertSpec(
    ManagementAlertsAuditDomain.financial,
    'Posted journals missing required audit evidence',
    ManagementAlertsAuditSeverity.critical,
    ManagementAlertsAuditNavigation.financialAccounting,
  ),
};

const _eventSpecs = <ManagementAuditAction, _EventSpec>{
  ManagementAuditAction.accountInvite: _EventSpec(
    ManagementAlertsAuditDomain.approvals,
    'Staff account invited',
    ManagementAlertsAuditSeverity.info,
    ManagementAlertsAuditNavigation.staffDevices,
  ),
  ManagementAuditAction.accountRoleChange: _EventSpec(
    ManagementAlertsAuditDomain.approvals,
    'Account permissions changed',
    ManagementAlertsAuditSeverity.attention,
    ManagementAlertsAuditNavigation.staffDevices,
  ),
  ManagementAuditAction.accountStatusChange: _EventSpec(
    ManagementAlertsAuditDomain.approvals,
    'Account status changed',
    ManagementAlertsAuditSeverity.attention,
    ManagementAlertsAuditNavigation.staffDevices,
  ),
  ManagementAuditAction.clientRegistrationApprove: _EventSpec(
    ManagementAlertsAuditDomain.approvals,
    'Client registration approved',
    ManagementAlertsAuditSeverity.review,
    ManagementAlertsAuditNavigation.clientRegistrations,
  ),
  ManagementAuditAction.clientRegistrationReject: _EventSpec(
    ManagementAlertsAuditDomain.approvals,
    'Client registration rejected',
    ManagementAlertsAuditSeverity.attention,
    ManagementAlertsAuditNavigation.clientRegistrations,
  ),
  ManagementAuditAction.deviceReplacementAutoRevoke: _EventSpec(
    ManagementAlertsAuditDomain.approvals,
    'Replaced device revoked',
    ManagementAlertsAuditSeverity.attention,
    ManagementAlertsAuditNavigation.staffDevices,
  ),
  ManagementAuditAction.deviceStatusChange: _EventSpec(
    ManagementAlertsAuditDomain.approvals,
    'Device status changed',
    ManagementAlertsAuditSeverity.attention,
    ManagementAlertsAuditNavigation.staffDevices,
  ),
  ManagementAuditAction.renewalRejected: _EventSpec(
    ManagementAlertsAuditDomain.approvals,
    'Renewal rejected',
    ManagementAlertsAuditSeverity.attention,
    ManagementAlertsAuditNavigation.renewals,
  ),
  ManagementAuditAction.renewalManagementApproved: _EventSpec(
    ManagementAlertsAuditDomain.approvals,
    'Renewal approved by Management',
    ManagementAlertsAuditSeverity.review,
    ManagementAlertsAuditNavigation.renewals,
  ),
  ManagementAuditAction.renewalManagementRejected: _EventSpec(
    ManagementAlertsAuditDomain.approvals,
    'Renewal rejected by Management',
    ManagementAlertsAuditSeverity.attention,
    ManagementAlertsAuditNavigation.renewals,
  ),
  ManagementAuditAction.renewalActivationCompleted: _EventSpec(
    ManagementAlertsAuditDomain.approvals,
    'Renewal activation completed',
    ManagementAlertsAuditSeverity.info,
    ManagementAlertsAuditNavigation.renewals,
  ),
  ManagementAuditAction.supportAnswered: _EventSpec(
    ManagementAlertsAuditDomain.approvals,
    'Support request answered',
    ManagementAlertsAuditSeverity.info,
    ManagementAlertsAuditNavigation.support,
  ),
  ManagementAuditAction.supportResolved: _EventSpec(
    ManagementAlertsAuditDomain.approvals,
    'Support request resolved',
    ManagementAlertsAuditSeverity.info,
    ManagementAlertsAuditNavigation.support,
  ),
  ManagementAuditAction.remittanceSubmitted: _EventSpec(
    ManagementAlertsAuditDomain.remittanceCustody,
    'Remittance submitted',
    ManagementAlertsAuditSeverity.review,
    ManagementAlertsAuditNavigation.remittanceReview,
  ),
  ManagementAuditAction.remittanceReceived: _EventSpec(
    ManagementAlertsAuditDomain.remittanceCustody,
    'Remittance received',
    ManagementAlertsAuditSeverity.info,
    ManagementAlertsAuditNavigation.remittanceReview,
  ),
  ManagementAuditAction.remittanceRejected: _EventSpec(
    ManagementAlertsAuditDomain.remittanceCustody,
    'Remittance rejected',
    ManagementAlertsAuditSeverity.attention,
    ManagementAlertsAuditNavigation.remittanceReview,
  ),
  ManagementAuditAction.financialDraftCreated: _EventSpec(
    ManagementAlertsAuditDomain.financial,
    'Protected journal draft created',
    ManagementAlertsAuditSeverity.review,
    ManagementAlertsAuditNavigation.financialAccounting,
    financial: true,
  ),
  ManagementAuditAction.financialDraftUpdated: _EventSpec(
    ManagementAlertsAuditDomain.financial,
    'Protected journal draft updated',
    ManagementAlertsAuditSeverity.review,
    ManagementAlertsAuditNavigation.financialAccounting,
    financial: true,
  ),
  ManagementAuditAction.financialPosted: _EventSpec(
    ManagementAlertsAuditDomain.financial,
    'Protected journal posted',
    ManagementAlertsAuditSeverity.attention,
    ManagementAlertsAuditNavigation.financialAccounting,
    financial: true,
  ),
  ManagementAuditAction.financialReversalCreated: _EventSpec(
    ManagementAlertsAuditDomain.financial,
    'Protected journal reversal created',
    ManagementAlertsAuditSeverity.attention,
    ManagementAlertsAuditNavigation.financialAccounting,
    financial: true,
  ),
};

const _sourceLabels = <String, String>{
  'collection': 'Collection',
  'ecl_allowance': 'ECL allowance',
  'ecl_post_writeoff_recovery': 'ECL post-write-off recovery',
  'ecl_writeoff': 'ECL write-off',
  'initial_capital_funding': 'Initial capital funding',
  'loan_disbursement': 'Loan disbursement',
  'loan_disbursement_cancellation_reversal':
      'Loan disbursement cancellation reversal',
  'loan_renewal_execution': 'Loan renewal execution',
  'manual': 'Manual journal',
  'no_collection': 'No-collection accounting',
  'opening_balance': 'Opening balance',
  'period_close': 'Period close',
  'regular_collection_void_reversal': 'Regular collection void reversal',
  'regular_eir_accrual': 'Regular EIR accrual',
  'regular_renewal_eir_accrual': 'Regular renewal EIR accrual',
  'remittance_transfer': 'Remittance transfer',
  'remittance_transfer_reversal': 'Remittance transfer reversal',
  'reversal': 'Journal reversal',
  'seven_by_seven_collection': '7x7 collection',
  'seven_by_seven_collection_reversal': '7x7 collection reversal',
  'v1_tax_additional_liability': 'Tax additional liability',
  'v1_tax_additional_settlement': 'Tax additional settlement',
  'v1_tax_adjustment': 'Tax adjustment',
  'v1_tax_liability': 'Tax liability',
  'v1_tax_recoverable_credit_application': 'Tax Recoverable credit application',
  'v1_tax_recoverable_refund': 'Tax Recoverable refund',
  'v1_tax_settlement': 'Tax settlement',
};

final _domains = <String, ManagementAlertsAuditDomain>{
  for (final value in ManagementAlertsAuditDomain.values)
    value.serverValue: value,
};
final _severities = <String, ManagementAlertsAuditSeverity>{
  for (final value in ManagementAlertsAuditSeverity.values)
    value.serverValue: value,
};
final _navigations = <String, ManagementAlertsAuditNavigation>{
  for (final value in ManagementAlertsAuditNavigation.values)
    value.serverValue: value,
};
final _alertCodes = <String, ManagementAlertCode>{
  for (final value in ManagementAlertCode.values) value.serverValue: value,
};
final _actions = <String, ManagementAuditAction>{
  for (final value in ManagementAuditAction.values) value.serverValue: value,
};

final _offsetTimestamp = RegExp(r'^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$');
final _calendarDate = RegExp(r'^\d{4}-\d{2}-\d{2}$');
final _money = RegExp(r'^(0|[1-9]\d*)\.\d{2}$');
final _uuid = RegExp(
  r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$',
);

ManagementAlert _parseAlert(Map<String, Object?> raw) {
  final code = _enumValue(_alertCodes, raw['code'], 'alert code');
  final spec = _alertSpecs[code]!;
  final fields = <String>{
    'code',
    'domain',
    'title',
    'count',
    'severity',
    'navigation_code',
    if (spec.hasAmount) 'amount',
  };
  _requireExactFields(raw, fields);
  final domain = _enumValue(_domains, raw['domain'], 'alert domain');
  final severity = _enumValue(_severities, raw['severity'], 'alert severity');
  final navigation = _enumValue(
    _navigations,
    raw['navigation_code'],
    'alert navigation',
  );
  final title = _text(raw['title'], maximum: 200);
  if (domain != spec.domain ||
      severity != spec.severity ||
      navigation != spec.navigation ||
      title != spec.title) {
    throw const FormatException('Invalid alerts and audit alert registry.');
  }
  return ManagementAlert(
    code: code,
    domain: domain,
    title: title,
    count: _integer(raw['count']),
    amount: spec.hasAmount ? _moneyText(raw['amount']) : null,
    severity: severity,
    navigation: navigation,
  );
}

ManagementAuditEvent _parseEvent(Map<String, Object?> raw) {
  _requireExactFields(raw, const <String>{
    'event_key',
    'domain',
    'action_code',
    'title',
    'severity',
    'navigation_code',
    'occurred_at',
    'business_date',
    'record_id',
    'reference',
    'current_state',
    'actor_name',
    'checker_name',
    'source_type',
    'source_label',
    'reason',
  });
  final action = _enumValue(_actions, raw['action_code'], 'event action');
  final spec = _eventSpecs[action]!;
  final domain = _enumValue(_domains, raw['domain'], 'event domain');
  final severity = _enumValue(_severities, raw['severity'], 'event severity');
  final navigation = _enumValue(
    _navigations,
    raw['navigation_code'],
    'event navigation',
  );
  final title = _text(raw['title'], maximum: 200);
  if (domain != spec.domain ||
      severity != spec.severity ||
      navigation != spec.navigation ||
      title != spec.title) {
    throw const FormatException('Invalid alerts and audit event registry.');
  }
  String? sourceType;
  String? sourceLabel;
  if (spec.financial) {
    sourceType = _text(raw['source_type'], maximum: 80);
    sourceLabel = _text(raw['source_label'], maximum: 200);
    if (_sourceLabels[sourceType] != sourceLabel) {
      throw const FormatException('Invalid protected financial source.');
    }
  } else if (raw['source_type'] != null || raw['source_label'] != null) {
    throw const FormatException('Invalid non-financial source.');
  }
  return ManagementAuditEvent(
    eventKey: _text(raw['event_key'], maximum: 300),
    domain: domain,
    action: action,
    title: title,
    severity: severity,
    navigation: navigation,
    occurredAt: _timestamp(raw['occurred_at']),
    businessDate: _date(raw['business_date']),
    recordId: _uuidText(raw['record_id']),
    reference: _text(raw['reference'], maximum: 200),
    currentState: _text(raw['current_state'], maximum: 80),
    actorName: _text(raw['actor_name'], maximum: 200),
    checkerName: _optionalText(raw['checker_name'], maximum: 200),
    sourceType: sourceType,
    sourceLabel: sourceLabel,
    reason: _optionalText(raw['reason'], maximum: 500),
  );
}

List<ManagementAlertsAuditDomain> _domainList(Object? raw) {
  if (raw is! List) {
    throw const FormatException('Invalid visible alert domains.');
  }
  final result = <ManagementAlertsAuditDomain>[];
  final seen = <ManagementAlertsAuditDomain>{};
  for (final item in raw) {
    final domain = _enumValue(_domains, item, 'visible domain');
    if (!seen.add(domain)) {
      throw const FormatException('Duplicate visible alert domain.');
    }
    result.add(domain);
  }
  if (!seen.contains(ManagementAlertsAuditDomain.paymentUpdates)) {
    throw const FormatException('Missing payment updates domain.');
  }
  return result;
}

List<Map<String, Object?>> _objectList(Object? raw, {required String name}) {
  if (raw is! List) throw FormatException('Invalid $name.');
  return raw
      .map((item) {
        if (item is! Map || item.keys.any((key) => key is! String)) {
          throw FormatException('Invalid $name item.');
        }
        return Map<String, Object?>.from(item);
      })
      .toList(growable: false);
}

T _enumValue<T>(Map<String, T> registry, Object? raw, String name) {
  if (raw is! String) {
    throw FormatException('Invalid $name.');
  }
  final value = registry[raw];
  if (value == null) throw FormatException('Invalid $name.');
  return value;
}

void _requireExactFields(Map<Object?, Object?> raw, Set<String> fields) {
  if (raw.length != fields.length || !fields.every(raw.containsKey)) {
    throw const FormatException('Invalid alerts and audit fields.');
  }
}

int _integer(Object? raw, {int minimum = 0, int? maximum}) {
  if (raw is! int || raw < minimum || (maximum != null && raw > maximum)) {
    throw const FormatException('Invalid alerts and audit integer.');
  }
  return raw;
}

String _text(Object? raw, {required int maximum}) {
  if (raw is! String ||
      raw.isEmpty ||
      raw.trim() != raw ||
      raw.length > maximum) {
    throw const FormatException('Invalid alerts and audit text.');
  }
  return raw;
}

String? _optionalText(Object? raw, {required int maximum}) {
  if (raw == null) return null;
  return _text(raw, maximum: maximum);
}

String _moneyText(Object? raw) {
  if (raw is! String || !_money.hasMatch(raw)) {
    throw const FormatException('Invalid alerts and audit amount.');
  }
  return raw;
}

String _uuidText(Object? raw) {
  if (raw is! String || !_uuid.hasMatch(raw)) {
    throw const FormatException('Invalid alerts and audit record ID.');
  }
  return raw.toLowerCase();
}

DateTime _timestamp(Object? raw) {
  if (raw is! String || !_offsetTimestamp.hasMatch(raw)) {
    throw const FormatException('Invalid alerts and audit timestamp.');
  }
  final parsed = DateTime.tryParse(raw);
  if (parsed == null) {
    throw const FormatException('Invalid alerts and audit timestamp.');
  }
  return parsed.toUtc();
}

DateTime _date(Object? raw) {
  if (raw is! String || !_calendarDate.hasMatch(raw)) {
    throw const FormatException('Invalid alerts and audit date.');
  }
  final parsed = DateTime.tryParse(raw);
  if (parsed == null || _dateText(parsed) != raw) {
    throw const FormatException('Invalid alerts and audit date.');
  }
  return DateTime.utc(parsed.year, parsed.month, parsed.day);
}

String _dateText(DateTime value) =>
    '${value.year.toString().padLeft(4, '0')}-'
    '${value.month.toString().padLeft(2, '0')}-'
    '${value.day.toString().padLeft(2, '0')}';

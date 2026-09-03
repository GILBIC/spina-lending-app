enum ManagementEmployeeActivityDomain {
  accounting('accounting'),
  hr('hr'),
  payroll('payroll'),
  crmSupport('crm_support'),
  remittanceOperations('remittance_operations'),
  administration('administration');

  const ManagementEmployeeActivityDomain(this.serverValue);

  final String serverValue;
}

enum ManagementEmployeeActivityStatus {
  noActivity('no_activity'),
  inProgress('in_progress'),
  awaitingReview('awaiting_review'),
  completed('completed'),
  needsAttention('needs_attention');

  const ManagementEmployeeActivityStatus(this.serverValue);

  final String serverValue;
}

enum ManagementEmployeeActivityCode {
  accountingJournalPrepared('accounting.journal.prepared'),
  supportAnswered('support.answered'),
  supportResolved('support.resolved'),
  remittanceSubmitted('remittance.submitted');

  const ManagementEmployeeActivityCode(this.serverValue);

  final String serverValue;
}

enum ManagementEmployeeActivityNavigationCode {
  generalJournals('management.general_journals'),
  supportRequests('management.support_requests'),
  remittanceReview('management.remittance_review');

  const ManagementEmployeeActivityNavigationCode(this.serverValue);

  final String serverValue;
}

class ManagementEmployeeActivityRow {
  const ManagementEmployeeActivityRow({
    required this.employeeUserId,
    required this.employeeName,
    required this.functionLabels,
    required this.completedCount,
    required this.inProgressCount,
    required this.awaitingReviewCount,
    required this.needsAttentionCount,
    required this.totalVisibleCount,
    required this.lastActivityAt,
    required this.lastActivityDomain,
    required this.status,
    required this.statusMessage,
  });

  factory ManagementEmployeeActivityRow.fromPayload(Object? raw) {
    final payload = _strictMap(raw, _rowFields, 'employee activity row');
    final completedCount = _count(
      payload['completed_count'],
      'completed_count',
    );
    final inProgressCount = _count(
      payload['in_progress_count'],
      'in_progress_count',
    );
    final awaitingReviewCount = _count(
      payload['awaiting_review_count'],
      'awaiting_review_count',
    );
    final needsAttentionCount = _count(
      payload['needs_attention_count'],
      'needs_attention_count',
    );
    final totalVisibleCount = _count(
      payload['total_visible_count'],
      'total_visible_count',
    );
    if (totalVisibleCount !=
        completedCount +
            inProgressCount +
            awaitingReviewCount +
            needsAttentionCount) {
      throw const FormatException('Invalid employee activity counts.');
    }
    final lastActivityAt = _optionalTimestamp(
      payload['last_activity_at'],
      'last_activity_at',
    );
    final lastActivityDomain = _optionalDomain(payload['last_activity_domain']);
    if ((lastActivityAt == null) != (lastActivityDomain == null)) {
      throw const FormatException('Invalid last employee activity.');
    }

    return ManagementEmployeeActivityRow(
      employeeUserId: _parseUuid(
        payload['employee_user_id'],
        'employee_user_id',
      ),
      employeeName: _text(
        payload['employee_name'],
        'employee_name',
        maximum: 200,
      ),
      functionLabels: _functionLabels(payload['function_labels']),
      completedCount: completedCount,
      inProgressCount: inProgressCount,
      awaitingReviewCount: awaitingReviewCount,
      needsAttentionCount: needsAttentionCount,
      totalVisibleCount: totalVisibleCount,
      lastActivityAt: lastActivityAt,
      lastActivityDomain: lastActivityDomain,
      status: _status(payload['status']),
      statusMessage: _text(
        payload['status_message'],
        'status_message',
        maximum: 500,
      ),
    );
  }

  final String employeeUserId;
  final String employeeName;
  final List<String> functionLabels;
  final int completedCount;
  final int inProgressCount;
  final int awaitingReviewCount;
  final int needsAttentionCount;
  final int totalVisibleCount;
  final DateTime? lastActivityAt;
  final ManagementEmployeeActivityDomain? lastActivityDomain;
  final ManagementEmployeeActivityStatus status;
  final String statusMessage;
}

class ManagementEmployeeActivityItem {
  const ManagementEmployeeActivityItem({
    required this.activityCode,
    required this.domain,
    required this.occurredAt,
    required this.businessDate,
    required this.recordType,
    required this.recordId,
    required this.displayReference,
    required this.summary,
    required this.workflowState,
    required this.status,
    required this.makerName,
    required this.checkerName,
    required this.navigationCode,
  });

  factory ManagementEmployeeActivityItem.fromPayload(Object? raw) {
    final payload = _strictMap(raw, _itemFields, 'employee activity item');
    return ManagementEmployeeActivityItem(
      activityCode: _activityCode(payload['activity_code']),
      domain: _domain(payload['domain']),
      occurredAt: _timestamp(payload['occurred_at'], 'occurred_at'),
      businessDate: _parseCalendarDate(
        payload['business_date'],
        'business_date',
      ),
      recordType: _text(payload['record_type'], 'record_type', maximum: 80),
      recordId: _parseUuid(payload['record_id'], 'record_id'),
      displayReference: _text(
        payload['display_reference'],
        'display_reference',
        maximum: 200,
      ),
      summary: _text(payload['summary'], 'summary', maximum: 500),
      workflowState: _text(
        payload['workflow_state'],
        'workflow_state',
        maximum: 80,
      ),
      status: _status(payload['status']),
      makerName: _optionalText(
        payload['maker_name'],
        'maker_name',
        maximum: 200,
      ),
      checkerName: _optionalText(
        payload['checker_name'],
        'checker_name',
        maximum: 200,
      ),
      navigationCode: _optionalNavigationCode(payload['navigation_code']),
    );
  }

  final ManagementEmployeeActivityCode activityCode;
  final ManagementEmployeeActivityDomain domain;
  final DateTime occurredAt;
  final DateTime businessDate;
  final String recordType;
  final String recordId;
  final String displayReference;
  final String summary;
  final String workflowState;
  final ManagementEmployeeActivityStatus status;
  final String? makerName;
  final String? checkerName;
  final ManagementEmployeeActivityNavigationCode? navigationCode;
}

class ManagementEmployeeActivityPage {
  const ManagementEmployeeActivityPage({
    required this.dateFrom,
    required this.dateTo,
    required this.generatedAt,
    required this.availableDomains,
    required this.totalCount,
    required this.rows,
  });

  factory ManagementEmployeeActivityPage.fromPayload(Object? raw) {
    final payload = _strictMap(raw, _pageFields, 'employee activity page');
    final dateFrom = _parseCalendarDate(payload['date_from'], 'date_from');
    final dateTo = _parseCalendarDate(payload['date_to'], 'date_to');
    _validateRange(dateFrom, dateTo);
    final availableDomains = _domains(payload['available_domains']);
    final rows = _items(
      payload['rows'],
      ManagementEmployeeActivityRow.fromPayload,
      'rows',
    );
    final totalCount = _count(payload['total_count'], 'total_count');
    if (rows.length > totalCount) {
      throw const FormatException('Invalid employee activity total.');
    }
    for (final row in rows) {
      final lastDomain = row.lastActivityDomain;
      if (lastDomain != null && !availableDomains.contains(lastDomain)) {
        throw const FormatException('Invalid employee activity visibility.');
      }
    }
    return ManagementEmployeeActivityPage(
      dateFrom: dateFrom,
      dateTo: dateTo,
      generatedAt: _timestamp(payload['generated_at'], 'generated_at'),
      availableDomains: availableDomains,
      totalCount: totalCount,
      rows: rows,
    );
  }

  final DateTime dateFrom;
  final DateTime dateTo;
  final DateTime generatedAt;
  final List<ManagementEmployeeActivityDomain> availableDomains;
  final int totalCount;
  final List<ManagementEmployeeActivityRow> rows;
}

class ManagementEmployeeActivityTimeline {
  const ManagementEmployeeActivityTimeline({
    required this.employeeUserId,
    required this.employeeName,
    required this.functionLabels,
    required this.dateFrom,
    required this.dateTo,
    required this.generatedAt,
    required this.availableDomains,
    required this.totalCount,
    required this.items,
  });

  factory ManagementEmployeeActivityTimeline.fromPayload(Object? raw) {
    final payload = _strictMap(
      raw,
      _timelineFields,
      'employee activity timeline',
    );
    final dateFrom = _parseCalendarDate(payload['date_from'], 'date_from');
    final dateTo = _parseCalendarDate(payload['date_to'], 'date_to');
    _validateRange(dateFrom, dateTo);
    final availableDomains = _domains(payload['available_domains']);
    final items = _items(
      payload['items'],
      ManagementEmployeeActivityItem.fromPayload,
      'items',
    );
    final totalCount = _count(payload['total_count'], 'total_count');
    if (items.length > totalCount ||
        items.any((item) => !availableDomains.contains(item.domain))) {
      throw const FormatException('Invalid employee activity timeline.');
    }
    return ManagementEmployeeActivityTimeline(
      employeeUserId: _parseUuid(
        payload['employee_user_id'],
        'employee_user_id',
      ),
      employeeName: _text(
        payload['employee_name'],
        'employee_name',
        maximum: 200,
      ),
      functionLabels: _functionLabels(payload['function_labels']),
      dateFrom: dateFrom,
      dateTo: dateTo,
      generatedAt: _timestamp(payload['generated_at'], 'generated_at'),
      availableDomains: availableDomains,
      totalCount: totalCount,
      items: items,
    );
  }

  final String employeeUserId;
  final String employeeName;
  final List<String> functionLabels;
  final DateTime dateFrom;
  final DateTime dateTo;
  final DateTime generatedAt;
  final List<ManagementEmployeeActivityDomain> availableDomains;
  final int totalCount;
  final List<ManagementEmployeeActivityItem> items;
}

const _rowFields = <String>{
  'employee_user_id',
  'employee_name',
  'function_labels',
  'completed_count',
  'in_progress_count',
  'awaiting_review_count',
  'needs_attention_count',
  'total_visible_count',
  'last_activity_at',
  'last_activity_domain',
  'status',
  'status_message',
};

const _itemFields = <String>{
  'activity_code',
  'domain',
  'occurred_at',
  'business_date',
  'record_type',
  'record_id',
  'display_reference',
  'summary',
  'workflow_state',
  'status',
  'maker_name',
  'checker_name',
  'navigation_code',
};

const _pageFields = <String>{
  'date_from',
  'date_to',
  'generated_at',
  'available_domains',
  'total_count',
  'rows',
};

const _timelineFields = <String>{
  'employee_user_id',
  'employee_name',
  'function_labels',
  'date_from',
  'date_to',
  'generated_at',
  'available_domains',
  'total_count',
  'items',
};

final _domainByValue = <String, ManagementEmployeeActivityDomain>{
  for (final value in ManagementEmployeeActivityDomain.values)
    value.serverValue: value,
};

final _statusByValue = <String, ManagementEmployeeActivityStatus>{
  for (final value in ManagementEmployeeActivityStatus.values)
    value.serverValue: value,
};

final _activityCodeByValue = <String, ManagementEmployeeActivityCode>{
  for (final value in ManagementEmployeeActivityCode.values)
    value.serverValue: value,
};

final _navigationCodeByValue =
    <String, ManagementEmployeeActivityNavigationCode>{
      for (final value in ManagementEmployeeActivityNavigationCode.values)
        value.serverValue: value,
    };

final _offsetTimestamp = RegExp(r'^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$');
final _calendarDatePattern = RegExp(r'^\d{4}-\d{2}-\d{2}$');
final _uuidPattern = RegExp(
  r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$',
);

Map<String, Object?> _strictMap(Object? raw, Set<String> fields, String label) {
  if (raw is! Map || raw.keys.any((key) => key is! String)) {
    throw FormatException('Invalid $label.');
  }
  final payload = Map<String, Object?>.from(raw);
  if (payload.length != fields.length ||
      fields.any((field) => !payload.containsKey(field))) {
    throw FormatException('Invalid $label fields.');
  }
  return payload;
}

List<T> _items<T>(Object? raw, T Function(Object?) parser, String field) {
  if (raw is! List) {
    throw FormatException('Invalid $field.');
  }
  return List<T>.unmodifiable(raw.map(parser));
}

List<String> _functionLabels(Object? raw) {
  final labels = _items(
    raw,
    (value) => _text(value, 'function_labels', maximum: 80),
    'function_labels',
  );
  if (labels.toSet().length != labels.length) {
    throw const FormatException('Duplicate employee function label.');
  }
  return labels;
}

List<ManagementEmployeeActivityDomain> _domains(Object? raw) {
  final domains = _items(raw, _domain, 'available_domains');
  if (domains.toSet().length != domains.length) {
    throw const FormatException('Duplicate employee activity domain.');
  }
  return domains;
}

ManagementEmployeeActivityDomain _domain(Object? raw) {
  if (raw is! String || !_domainByValue.containsKey(raw)) {
    throw const FormatException('Invalid employee activity domain.');
  }
  return _domainByValue[raw]!;
}

ManagementEmployeeActivityDomain? _optionalDomain(Object? raw) {
  if (raw == null) return null;
  return _domain(raw);
}

ManagementEmployeeActivityStatus _status(Object? raw) {
  if (raw is! String || !_statusByValue.containsKey(raw)) {
    throw const FormatException('Invalid employee activity status.');
  }
  return _statusByValue[raw]!;
}

ManagementEmployeeActivityCode _activityCode(Object? raw) {
  if (raw is! String || !_activityCodeByValue.containsKey(raw)) {
    throw const FormatException('Invalid employee activity code.');
  }
  return _activityCodeByValue[raw]!;
}

ManagementEmployeeActivityNavigationCode? _optionalNavigationCode(Object? raw) {
  if (raw == null) return null;
  if (raw is! String || !_navigationCodeByValue.containsKey(raw)) {
    throw const FormatException('Invalid employee activity navigation code.');
  }
  return _navigationCodeByValue[raw]!;
}

int _count(Object? raw, String field) {
  if (raw is! int || raw < 0) {
    throw FormatException('Invalid $field.');
  }
  return raw;
}

String _text(Object? raw, String field, {required int maximum}) {
  if (raw is! String) {
    throw FormatException('Invalid $field.');
  }
  final normalized = raw.split(RegExp(r'\s+')).join(' ').trim();
  if (normalized.isEmpty || normalized.length > maximum || normalized != raw) {
    throw FormatException('Invalid $field.');
  }
  return normalized;
}

String? _optionalText(Object? raw, String field, {required int maximum}) {
  if (raw == null) return null;
  return _text(raw, field, maximum: maximum);
}

String _parseUuid(Object? raw, String field) {
  if (raw is! String || !_uuidPattern.hasMatch(raw)) {
    throw FormatException('Invalid $field.');
  }
  return raw.toLowerCase();
}

DateTime _timestamp(Object? raw, String field) {
  if (raw is! String || !_offsetTimestamp.hasMatch(raw)) {
    throw FormatException('Invalid $field.');
  }
  final parsed = DateTime.tryParse(raw);
  if (parsed == null) {
    throw FormatException('Invalid $field.');
  }
  return parsed.toUtc();
}

DateTime? _optionalTimestamp(Object? raw, String field) {
  if (raw == null) return null;
  return _timestamp(raw, field);
}

DateTime _parseCalendarDate(Object? raw, String field) {
  if (raw is! String || !_calendarDatePattern.hasMatch(raw)) {
    throw FormatException('Invalid $field.');
  }
  final parsed = DateTime.tryParse(raw);
  if (parsed == null) {
    throw FormatException('Invalid $field.');
  }
  final value = DateTime.utc(parsed.year, parsed.month, parsed.day);
  if (_dateText(value) != raw) {
    throw FormatException('Invalid $field.');
  }
  return value;
}

void _validateRange(DateTime dateFrom, DateTime dateTo) {
  final days = dateTo.difference(dateFrom).inDays;
  if (days < 0 || days >= 31) {
    throw const FormatException('Invalid employee activity date range.');
  }
}

String _dateText(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}

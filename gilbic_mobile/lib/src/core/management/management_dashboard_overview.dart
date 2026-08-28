enum ManagementDashboardMetricKey {
  activeClients('portfolio.active_clients'),
  activeLoans('portfolio.active_loans'),
  overdueLoans('portfolio.overdue_loans'),
  outstandingBalance('portfolio.outstanding_balance'),
  latestCollections('collections.latest_day'),
  unremittedCollections('collections.unremitted'),
  assignedRemittances('queues.remittances_assigned'),
  protectedRenewals('queues.renewals_protected'),
  staffRegistrations('queues.staff_registrations'),
  clientRegistrations('queues.client_registrations'),
  collectorMobileDevices('queues.collector_mobile_devices'),
  borrowerSupport('queues.borrower_support'),
  unreadActivity('activity.unread');

  const ManagementDashboardMetricKey(this.serverKey);

  final String serverKey;
}

class ManagementDashboardMetric {
  const ManagementDashboardMetric({
    required this.key,
    this.count,
    this.amount,
    this.asOfDate,
  });

  final ManagementDashboardMetricKey key;
  final int? count;
  final String? amount;
  final DateTime? asOfDate;
}

class ManagementDashboardOverview {
  const ManagementDashboardOverview({
    required this.generatedAt,
    required this.currency,
    required this.metrics,
    required this.ignoredMetricKeys,
  });

  factory ManagementDashboardOverview.fromPayload(
    Map<String, dynamic> payload,
  ) {
    final generatedAt = _parseGeneratedAt(payload['generated_at']);
    if (payload['currency'] != 'PHP') {
      throw const FormatException('Invalid overview currency.');
    }

    final rawMetrics = payload['metrics'];
    if (rawMetrics is! List) {
      throw const FormatException('Invalid overview metrics.');
    }

    final metrics = <ManagementDashboardMetric>[];
    final ignoredMetricKeys = <String>[];
    final seenKeys = <ManagementDashboardMetricKey>{};
    for (final rawMetric in rawMetrics) {
      final metricMap = _metricMap(rawMetric);
      final rawKey = metricMap['key'];
      if (rawKey is! String || rawKey.isEmpty || rawKey.trim() != rawKey) {
        throw const FormatException('Invalid overview metric key.');
      }

      final key = _metricKeyByServerKey[rawKey];
      if (key == null) {
        ignoredMetricKeys.add(rawKey);
        continue;
      }
      if (!seenKeys.add(key)) {
        throw const FormatException('Duplicate overview metric key.');
      }
      metrics.add(_parseKnownMetric(key, metricMap));
    }

    return ManagementDashboardOverview(
      generatedAt: generatedAt,
      currency: 'PHP',
      metrics: List<ManagementDashboardMetric>.unmodifiable(metrics),
      ignoredMetricKeys: List<String>.unmodifiable(ignoredMetricKeys),
    );
  }

  final DateTime generatedAt;
  final String currency;
  final List<ManagementDashboardMetric> metrics;
  final List<String> ignoredMetricKeys;

  ManagementDashboardMetric? metric(ManagementDashboardMetricKey key) {
    for (final metric in metrics) {
      if (metric.key == key) return metric;
    }
    return null;
  }
}

enum _MetricShape { count, amount, countAndAmount, datedCountAndAmount }

const _shapeByKey = <ManagementDashboardMetricKey, _MetricShape>{
  ManagementDashboardMetricKey.activeClients: _MetricShape.count,
  ManagementDashboardMetricKey.activeLoans: _MetricShape.count,
  ManagementDashboardMetricKey.overdueLoans: _MetricShape.count,
  ManagementDashboardMetricKey.outstandingBalance: _MetricShape.amount,
  ManagementDashboardMetricKey.latestCollections:
      _MetricShape.datedCountAndAmount,
  ManagementDashboardMetricKey.unremittedCollections:
      _MetricShape.countAndAmount,
  ManagementDashboardMetricKey.assignedRemittances: _MetricShape.countAndAmount,
  ManagementDashboardMetricKey.protectedRenewals: _MetricShape.count,
  ManagementDashboardMetricKey.staffRegistrations: _MetricShape.count,
  ManagementDashboardMetricKey.clientRegistrations: _MetricShape.count,
  ManagementDashboardMetricKey.collectorMobileDevices: _MetricShape.count,
  ManagementDashboardMetricKey.borrowerSupport: _MetricShape.count,
  ManagementDashboardMetricKey.unreadActivity: _MetricShape.count,
};

final _metricKeyByServerKey = <String, ManagementDashboardMetricKey>{
  for (final key in ManagementDashboardMetricKey.values) key.serverKey: key,
};

final _offsetTimestamp = RegExp(r'^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$');
final _money = RegExp(r'^(0|[1-9]\d*)\.\d{2}$');
final _calendarDate = RegExp(r'^\d{4}-\d{2}-\d{2}$');

DateTime _parseGeneratedAt(Object? raw) {
  if (raw is! String || !_offsetTimestamp.hasMatch(raw)) {
    throw const FormatException('Invalid overview timestamp.');
  }
  final parsed = DateTime.tryParse(raw);
  if (parsed == null) {
    throw const FormatException('Invalid overview timestamp.');
  }
  return parsed.toUtc();
}

Map<String, Object?> _metricMap(Object? raw) {
  if (raw is! Map || raw.keys.any((key) => key is! String)) {
    throw const FormatException('Invalid overview metric.');
  }
  return Map<String, Object?>.from(raw);
}

ManagementDashboardMetric _parseKnownMetric(
  ManagementDashboardMetricKey key,
  Map<String, Object?> metric,
) {
  final shape = _shapeByKey[key]!;
  final allowedFields = switch (shape) {
    _MetricShape.count => const <String>{'key', 'count'},
    _MetricShape.amount => const <String>{'key', 'amount'},
    _MetricShape.countAndAmount => const <String>{'key', 'count', 'amount'},
    _MetricShape.datedCountAndAmount => const <String>{
      'key',
      'count',
      'amount',
      'as_of_date',
    },
  };
  if (metric.keys.any((field) => !allowedFields.contains(field))) {
    throw const FormatException('Invalid overview metric fields.');
  }

  final needsCount = shape != _MetricShape.amount;
  final needsAmount = shape != _MetricShape.count;
  final count = needsCount ? _parseCount(metric['count']) : null;
  final amount = needsAmount ? _parseAmount(metric['amount']) : null;
  DateTime? asOfDate;
  if (shape == _MetricShape.datedCountAndAmount &&
      metric.containsKey('as_of_date')) {
    asOfDate = _parseCalendarDate(metric['as_of_date']);
  }

  return ManagementDashboardMetric(
    key: key,
    count: count,
    amount: amount,
    asOfDate: asOfDate,
  );
}

int _parseCount(Object? raw) {
  if (raw is! int || raw < 0) {
    throw const FormatException('Invalid overview count.');
  }
  return raw;
}

String _parseAmount(Object? raw) {
  if (raw is! String || !_money.hasMatch(raw)) {
    throw const FormatException('Invalid overview amount.');
  }
  return raw;
}

DateTime _parseCalendarDate(Object? raw) {
  if (raw is! String || !_calendarDate.hasMatch(raw)) {
    throw const FormatException('Invalid overview date.');
  }
  final parsed = DateTime.tryParse(raw);
  if (parsed == null || _dateText(parsed) != raw) {
    throw const FormatException('Invalid overview date.');
  }
  return DateTime.utc(parsed.year, parsed.month, parsed.day);
}

String _dateText(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}

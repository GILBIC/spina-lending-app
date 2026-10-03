import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';

enum CollectorSurplusKind {
  credits,
  cases,
  actions,
  requests,
  counts,
  exceptions,
  remittances,
  openings,
}

const collectorSurplusAmounts = {
  'gross_obligation',
  'refund_due_total',
  'physical_cash_required',
  'counted_amount',
  'difference',
  'physical_amount',
  'retained_cash_amount',
  'authorized_credit_amount',
  'received_excess_amount',
  'unidentified_amount',
  'recognized_amount',
  'reclassified_amount',
  'returned_amount',
  'applied_amount',
  'outstanding_amount',
  'reserved_amount',
  'available_amount',
  'amount',
  'reviewed_amount',
  'retained_amount',
  'included_amount',
  'remaining_held_amount',
  'authorized_credit_application',
  'total_amount',
  'reversed_amount',
};
const collectorSurplusDispositions = {
  'counted_ready',
  'counted_short_rejected',
  'accepted_exact',
  'accepted_pending_identification',
  'recognized',
  'requested',
  'reserved',
  'return_debited_confirmation_pending',
  'acknowledged_received',
  'acknowledged_not_received',
  'paid',
  'exception_returned',
  'cancelled',
  'opening_prepared',
  'opening_activated',
  'custody_exception_recorded',
  'blocked_adapter',
  'recovery_required',
  'return_reversed',
};

// Mirrors the authoritative safe own-row projection; unknown fields must never
// enter the generic fact renderer or a private export as investigation data.
const collectorOwnRowFields = {
  'id',
  'version',
  'account_id',
  'ledger_context_id',
  'collector_user_id',
  'created_at',
  'remittance_id',
  'recipient_user_id',
  'source_digest',
  'gross_obligation',
  'refund_due_total',
  'physical_cash_required',
  'counted_amount',
  'difference',
  'counted_at',
  'recorded_at',
  'disposition',
  'settlement_id',
  'opening_id',
  'opening_anchor_id',
  'received_excess_amount',
  'unidentified_amount',
  'status',
  'resolutions',
  'case_id',
  'origin_account_id',
  'recognized_amount',
  'reclassified_amount',
  'returned_amount',
  'applied_amount',
  'outstanding_amount',
  'reserved_amount',
  'available_amount',
  'frozen',
  'entries',
  'kind',
  'credit_id',
  'amount',
  'destination',
  'action_id',
  'event_id',
  'event_version',
  'reviewed_amount',
  'confirmation',
  'acknowledged_at',
  'exception_id',
  'collector_request_id',
  'paying_account_id',
  'acknowledgment_id',
  'acknowledgment',
  'holder_user_id',
  'retained_amount',
  'included_amount',
  'remaining_held_amount',
  'cutoff',
  'anchor_kind',
  'reversed_amount',
  'count_id',
  'physical_amount',
  'retained_cash_amount',
  'retained_exception_id',
  'retained_exception_version',
  'authorized_credit_amount',
  'accepted_at',
  'remittance_number',
  'collection_date',
  'total_amount',
  'submitted_at',
  'application_request_supported',
};
const collectorSurplusTotals = {
  'credits': {
    'recognized_amount',
    'reclassified_amount',
    'returned_amount',
    'applied_amount',
    'outstanding_amount',
    'reserved_amount',
    'available_amount',
  },
  'cases': {'received_excess_amount', 'unidentified_amount'},
  'exceptions': {
    'retained_amount',
    'returned_amount',
    'included_amount',
    'remaining_held_amount',
    'reserved_amount',
    'available_amount',
  },
  'actions': {'reserved_amount'},
};

void _validateOwnRowFields(Map row) {
  if (row.keys.any((key) => !collectorOwnRowFields.contains(key))) {
    throw const FormatException(
      'Private investigation fields cannot enter your credit view.',
    );
  }
  const compoundFields = {
    'entries',
    'resolutions',
    'destination',
    'acknowledgment',
  };
  if (row.entries.any(
    (entry) =>
        !compoundFields.contains(entry.key) &&
        (entry.value is Map || entry.value is List),
  )) {
    throw const FormatException(
      'A scalar credit field contains unexpected private data.',
    );
  }
  for (final entry in <String, Set<String>>{
    'entries': {'id', 'kind', 'amount', 'action_id', 'created_at'},
    'resolutions': {'id', 'kind', 'amount', 'status', 'created_at'},
  }.entries) {
    if (row[entry.key] == null) continue;
    if (row[entry.key] is! List ||
        (row[entry.key] as List).any(
          (item) =>
              item is! Map ||
              item.keys.any((key) => !entry.value.contains(key)) ||
              item.values.any((value) => value is Map || value is List),
        )) {
      throw const FormatException(
        'Private investigation history cannot enter your credit view.',
      );
    }
  }
  if (row['destination'] != null) {
    final destination = treasuryObject(row['destination']);
    if (destination.keys.any(
      (key) => !{'kind', 'recipient_reference'}.contains(key),
    )) {
      throw const FormatException(
        'Private destination fields cannot enter your credit view.',
      );
    }
    const TreasuryField(
      'destination',
      'Recipient destination',
      TreasuryFieldKind.destination,
    ).parse(destination);
  }
  if (row['acknowledgment'] != null) {
    final acknowledgment = treasuryObject(row['acknowledgment']);
    const acknowledgmentKeys = {
      'id',
      'version',
      'account_id',
      'ledger_context_id',
      'collector_user_id',
      'created_at',
      'action_id',
      'event_id',
      'event_version',
      'reviewed_amount',
      'confirmation',
      'acknowledged_at',
      'recorded_at',
    };
    if (acknowledgment.keys.any((key) => !acknowledgmentKeys.contains(key))) {
      throw const FormatException(
        'Private acknowledgment fields cannot enter your credit view.',
      );
    }
    _validateOwnRowFields(acknowledgment);
  }
}

void _validateOwnResultEnvelope(Map raw, Map result, String ownUserId) {
  const outerKeys = {
    'contract_version',
    'request_id',
    'action',
    'status',
    'target_id',
    'version',
    'result',
  };
  const phaseSlots = {
    'count',
    'settlement',
    'case',
    'credit',
    'request',
    'action_record',
    'acknowledgment',
    'exception',
    'opening_anchor',
  };
  const scalarKeys = {
    'collector_surplus_contract_version',
    'disposition',
    'source_account_id',
    'actor_user_id',
    'device_id',
    'account_id',
    'ledger_context_id',
  };
  if (raw.keys.any((key) => !outerKeys.contains(key)) ||
      result.keys.any(
        (key) =>
            !phaseSlots.contains(key) &&
            !scalarKeys.contains(key) &&
            key != 'blockers',
      ) ||
      result.entries.any(
        (entry) =>
            scalarKeys.contains(entry.key) &&
            (entry.value is Map || entry.value is List),
      ) ||
      phaseSlots.any((key) => result[key] != null && result[key] is! Map)) {
    throw const FormatException(
      'Unexpected result fields cannot enter your credit view.',
    );
  }
  if (result['blockers'] is! List ||
      (result['blockers'] as List).any(
        (blocker) =>
            blocker is! Map ||
            blocker.keys.any((key) => !{'code', 'message'}.contains(key)) ||
            blocker['code'] is! String ||
            blocker['message'] is! String,
      )) {
    throw const FormatException(
      'Unexpected blocker data cannot enter your credit view.',
    );
  }
  for (final slot in phaseSlots) {
    if (result[slot] == null) continue;
    final row = treasuryObject(result[slot]);
    _validateOwnRowFields(row);
    requireTreasuryId(row['id']);
    if (row['collector_user_id'] != ownUserId ||
        row['version'] is! int ||
        row['version'] < 1) {
      throw const FormatException(
        'An own phase record has no confirmed identity.',
      );
    }
  }
}

void validateCollectorProjection(Object? value, {String? ownUserId}) {
  if (value is List) {
    for (final row in value) {
      validateCollectorProjection(row, ownUserId: ownUserId);
    }
  } else if (value is Map) {
    if (ownUserId != null &&
        value.containsKey('id') &&
        value.containsKey('collector_user_id')) {
      _validateOwnRowFields(value);
    }
    for (final e in value.entries) {
      if (ownUserId != null &&
          {
            'evidence_id',
            'cancellation_evidence_id',
            'recipient_attestation',
            'holder_attestation',
            'reason',
            'source_id',
            'opening_version',
            'source_snapshot',
            'source_items',
            'account_version',
            'balance',
            'masked_identifier',
            'payment_instructions',
            'fee',
            'destination_evidence_id',
            'borrower_name',
            'client_name',
          }.contains(e.key)) {
        throw const FormatException(
          'Private account evidence cannot enter your credit view.',
        );
      }
      if (e.key == 'collector_user_id' &&
          ownUserId != null &&
          e.value != ownUserId) {
        throw const FormatException(
          'This credit does not belong to your account.',
        );
      }
      if (collectorSurplusAmounts.contains(e.key) && e.value != null) {
        TreasuryMoney(e.value, signed: e.key == 'difference');
      }
      if (e.key == 'source_digest' &&
          e.value != null &&
          (e.value is! String ||
              !RegExp(r'^[a-f0-9]{64}$').hasMatch(e.value as String))) {
        throw const FormatException('The source review is incomplete.');
      }
      if (e.key == 'version' && (e.value is! int || (e.value as int) < 1)) {
        throw const FormatException(
          'The current record version is unavailable.',
        );
      }
      if ((e.key == 'id' || (e.key as String).endsWith('_id')) &&
          e.value != null) {
        requireTreasuryId(e.value);
      }
      if (((e.key as String).endsWith('_at') || e.key == 'cutoff') &&
          e.value != null) {
        const TreasuryField(
          'time',
          'Recorded time',
          TreasuryFieldKind.instant,
        ).parse(e.value);
      }
      validateCollectorProjection(e.value, ownUserId: ownUserId);
    }
  }
}

class CollectorSurplusAccount {
  CollectorSurplusAccount(Map<String, dynamic> data)
    : raw = treasuryObject(immutableTreasury(data)) {
    for (final k in ['id', 'ledger_context_id', 'custodian_user_id']) {
      requireTreasuryId(raw[k]);
    }
    if (raw['version'] is! int ||
        raw['version'] < 1 ||
        raw['alias'] is! String ||
        !['physical_cash', 'gcash', 'bank', 'transit'].contains(raw['kind']) ||
        raw['actions'] is! List ||
        (raw['actions'] as List).any((v) => v is! String) ||
        raw.containsKey('balance')) {
      throw const FormatException('The surplus account scope is incomplete.');
    }
  }
  final Map<String, dynamic> raw;
  String get id => raw['id'] as String;
  String get ledgerContextId => raw['ledger_context_id'] as String;
  String get kind => raw['kind'] as String;
  String get alias => raw['alias'] as String;
  int get version => raw['version'] as int;
  bool permits(String capability) =>
      (raw['actions'] as List).contains(capability) ||
      (raw['actions'] as List).contains('collector_surplus_$capability') ||
      (raw['actions'] as List).contains('collector_$capability');
}

void validateCollectorWorkspaceMetadata(
  Map<String, dynamic> raw, {
  required String expectedUserId,
}) {
  final actor = TreasuryActor.fromJson(treasuryObject(raw['actor']));
  if (raw['collector_surplus_contract_version'] != 1 ||
      actor.userId != expectedUserId ||
      !['own', 'staff'].contains(raw['mode']) ||
      raw['readiness'] is! Map ||
      raw['capabilities'] is! Map ||
      (raw['capabilities'] as Map).values.any((value) => value is! bool) ||
      raw['accounts'] is! List ||
      raw['collector_choices'] is! List ||
      raw['opening_choices'] != null && raw['opening_choices'] is! List) {
    throw const FormatException('The surplus workspace scope is incomplete.');
  }
  final readiness = raw['readiness'] as Map;
  for (final key in [
    'enabled',
    'treasury_ready',
    'application_enabled',
    'application_supported',
    'historical_correction_supported',
    'gl_supported',
  ]) {
    if (readiness[key] is! bool) {
      throw const FormatException('Surplus readiness is incomplete.');
    }
  }
  if (readiness['blockers'] is! List) {
    throw const FormatException('Surplus blockers are unavailable.');
  }
  for (final blocker in readiness['blockers'] as List) {
    treasuryBlockerMessage(blocker);
  }
  if (!CollectorSurplusKind.values.any((kind) => kind.name == raw['kind']) ||
      raw['totals'] != null && raw['totals'] is! Map) {
    throw const FormatException('The surplus totals scope is incomplete.');
  }
  final totals = raw['totals'] as Map? ?? const {};
  final allowedTotals = collectorSurplusTotals[raw['kind']] ?? const <String>{};
  if (totals.keys.any((key) => !allowedTotals.contains(key))) {
    throw const FormatException(
      'Unexpected financial totals cannot enter this view.',
    );
  }
  for (final amount in totals.values) {
    TreasuryMoney(amount);
  }
  if (raw['mode'] == 'own') {
    const safeKeys = {
      'collector_surplus_contract_version',
      'actor',
      'mode',
      'readiness',
      'capabilities',
      'accounts',
      'collector_choices',
      'opening_choices',
      'kind',
      'items',
      'total_count',
      'totals',
      'has_more',
      'limit',
      'offset',
    };
    if (raw.keys.any((key) => !safeKeys.contains(key)) ||
        (raw['accounts'] as List).isNotEmpty ||
        (raw['collector_choices'] as List).isNotEmpty ||
        (raw['opening_choices'] as List? ?? const []).isNotEmpty) {
      throw const FormatException(
        'Your credit view exposed a wider account scope.',
      );
    }
    if ((raw['actor'] as Map).keys.any(
      (key) => !{'user_id', 'device_id'}.contains(key),
    )) {
      throw const FormatException(
        'Unexpected actor fields cannot enter your credit view.',
      );
    }
    final readiness = treasuryObject(raw['readiness']);
    if (readiness.keys.any(
      (key) => !{
        'enabled',
        'treasury_ready',
        'application_enabled',
        'application_supported',
        'historical_correction_supported',
        'gl_supported',
        'blockers',
      }.contains(key),
    )) {
      throw const FormatException(
        'Unexpected readiness fields cannot enter your credit view.',
      );
    }
    if (readiness['blockers'] is! List ||
        (readiness['blockers'] as List).any(
          (blocker) =>
              blocker is! Map ||
              blocker.keys.any((key) => !{'code', 'message'}.contains(key)),
        )) {
      throw const FormatException(
        'Unexpected blocker fields cannot enter your credit view.',
      );
    }
    validateCollectorProjection(raw, ownUserId: expectedUserId);
  }
}

class CollectorSurplusWorkspace {
  CollectorSurplusWorkspace(
    Map<String, dynamic> json, {
    required String expectedUserId,
    required CollectorSurplusKind kind,
    required int limit,
    required int offset,
  }) : raw = treasuryObject(immutableTreasury(json)),
       actor = TreasuryActor.fromJson(treasuryObject(json['actor'])) {
    validateCollectorWorkspaceMetadata(raw, expectedUserId: expectedUserId);
    if (raw['collector_surplus_contract_version'] != 1 ||
        actor.userId != expectedUserId ||
        !['own', 'staff'].contains(raw['mode']) ||
        raw['kind'] != kind.name ||
        raw['readiness'] is! Map ||
        raw['capabilities'] is! Map ||
        raw['accounts'] is! List ||
        raw['collector_choices'] is! List ||
        (raw['capabilities'] as Map).values.any((v) => v is! bool)) {
      throw const FormatException(
        'Collector excess is unavailable on this server.',
      );
    }
    final readiness = raw['readiness'] as Map;
    for (final key in [
      'enabled',
      'treasury_ready',
      'application_enabled',
      'application_supported',
      'historical_correction_supported',
      'gl_supported',
    ]) {
      if (readiness[key] is! bool) {
        throw const FormatException('Surplus readiness is incomplete.');
      }
    }
    if (readiness['blockers'] is! List) {
      throw const FormatException('Surplus blockers are unavailable.');
    }
    for (final b in readiness['blockers'] as List) {
      treasuryBlockerMessage(b);
    }
    accounts = (raw['accounts'] as List)
        .map((v) => CollectorSurplusAccount(treasuryObject(v)))
        .toList(growable: false);
    if (mode == 'own' &&
        (accounts.isNotEmpty ||
            (raw['collector_choices'] as List).isNotEmpty)) {
      throw const FormatException(
        'Your credit view exposed a wider account scope.',
      );
    }
    page = TreasuryPage.fromJson(raw, limit: limit, offset: offset);
    validateCollectorProjection({
      'items': raw['items'],
      'totals': raw['totals'],
    }, ownUserId: mode == 'own' ? expectedUserId : null);
    for (final row in page.items) {
      validateCollectorRecord(
        row,
        kind,
        ownUserId: mode == 'own' ? expectedUserId : null,
      );
    }
  }
  final Map<String, dynamic> raw;
  final TreasuryActor actor;
  late final List<CollectorSurplusAccount> accounts;
  late final TreasuryPage page;
  String get mode => raw['mode'] as String;
  bool capability(String key) => (raw['capabilities'] as Map)[key] == true;
  List<String> get blockers => ((raw['readiness'] as Map)['blockers'] as List)
      .map(treasuryBlockerMessage)
      .toList();
  CollectorSurplusAccount? account(String id) =>
      accounts.where((a) => a.id == id).firstOrNull;
  String get authorization => canonicalTreasury({
    'actor': actor.toJson(),
    'mode': mode,
    'accounts': [
      for (final a in accounts)
        {'id': a.id, 'context': a.ledgerContextId, 'actions': a.raw['actions']},
    ],
  });
}

void validateCollectorRecord(
  Map<String, dynamic> row,
  CollectorSurplusKind kind, {
  String? ownUserId,
}) {
  requireTreasuryId(row['id']);
  requireTreasuryId(row['collector_user_id']);
  if (kind != CollectorSurplusKind.remittances) {
    requireTreasuryId(row['ledger_context_id']);
  }
  if (kind != CollectorSurplusKind.remittances &&
      (row['version'] is! int || row['version'] < 1)) {
    throw const FormatException('Record version unavailable.');
  }
  validateCollectorProjection(row, ownUserId: ownUserId);
  final requiredMoney = switch (kind) {
    CollectorSurplusKind.credits => [
      'recognized_amount',
      'reclassified_amount',
      'returned_amount',
      'applied_amount',
      'outstanding_amount',
      'reserved_amount',
      'available_amount',
    ],
    CollectorSurplusKind.cases => [
      'received_excess_amount',
      'unidentified_amount',
    ],
    CollectorSurplusKind.counts => [
      'gross_obligation',
      'refund_due_total',
      'physical_cash_required',
      'counted_amount',
      'difference',
    ],
    CollectorSurplusKind.exceptions => [
      'retained_amount',
      'returned_amount',
      'included_amount',
      'reserved_amount',
      'remaining_held_amount',
      'available_amount',
    ],
    CollectorSurplusKind.remittances =>
      row['application_request_supported'] == true
          ? ['gross_obligation', 'refund_due_total', 'physical_cash_required']
          : <String>[],
    _ => ['amount'],
  };
  for (final key in requiredMoney) {
    TreasuryMoney(row[key], signed: key == 'difference');
  }
  final statuses = switch (kind) {
    CollectorSurplusKind.credits => [
      'outstanding',
      'settled',
      'recovery_required',
    ],
    CollectorSurplusKind.cases => ['pending_identification', 'resolved'],
    CollectorSurplusKind.counts => ['counted_ready', 'counted_short_rejected'],
    CollectorSurplusKind.actions => [
      'reserved',
      'debited_confirmation_pending',
      'partly_reversed',
      'reversed',
      'paid',
      'applied',
      'cancelled',
    ],
    CollectorSurplusKind.requests => ['requested', 'approved'],
    CollectorSurplusKind.exceptions => [
      'held_disputed',
      'partly_returned',
      'returned',
      'included_in_settlement',
    ],
    CollectorSurplusKind.openings => ['draft', 'active'],
    CollectorSurplusKind.remittances => ['submitted', 'received', 'rejected'],
  };
  if (!statuses.contains(
    row[kind == CollectorSurplusKind.counts ? 'disposition' : 'status'],
  )) {
    throw const FormatException('Unsupported surplus record state.');
  }
}

class CollectorSettlementPreview {
  CollectorSettlementPreview(
    Map<String, dynamic> json, {
    required String userId,
    required String deviceId,
    required String remittanceId,
    required CollectorSurplusAccount account,
    String? retainedExceptionId,
    int? retainedExceptionVersion,
  }) : raw = treasuryObject(immutableTreasury(json)) {
    if (raw['collector_surplus_contract_version'] != 1 ||
        raw['actor_user_id'] != userId ||
        raw['device_id'] != deviceId ||
        raw['account_id'] != account.id ||
        raw['account_version'] != account.version ||
        raw['ledger_context_id'] != account.ledgerContextId ||
        raw['remittance_id'] != remittanceId ||
        raw['recipient_user_id'] != userId ||
        account.kind != 'physical_cash' ||
        account.raw['custodian_user_id'] != userId ||
        raw['can_count'] is! bool ||
        raw['blockers'] is! List ||
        raw['source_items'] is! List ||
        raw['refund_due_releases'] is! List ||
        raw['remittance_snapshot'] is! Map) {
      throw const FormatException(
        'The receiving snapshot could not be confirmed.',
      );
    }
    validateCollectorProjection(raw);
    if (raw['retained_exception_id'] != retainedExceptionId ||
        raw['retained_exception_version'] != retainedExceptionVersion ||
        (retainedExceptionId == null) != (retainedExceptionVersion == null)) {
      throw const FormatException('The retained cash selection changed.');
    }
    final retained = TreasuryMoney(raw['retained_cash_amount'] ?? '0.00');
    if ((retainedExceptionId == null) != (retained.text == '0.00')) {
      throw const FormatException('The retained cash amount is incomplete.');
    }
    for (final key in [
      'gross_obligation',
      'refund_due_total',
      'authorized_credit_application',
      'physical_cash_required',
    ]) {
      TreasuryMoney(raw[key]);
    }
    for (final b in raw['blockers'] as List) {
      treasuryBlockerMessage(b);
    }
    if (raw['can_count'] == true &&
        ((raw['blockers'] as List).isNotEmpty ||
            raw['source_digest'] is! String)) {
      throw const FormatException('The source is not ready for count.');
    }
  }
  final Map<String, dynamic> raw;
  bool get canCount => raw['can_count'] == true;
  String? get digest => raw['source_digest'] as String?;
  List<String> get blockers =>
      (raw['blockers'] as List).map(treasuryBlockerMessage).toList();
}

const collectorResultPhases = {
  'collector_surplus_return_reverse': ['action_record', 'return_reversed'],
  'collector_count_record': [
    'count',
    'counted_ready',
    'counted_short_rejected',
  ],
  'collector_count_accept': [
    'settlement',
    'accepted_exact',
    'accepted_pending_identification',
  ],
  'collector_surplus_recognize': ['credit', 'recognized'],
  'collector_surplus_return_request': ['request', 'requested'],
  'collector_surplus_application_request': ['request', 'requested'],
  'collector_surplus_return_prepare': ['action_record', 'reserved'],
  'collector_custody_exception_return_prepare': ['action_record', 'reserved'],
  'collector_surplus_return_acknowledge': [
    'acknowledgment',
    'acknowledged_received',
    'acknowledged_not_received',
  ],
  'collector_custody_exception_return_acknowledge': [
    'acknowledgment',
    'acknowledged_received',
    'acknowledged_not_received',
  ],
  'collector_surplus_return_record': [
    'action_record',
    'paid',
    'exception_returned',
  ],
  'collector_surplus_action_cancel': ['action_record', 'cancelled'],
  'collector_surplus_application_prepare': ['credit', 'blocked_adapter'],
  'collector_surplus_resolve_source': [
    'credit',
    'blocked_adapter',
    'recovery_required',
  ],
  'collector_surplus_opening_prepare': ['opening_anchor', 'opening_prepared'],
  'collector_surplus_opening_activate': ['opening_anchor', 'opening_activated'],
  'collector_custody_exception_record': [
    'exception',
    'custody_exception_recorded',
  ],
};

TreasuryResult validateCollectorOutcome(
  Object? raw,
  Map<String, dynamic> held,
) {
  final value = TreasuryResult.fromJson(treasuryObject(raw));
  final r = value.result, body = treasuryObject(held['body']);
  if (held['surplus_mode'] == 'own') {
    _validateOwnResultEnvelope(value.raw, r, held['actor_user_id'] as String);
  }
  final phase = collectorResultPhases[held['action']];
  if (phase == null ||
      r['collector_surplus_contract_version'] != 1 ||
      value.raw['request_id'] != held['request_id'] ||
      value.raw['action'] != held['action'] ||
      r['actor_user_id'] != held['actor_user_id'] ||
      r['device_id'] != held['device_id'] ||
      r['account_id'] != held['account_id'] ||
      r['ledger_context_id'] != held['ledger_context_id'] ||
      r['blockers'] is! List ||
      !collectorSurplusDispositions.contains(r['disposition'])) {
    throw const FormatException(
      'The exact submitted surplus result is unconfirmed.',
    );
  }
  for (final b in r['blockers'] as List) {
    treasuryBlockerMessage(b);
  }
  validateCollectorProjection(
    r,
    ownUserId: held['surplus_mode'] == 'own'
        ? held['actor_user_id'] as String
        : null,
  );
  const rowKinds = {
    'count': CollectorSurplusKind.counts,
    'case': CollectorSurplusKind.cases,
    'credit': CollectorSurplusKind.credits,
    'request': CollectorSurplusKind.requests,
    'action_record': CollectorSurplusKind.actions,
    'exception': CollectorSurplusKind.exceptions,
    'opening_anchor': CollectorSurplusKind.openings,
  };
  for (final entry in rowKinds.entries) {
    if (!r.containsKey(entry.key)) {
      throw const FormatException('The phase projection is incomplete.');
    }
    if (r[entry.key] != null) {
      final linked = treasuryObject(r[entry.key]);
      if (linked['ledger_context_id'] != held['ledger_context_id']) {
        throw const FormatException('The linked phase context changed.');
      }
      validateCollectorRecord(
        treasuryObject(r[entry.key]),
        entry.value,
        ownUserId: held['surplus_mode'] == 'own'
            ? held['actor_user_id'] as String
            : null,
      );
    }
  }
  if (value.status == 'blocked') {
    if (!['blocked_adapter', 'recovery_required'].contains(r['disposition']) ||
        (r['blockers'] as List).isEmpty) {
      throw const FormatException('The blocked phase is incomplete.');
    }
  } else if (!phase.skip(1).contains(r['disposition'])) {
    throw const FormatException(
      'The returned phase is not this submitted action.',
    );
  }
  final disposition = r['disposition'];
  final requiredSlots = switch (disposition) {
    'accepted_exact' => ['count', 'settlement'],
    'accepted_pending_identification' => ['count', 'settlement', 'case'],
    'recognized' => ['case', 'credit'],
    'requested' => ['credit', 'request'],
    _ => <String>[],
  };
  if (requiredSlots.any((slot) => r[slot] is! Map)) {
    throw const FormatException('The linked result phase is incomplete.');
  }
  final phaseStatus = switch (disposition) {
    'reserved' => 'reserved',
    'paid' || 'exception_returned' => 'paid',
    'cancelled' => 'cancelled',
    'opening_prepared' => 'draft',
    'opening_activated' => 'active',
    'requested' => 'requested',
    _ => null,
  };
  if (phaseStatus != null &&
      (r[phase.first] is! Map || r[phase.first]['status'] != phaseStatus)) {
    throw const FormatException('The saved phase status changed.');
  }
  final candidates = [
    'count',
    'settlement',
    'case',
    'credit',
    'request',
    'action_record',
    'acknowledgment',
    'exception',
    'opening_anchor',
  ];
  final principalKey = value.status == 'blocked'
      ? candidates
            .where((k) => r[k] is Map && (r[k] as Map)['id'] == value.targetId)
            .firstOrNull
      : phase.first;
  if (principalKey == null ||
      r[principalKey] is! Map ||
      r[principalKey]['id'] != value.targetId ||
      r[principalKey]['version'] != value.version) {
    throw const FormatException('The returned phase target is unconfirmed.');
  }
  final principal = treasuryObject(r[principalKey]);
  final snapshots = held['surplus_records'] as Map? ?? const {};
  for (final entry in snapshots.entries) {
    final slot = entry.key as String;
    final expected = entry.value as Map;
    final actual = r[slot];
    if (actual is Map &&
        (actual['id'] != expected['id'] ||
            actual['collector_user_id'] != expected['collector_user_id'])) {
      throw const FormatException('The returned source identity changed.');
    }
    if (actual is Map &&
        [
          'account_id',
          'origin_account_id',
          'paying_account_id',
          'ledger_context_id',
        ].any((key) => expected[key] != null && actual[key] != expected[key])) {
      throw const FormatException('The reviewed source account changed.');
    }
    if (actual is Map &&
        expected['amount'] != null &&
        actual['amount'] != expected['amount']) {
      throw const FormatException('The reviewed reserved principal changed.');
    }
    if (actual is Map &&
        slot == 'count' &&
        canonicalTreasury(actual) != canonicalTreasury(expected)) {
      throw const FormatException('The immutable reviewed count changed.');
    }
    if (principal['collector_user_id'] != expected['collector_user_id']) {
      throw const FormatException('The returned Collector changed.');
    }
  }
  final bindings = <String, String>{
    'remittance_id': 'remittance_id',
    'count_id': 'count_id',
    'case_id': 'case_id',
    'credit_id': 'credit_id',
    'exception_id': 'exception_id',
    'action_id': 'action_id',
    'collector_request_id': 'collector_request_id',
    'event_id': 'event_id',
    'event_version': 'event_version',
    'source_digest': 'source_digest',
    'destination': 'destination',
    'counted_amount': 'counted_amount',

    'reviewed_amount': 'reviewed_amount',
    'confirmation': 'confirmation',
    'opening_id': 'opening_id',
    'anchor_id': 'id',
  };
  for (final e in bindings.entries) {
    if (body[e.key] != null &&
        principal.containsKey(e.value) &&
        canonicalTreasury(principal[e.value]) !=
            canonicalTreasury(body[e.key])) {
      throw FormatException('The returned ${e.value} changed.');
    }
  }
  if (body['counted_at'] != null &&
      principal.containsKey('counted_at') &&
      DateTime.parse(principal['counted_at'] as String) !=
          DateTime.parse(body['counted_at'] as String)) {
    throw const FormatException('The recorded count time changed.');
  }
  if (body['amount'] != null &&
      held['action'] != 'collector_surplus_return_reverse' &&
      ['request', 'action_record', 'opening_anchor'].contains(principalKey) &&
      principal['amount'] != body['amount']) {
    throw const FormatException('The returned principal changed.');
  }
  if (principalKey == 'count' &&
      (principal['counted_amount'] != body['counted_amount'] ||
          principal['remittance_id'] != body['remittance_id'] ||
          principal['source_digest'] != body['source_digest'])) {
    throw const FormatException('The count result changed.');
  }
  if (principalKey == 'count' || principalKey == 'settlement') {
    final reference = principalKey == 'count' ? body : snapshots['count'];
    for (final key in ['retained_exception_id', 'retained_exception_version']) {
      if (reference is! Map || principal[key] != reference[key]) {
        throw const FormatException(
          'The retained cash identity or version changed.',
        );
      }
    }
    if (principalKey == 'settlement' &&
        (principal['retained_cash_amount'] ?? '0.00') !=
            (reference['retained_cash_amount'] ?? '0.00')) {
      throw const FormatException('The accepted retained cash amount changed.');
    }
    if (principalKey == 'count' &&
        (principal['retained_cash_amount'] ?? '0.00') !=
            ((snapshots['remittance'] as Map?)?['retained_cash_amount'] ??
                '0.00')) {
      throw const FormatException('The counted retained cash amount changed.');
    }
  }
  if (principalKey == 'settlement') {
    for (final key in [
      'physical_amount',
      'authorized_credit_amount',
      'gross_obligation',
    ]) {
      TreasuryMoney(principal[key]);
    }
    if (principal['account_id'] != held['account_id'] ||
        principal['ledger_context_id'] != held['ledger_context_id']) {
      throw const FormatException('The settlement account changed.');
    }
    final count = snapshots['count'];
    if (count is! Map ||
        principal['count_id'] != count['id'] ||
        principal['physical_amount'] != count['counted_amount'] ||
        principal['gross_obligation'] != count['gross_obligation'] ||
        principal['authorized_credit_amount'] != '0.00' ||
        principal['remittance_id'] != count['remittance_id'] ||
        principal['recipient_user_id'] != count['recipient_user_id'] ||
        principal['collector_user_id'] != count['collector_user_id'] ||
        principal['event_id'] == null &&
            principal['physical_amount'] != '0.00') {
      throw const FormatException('The accepted physical settlement changed.');
    }
    final excess = r['case'];
    if (disposition == 'accepted_pending_identification') {
      if (excess is! Map ||
          excess['settlement_id'] != principal['id'] ||
          excess['collector_user_id'] != count['collector_user_id'] ||
          excess['account_id'] != count['account_id'] ||
          excess['ledger_context_id'] != count['ledger_context_id'] ||
          excess['source_digest'] != count['source_digest'] ||
          excess['status'] != 'pending_identification' ||
          excess['received_excess_amount'] != count['difference'] ||
          excess['unidentified_amount'] != count['difference'] ||
          count['difference'] == '0.00' ||
          r['credit'] != null) {
        throw const FormatException(
          'The pending excess identification changed.',
        );
      }
    } else if (disposition == 'accepted_exact' &&
        (count['difference'] != '0.00' ||
            excess != null ||
            r['credit'] != null)) {
      throw const FormatException(
        'Exact acceptance cannot recognize excess credit.',
      );
    }
  }
  if (principalKey == 'settlement' && principal['event_id'] != null) {
    requireTreasuryId(principal['event_id']);
  }
  if (principalKey == 'acknowledgment' &&
      (principal['action_id'] != body['action_id'] ||
          principal['event_id'] != body['event_id'] ||
          principal['event_version'] != body['event_version'] ||
          principal['reviewed_amount'] != body['reviewed_amount'] ||
          principal['confirmation'] != body['confirmation'])) {
    throw const FormatException('The recipient acknowledgment changed.');
  }
  if (principalKey == 'action_record' &&
      ['paid', 'exception_returned'].contains(r['disposition']) &&
      (principal['status'] != 'paid' ||
          principal['event_id'] != body['event_id'] ||
          principal['event_version'] != body['event_version'] ||
          principal['acknowledgment_id'] != body['acknowledgment_id'])) {
    throw const FormatException('The paid return is unconfirmed.');
  }
  if (principalKey == 'credit' &&
      held['action'] == 'collector_surplus_recognize' &&
      principal['recognized_amount'] != body['amount']) {
    throw const FormatException('Recognized credit amount changed.');
  }
  if (principalKey == 'count' && principal['disposition'] != r['disposition']) {
    throw const FormatException('Count disposition changed.');
  }
  if (principalKey == 'acknowledgment' &&
      r['disposition'] != 'acknowledged_${body['confirmation']}') {
    throw const FormatException('Acknowledgment disposition changed.');
  }
  if (held['action'] == 'collector_surplus_return_reverse') {
    final incoming = r['incoming_event'];
    if (incoming is! Map ||
        incoming['amount'] != body['amount'] ||
        incoming['direction'] != 'credit' ||
        incoming['account_id'] != held['account_id'] ||
        incoming['ledger_context_id'] != held['ledger_context_id'] ||
        incoming['provider'] != body['provider'] ||
        incoming['reference'] != body['reference'] ||
        incoming['evidence_id'] != body['evidence_id'] ||
        incoming['effective_at'] is! String ||
        DateTime.parse(incoming['effective_at'] as String) !=
            DateTime.parse(body['effective_at'] as String) ||
        !['partly_reversed', 'reversed'].contains(principal['status'])) {
      throw const FormatException('The observed incoming reversal changed.');
    }
  }
  return value;
}

// Validates an already observed cash fact independently of business-link
// success. A source blocker preserves the event and the unpaid reservation.
void validateCollectorDebitOutcome(
  TreasuryResult value,
  Map<String, dynamic> held,
) {
  final result = value.result, body = treasuryObject(held['body']);
  if (value.status != 'saved' ||
      value.raw['request_id'] != body['request_id'] ||
      value.raw['action'] != 'disbursement_record' ||
      result['actor_user_id'] != held['actor_user_id'] ||
      result['device_id'] != held['device_id'] ||
      result['account_id'] != held['account_id'] ||
      result['ledger_context_id'] != held['ledger_context_id'] ||
      result['event'] is! Map ||
      result['event']['id'] != value.targetId ||
      result['event']['version'] != value.version ||
      result['event']['amount'] != body['amount']) {
    throw const FormatException('The actual debit identity changed.');
  }
  final original = treasuryObject(held['collector_source']);
  final event = treasuryObject(result['event']);
  if (event['account_id'] != held['account_id'] ||
      event['ledger_context_id'] != held['ledger_context_id'] ||
      event['direction'] != 'debit') {
    throw const FormatException(
      'The actual debit/source result is unconfirmed.',
    );
  }
  final link = treasuryObject(result['source_link']);
  if (link['source_id'] != body['source_id'] ||
      link['source_version'] != body['source_version'] ||
      link['observed_event_id'] != event['id'] ||
      event['recorded_by_user_id'] != held['actor_user_id'] ||
      event['device_id'] != held['device_id'] ||
      event['provider'] != body['provider'] ||
      event['reference'] != body['reference'] ||
      event['evidence_id'] != body['evidence_id'] ||
      event['fee'] != body['fee'] ||
      event['effective_at'] is! String ||
      DateTime.parse(event['effective_at'] as String) !=
          DateTime.parse(body['effective_at'] as String)) {
    throw const FormatException(
      'The actual debit/source result is unconfirmed.',
    );
  }

  if (link['status'] == 'confirmation_pending') {
    final row = treasuryObject(link['action_record']);
    validateCollectorRecord(row, CollectorSurplusKind.actions);
    if (link['disposition'] != 'return_debited_confirmation_pending' ||
        row['id'] != original['id'] ||
        row['collector_user_id'] != original['collector_user_id'] ||
        row['amount'] != original['amount'] ||
        row['paying_account_id'] != held['account_id'] ||
        row['ledger_context_id'] != held['ledger_context_id'] ||
        row['event_id'] != event['id'] ||
        row['event_version'] != event['version'] ||
        row['status'] != 'debited_confirmation_pending') {
      throw const FormatException(
        'The actual debit/source result is unconfirmed.',
      );
    }
  } else if (link['status'] == 'blocked' &&
      link['blocker'] is String &&
      (link['blocker'] as String).isNotEmpty) {
    final row = treasuryObject(link['action_record']);
    validateCollectorRecord(row, CollectorSurplusKind.actions);
    if (row['id'] != original['id'] ||
        row['amount'] != original['amount'] ||
        row['collector_user_id'] != original['collector_user_id'] ||
        row['origin_account_id'] != original['origin_account_id'] ||
        row['paying_account_id'] != held['account_id'] ||
        row['ledger_context_id'] != held['ledger_context_id'] ||
        row['status'] != 'reserved' ||
        row['event_id'] != original['event_id']) {
      throw const FormatException(
        'The actual debit/source result is unconfirmed.',
      );
    }
  } else {
    throw const FormatException(
      'The actual debit/source result is unconfirmed.',
    );
  }
}

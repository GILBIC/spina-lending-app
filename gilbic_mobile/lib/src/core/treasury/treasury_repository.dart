import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:crypto/crypto.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_repository.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/media/private_image_store.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/core/treasury/collector_surplus_models.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import 'package:path/path.dart' as paths;
import 'package:path_provider/path_provider.dart';

class TreasuryAccessChanged implements Exception {
  const TreasuryAccessChanged();
  @override
  String toString() =>
      'Access changed. Reopen this task with your current account.';
}

class TreasuryUncertain implements Exception {
  const TreasuryUncertain();
  @override
  String toString() =>
      'The result is unconfirmed. Check this exact request before another submission.';
}

abstract interface class TreasuryJournal {
  Future<String?> read();
  Future<void> write(String value);
  Future<void> clear();
}

class SecureTreasuryJournal implements TreasuryJournal {
  const SecureTreasuryJournal({this.storage = const FlutterSecureStorage()});
  final FlutterSecureStorage storage;
  static const key = 'gilbic.treasury.submitted_attempt.v1';
  @override
  Future<String?> read() => storage.read(key: key);
  @override
  Future<void> write(String value) => storage.write(key: key, value: value);
  @override
  Future<void> clear() => storage.delete(key: key);
}

class MemoryTreasuryJournal implements TreasuryJournal {
  String? value;
  @override
  Future<String?> read() async => value;
  @override
  Future<void> write(String next) async {
    value = next;
  }

  @override
  Future<void> clear() async {
    value = null;
  }
}

abstract interface class TreasuryRepository {
  TreasuryWorkspace? get workspace;
  String? get pendingRequestId;
  bool get busy;
  bool get denied;
  Future<TreasuryWorkspace> loadWorkspace();
  Future<void> restoreAttempt();
  Future<TreasuryPage> list(
    TreasuryListKind kind, {
    String? accountId,
    String? clientId,
    int limit = 50,
    int offset = 0,
  });
  Future<Map<String, dynamic>> detail(TreasuryListKind kind, String id);
  Future<Map<String, dynamic>> instructions();
  Future<ClientDocumentFile> exportReconciliation(String id);
  Future<TreasuryResult> execute(TreasuryCommand command, {String? targetId});
  Future<TreasuryResult?> recover();
  Future<TreasuryResult> retrySame();
  Future<TreasuryResult> uploadClaim(
    Map<String, dynamic> metadata,
    XFile file, {
    String? claimId,
  });
  Future<TreasuryResult> uploadEvidence({
    required String requestId,
    required String accountId,
    required String purpose,
    required XFile file,
  });
  Future<Map<String, dynamic>> preview(
    String receiptId,
    Map<String, dynamic> input,
  );
  Future<Uint8List> content({
    String? claimId,
    int? version,
    String? evidenceId,
    required String mediaType,
    String? digest,
    int? byteCount,
  });
  void dispose();
}

abstract interface class CollectorSurplusRepository
    implements TreasuryRepository {
  CollectorSurplusWorkspace? get surplusWorkspace;
  Future<CollectorSurplusWorkspace> loadCollectorSurplus({
    CollectorSurplusKind kind = CollectorSurplusKind.credits,
    String? accountId,
    String? mode,
    int limit = 50,
    int offset = 0,
  });
  Future<Map<String, dynamic>> collectorSurplusDetail(
    CollectorSurplusKind kind,
    String id,
  );
  Future<CollectorSettlementPreview> collectorSettlementPreview(
    String remittanceId,
    String accountId, {
    String? retainedExceptionId,
    int? retainedExceptionVersion,
  });
  Future<ClientDocumentFile> exportCollectorSurplus({
    CollectorSurplusKind kind = CollectorSurplusKind.credits,
    String? accountId,
  });
}

class SpinaTreasuryRepository implements CollectorSurplusRepository {
  SpinaTreasuryRepository({
    required UserSession session,
    required this.deviceId,
    http.Client? client,
    UserSession? Function()? getSession,
    bool Function()? isOnline,
    TreasuryJournal? journal,
    PrivateImageStore? images,
  }) : _initial = session,
       _getSession = getSession ?? (() => session),
       _isOnline = isOnline ?? (() => true),
       _client = client ?? http.Client(),
       _ownsClient = client == null,
       _journal = journal ?? const SecureTreasuryJournal(),
       _images = images ?? PrivateImageStore(directory: _privateDirectory),
       _initialScope = _scope(session);
  final UserSession _initial;
  final String deviceId;
  final UserSession? Function() _getSession;
  final bool Function() _isOnline;
  final http.Client _client;
  final bool _ownsClient;
  final TreasuryJournal _journal;
  final PrivateImageStore _images;
  final String _initialScope;
  TreasuryWorkspace? _workspace;
  CollectorSurplusWorkspace? _surplus;
  String? _surplusAuthorization;
  String? _surplusMode;
  CollectorSettlementPreview? _settlementPreview;
  @override
  CollectorSurplusWorkspace? get surplusWorkspace => _surplus;
  Map<String, dynamic>? _attempt;
  Map<String, dynamic>? _previewInput, _lastPreview;
  bool _busy = false, _disposed = false, _denied = false;
  String? _authorization;
  @override
  TreasuryWorkspace? get workspace => _workspace;
  @override
  String? get pendingRequestId => _attempt?['request_id'] as String?;
  @override
  bool get busy => _busy;
  @override
  bool get denied => _denied;
  static String _scope(UserSession s) => canonicalTreasury({
    'user': s.userId,
    'role': s.rawRole,
    'roles': s.roles,
    'permissions': s.permissions.toList()..sort(),
  });
  static Future<Directory> _privateDirectory() async => Directory(
    paths.join(
      await (await getApplicationSupportDirectory()).resolveSymbolicLinks(),
      'gilbic_treasury_submitted_files_v1',
    ),
  );
  void _current() {
    final session = _getSession();
    if (_disposed ||
        session == null ||
        session.isExpired ||
        session.accessToken.isEmpty ||
        _scope(session) != _initialScope) {
      _workspace = null;
      _denied = true;
      throw const TreasuryAccessChanged();
    }
  }

  void _online() {
    _current();
    if (!_isOnline()) {
      throw StateError(
        'Connect to the internet before sending or checking a request.',
      );
    }
  }

  Future<void> _redact() async {
    _workspace = null;
    _surplus = null;
    _settlementPreview = null;
    _attempt = null;
    _lastPreview = null;
    _previewInput = null;
    _denied = true;
    try {
      await _journal.clear();
    } finally {
      // A foreign or corrupt restored journal can have private files even
      // before it becomes this repository's in-memory attempt.
      await _images.cleanup();
    }
  }

  Map<String, String> _headers() => {
    'Accept': 'application/json',
    'Authorization': 'Bearer ${_getSession()!.accessToken}',
    'X-Device-Id': deviceId,
  };
  Future<Object?> _request(
    String path, {
    String method = 'GET',
    Object? body,
    Uint8List? bytes,
    Map<String, String> headers = const {},
  }) async {
    _current();
    late http.Response response;
    try {
      final uri = ApiConfig.endpoint('/api/v1/treasury$path');
      final h = {
        ..._headers(),
        ...headers,
        if (body != null) 'Content-Type': 'application/json',
      };
      response = method == 'GET'
          ? await _client.get(uri, headers: h)
          : await _client.post(
              uri,
              headers: h,
              body: bytes ?? (body == null ? null : jsonEncode(body)),
            );
    } on Exception {
      _current();
      rethrow;
    }
    _current();
    if (response.statusCode == 401 || response.statusCode == 403) {
      await _redact();
      throw const TreasuryAccessChanged();
    }
    late Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Exception {
      throw const TreasuryUncertain();
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = payload['detail'];
      final detailMap = detail is Map ? detail : const {};
      throw SpinaApiException(
        detailMap['message'] as String? ??
            'The server could not confirm this request. Refresh and review.',
        statusCode: response.statusCode,
        code: detailMap['code'] as String?,
      );
    }
    if (payload['success'] != true || !payload.containsKey('data')) {
      throw const TreasuryUncertain();
    }
    return unwrapSpinaData(payload, statusCode: response.statusCode);
  }

  @override
  Future<TreasuryWorkspace> loadWorkspace() async {
    final value = TreasuryWorkspace.fromJson(
      treasuryObject(await _request('/workspace')),
      expectedUserId: _initial.userId,
    );
    _current();
    if (_authorization != null && _authorization != value.authorization) {
      await _redact();
      throw const TreasuryAccessChanged();
    }
    _authorization = value.authorization;
    _workspace = value;
    return value;
  }

  void _permitted(String action, String accountId) {
    _current();
    final w = _workspace;
    if (w == null || !w.capability(action)) {
      throw StateError(
        'This action is disabled or unavailable for your access.',
      );
    }
    final account = w.account(accountId);
    if (account == null && action == 'account_configure') return;
    if (account?.permits(action) != true) throw const TreasuryAccessChanged();
  }

  @override
  Future<void> restoreAttempt() async {
    _current();
    if (_busy || _attempt != null) return;
    final raw = await _journal.read();
    _current();
    if (raw == null) return;
    late final Map<String, dynamic> held;
    try {
      held = treasuryObject(jsonDecode(raw));
      if (held['contract_version'] != 1 ||
          held['scope'] != _initialScope ||
          held['external_device_id'] != deviceId ||
          !treasuryUuid(held['actor_user_id']) ||
          held['actor_user_id'] != _initial.userId ||
          !treasuryUuid(held['device_id']) ||
          held['surplus'] == true &&
              !['own', 'staff'].contains(held['surplus_mode']) ||
          !treasuryUuid(held['request_id']) ||
          !treasuryUuid(held['account_id']) ||
          held['path'] is! String ||
          held['action'] is! String) {
        throw const TreasuryAccessChanged();
      }
    } on Exception {
      await _redact();
      throw const TreasuryAccessChanged();
    }
    // The shared journal may belong to either workspace. Retain the same-scope
    // attempt while the server is unavailable; missing cached authority is not
    // evidence that the submitted write or its private bytes are foreign.
    _attempt = treasuryObject(immutableTreasury(held));
    await _authorizeAttempt(held);
  }

  Future<void> _authorizeAttempt(Map<String, dynamic> held) async {
    final actor = held['surplus'] == true
        ? (await loadCollectorSurplus(
            mode: held['surplus_mode'] as String,
          )).actor
        : (await loadWorkspace()).actor;
    if (actor.userId != held['actor_user_id'] ||
        actor.deviceId != held['device_id']) {
      await _redact();
      throw const TreasuryAccessChanged();
    }
  }

  @override
  Future<TreasuryPage> list(
    TreasuryListKind kind, {
    String? accountId,
    String? clientId,
    int limit = 50,
    int offset = 0,
  }) async {
    if (limit < 1 ||
        limit > 100 ||
        offset < 0 ||
        offset > 100000 ||
        accountId == null && kind != TreasuryListKind.claims) {
      throw ArgumentError('Choose a valid Treasury page.');
    }
    if (accountId != null) {
      requireTreasuryId(accountId);
      if ([
            TreasuryListKind.events,
            TreasuryListKind.receipts,
            TreasuryListKind.reconciliations,
            TreasuryListKind.openings,
          ].contains(kind) &&
          _workspace?.account(accountId)?.balance == null) {
        throw const TreasuryAccessChanged();
      }
    }
    if (clientId != null) requireTreasuryId(clientId);
    final query = Uri(
      queryParameters: {
        'limit': '$limit',
        'offset': '$offset',
        if (clientId != null) 'client_id': clientId,
        if (accountId != null && kind == TreasuryListKind.claims)
          'account_id': accountId,
      },
    ).query;
    return TreasuryPage.fromJson(
      treasuryObject(
        await _request(
          '${accountId == null || kind == TreasuryListKind.claims ? '' : '/accounts/$accountId'}/${kind.name}?$query',
        ),
      ),
      limit: limit,
      offset: offset,
    );
  }

  @override
  Future<Map<String, dynamic>> detail(TreasuryListKind kind, String id) async {
    if (kind == TreasuryListKind.events || kind == TreasuryListKind.openings) {
      throw ArgumentError('Choose an available detail.');
    }
    requireTreasuryId(id);
    final data = treasuryObject(await _request('/${kind.name}/$id'));
    if (data['id'] != id) {
      throw const FormatException(
        'The selected record could not be confirmed.',
      );
    }
    validateTreasuryFinancialProjection(data);
    return treasuryObject(immutableTreasury(data));
  }

  @override
  Future<Map<String, dynamic>> instructions() async {
    final value = treasuryObject(await _request('/instructions'));
    if (value['items'] is! List ||
        value['total_count'] is! int ||
        (value['items'] as List).length != value['total_count']) {
      throw const FormatException('Payment instructions are unavailable.');
    }
    return value;
  }

  @override
  Future<ClientDocumentFile> exportReconciliation(String id) async {
    _online();
    requireTreasuryId(id);
    await loadWorkspace();
    final record = await detail(TreasuryListKind.reconciliations, id);
    final account = _workspace!.account(record['account_id'] as String? ?? '');
    if (account?.balance == null ||
        account?.permits('reconciliation_observe') != true ||
        _workspace?.capability('reconciliation_observe') != true) {
      throw const TreasuryAccessChanged();
    }
    final response = await _client.get(
      ApiConfig.endpoint('/api/v1/treasury/reconciliations/$id/export'),
      headers: _headers(),
    );
    _current();
    if (response.statusCode == 401 || response.statusCode == 403) {
      await _redact();
      throw const TreasuryAccessChanged();
    }
    if (response.statusCode != 200 ||
        response.headers['content-type']?.split(';').first !=
            'application/json' ||
        response.headers['cache-control']?.contains('no-store') != true ||
        response.bodyBytes.length > 20 * 1024 * 1024) {
      throw const FormatException(
        'The private reconciliation export is unavailable.',
      );
    }
    final data = treasuryObject(jsonDecode(utf8.decode(response.bodyBytes)));
    final exportedAccount = treasuryObject(data['account']);
    final exportedRecord = treasuryObject(data['reconciliation']);
    if (data['contract_version'] != 1 ||
        exportedAccount['id'] != account!.id ||
        exportedAccount['ledger_context_id'] != account.ledgerContextId ||
        exportedAccount['currency'] != 'PHP' ||
        exportedRecord['id'] != id ||
        exportedRecord['account_id'] != account.id ||
        data['ledger'] is! List ||
        data['exceptions'] is! Map) {
      throw const FormatException(
        'The private export does not match the selected reconciliation.',
      );
    }
    validateTreasuryFinancialProjection(data);
    return ClientDocumentFile(
      filename: 'treasury-private-reconciliation-$id.json',
      bytes: Uint8List.fromList(response.bodyBytes),
      mediaType: 'application/json',
    );
  }

  Map<String, dynamic> _held({
    required String requestId,
    required String action,
    required String accountId,
    required String path,
    Map<String, dynamic>? body,
    String? targetId,
    Map<String, dynamic>? upload,
  }) {
    final account = _workspace!.account(accountId);
    return {
      'contract_version': 1,
      'scope': _initialScope,
      'external_device_id': deviceId,
      'actor_user_id': _workspace!.actor.userId,
      'device_id': _workspace!.actor.deviceId,
      'request_id': requestId,
      'action': action,
      'account_id': accountId,
      'ledger_context_id':
          account?.ledgerContextId ?? body?['ledger_context_id'],
      'path': path,
      'body': body,
      'target_id': targetId,
      'upload': upload,
    };
  }

  Future<void> _hold(Map<String, dynamic> value) async {
    await _journal.write(jsonEncode(value));
    _current();
    _attempt = treasuryObject(immutableTreasury(value));
  }

  @override
  Future<CollectorSurplusWorkspace> loadCollectorSurplus({
    CollectorSurplusKind kind = CollectorSurplusKind.credits,
    String? accountId,
    String? mode,
    int limit = 50,
    int offset = 0,
  }) async {
    if (limit < 1 || limit > 100 || offset < 0 || offset > 100000) {
      throw ArgumentError('Choose a valid history page.');
    }
    if (accountId != null) requireTreasuryId(accountId);
    final changedMode = mode != null && mode != _surplusMode;
    if (mode != null && !['own', 'staff'].contains(mode)) {
      throw ArgumentError('Choose an authorized mode.');
    }
    if (changedMode &&
        _attempt != null &&
        !(_attempt!['surplus'] == true && _attempt!['surplus_mode'] == mode)) {
      throw StateError('Recover the pending phase before changing mode.');
    }
    final requestedMode = mode ?? _surplusMode;
    final query = Uri(
      queryParameters: {
        'kind': kind.name,
        'limit': '$limit',
        'offset': '$offset',
        if (accountId != null) 'account_id': accountId,
        if (requestedMode != null) 'mode': requestedMode,
      },
    ).query;
    final value = CollectorSurplusWorkspace(
      treasuryObject(await _request('/collector-surplus/workspace?$query')),
      expectedUserId: _initial.userId,
      kind: kind,
      limit: limit,
      offset: offset,
    );
    _current();
    if (!changedMode &&
        accountId == null &&
        _surplusAuthorization != null &&
        _surplusAuthorization != value.authorization) {
      await _redact();
      throw const TreasuryAccessChanged();
    }
    if (accountId == null) _surplusAuthorization = value.authorization;
    if (requestedMode != null && value.mode != requestedMode) {
      throw const TreasuryAccessChanged();
    }
    _surplusMode = requestedMode;
    _surplus = value;
    return value;
  }

  @override
  Future<Map<String, dynamic>> collectorSurplusDetail(
    CollectorSurplusKind kind,
    String id,
  ) async {
    requireTreasuryId(id);
    if (kind == CollectorSurplusKind.remittances ||
        kind == CollectorSurplusKind.openings) {
      throw ArgumentError('Use the current authorized workspace record.');
    }
    final row = treasuryObject(
      await _request(
        '/collector-surplus/${kind.name}/$id${_surplusMode == null ? '' : '?mode=$_surplusMode'}',
      ),
    );
    if (row['id'] != id) {
      throw const FormatException('The selected surplus record changed.');
    }
    validateCollectorRecord(
      row,
      kind,
      ownUserId: _surplus?.mode == 'own' ? _initial.userId : null,
    );
    return treasuryObject(immutableTreasury(row));
  }

  @override
  Future<CollectorSettlementPreview> collectorSettlementPreview(
    String remittanceId,
    String accountId, {
    String? retainedExceptionId,
    int? retainedExceptionVersion,
  }) async {
    _online();
    requireTreasuryId(remittanceId);
    if ((retainedExceptionId == null) != (retainedExceptionVersion == null)) {
      throw const FormatException('Select the exact retained cash version.');
    }
    if (retainedExceptionId != null) {
      requireTreasuryId(retainedExceptionId);
      if (retainedExceptionVersion! < 1) {
        throw const FormatException('Invalid retained cash version.');
      }
    }
    final w = await loadCollectorSurplus(
      kind: CollectorSurplusKind.remittances,
      accountId: accountId,
    );
    final account = w.account(accountId);
    if (account == null) throw const TreasuryAccessChanged();
    final value = CollectorSettlementPreview(
      treasuryObject(
        await _request(
          '/collector-surplus/remittances/$remittanceId/preview',
          method: 'POST',
          body: {
            'account_id': account.id,
            'expected_version': account.version,
            'credit_application_id': null,
            'credit_application_version': null,
            if (retainedExceptionId != null) ...{
              'retained_exception_id': retainedExceptionId,
              'retained_exception_version': retainedExceptionVersion,
            },
          },
        ),
      ),
      userId: w.actor.userId,
      deviceId: w.actor.deviceId,
      remittanceId: remittanceId,
      account: account,
      retainedExceptionId: retainedExceptionId,
      retainedExceptionVersion: retainedExceptionVersion,
    );
    _settlementPreview = value;
    return value;
  }

  void _collectorPermitted(TreasuryAction action, String accountId) {
    _current();
    final w = _surplus;
    if (w == null || !w.capability(collectorCapability(action))) {
      throw StateError(
        'This surplus action is disabled or unavailable for your current authority.',
      );
    }
    if (collectorOwnActions.contains(action)) {
      if (w.mode != 'own') throw const TreasuryAccessChanged();
    } else if (w.mode != 'staff' ||
        w.account(accountId)?.permits(collectorCapability(action)) != true) {
      throw const TreasuryAccessChanged();
    }
  }

  Future<TreasuryResult> _executeCollectorSurplus(
    TreasuryCommand command,
  ) async {
    _online();
    if (_busy || _attempt != null) {
      throw StateError(
        'Check the exact pending request before another submission.',
      );
    }
    _busy = true;
    try {
      final w = await loadCollectorSurplus();
      final body = command.toJson();
      final records = <String, dynamic>{};
      for (final entry in <String, CollectorSurplusKind>{
        'credit': CollectorSurplusKind.credits,
        'case': CollectorSurplusKind.cases,
        'count': CollectorSurplusKind.counts,
        'exception': CollectorSurplusKind.exceptions,
        'action': CollectorSurplusKind.actions,
        'collector_request': CollectorSurplusKind.requests,
      }.entries) {
        final id = body['${entry.key}_id'];
        if (id == null) continue;
        final row = await collectorSurplusDetail(entry.value, id as String);
        if (row['version'] != body['${entry.key}_version']) {
          throw StateError('The source changed. Refresh and review again.');
        }
        records[entry.key == 'action'
                ? 'action_record'
                : entry.key == 'collector_request'
                ? 'request'
                : entry.key] =
            row;
      }
      if (command.action == TreasuryAction.collectorSurplusOpeningActivate) {
        Map<String, dynamic>? anchor;
        for (var offset = 0; offset <= 100000; offset += 100) {
          final page = await loadCollectorSurplus(
            kind: CollectorSurplusKind.openings,
            accountId: command.accountId,
            mode: 'staff',
            limit: 100,
            offset: offset,
          );
          anchor = page.page.items
              .where((r) => r['id'] == body['anchor_id'])
              .firstOrNull;
          if (anchor != null || !page.page.hasMore) break;
        }
        if (anchor == null ||
            anchor['version'] != body['anchor_version'] ||
            anchor['status'] != 'draft') {
          throw StateError(
            'The opening anchor changed. Refresh and review again.',
          );
        }
        records['opening_anchor'] = anchor;
      }
      if (command.action == TreasuryAction.collectorSurplusOpeningPrepare) {
        final choices = w.raw['opening_choices'] as List? ?? [];
        if (!choices.whereType<Map>().any(
          (o) =>
              o['id'] == body['opening_id'] &&
              o['version'] == body['opening_version'] &&
              o['account_id'] == command.accountId &&
              o['status'] == 'active',
        )) {
          throw StateError(
            'The active opening changed. Refresh and review again.',
          );
        }
        if (!(w.raw['collector_choices'] as List).whereType<Map>().any(
          (c) => c['id'] == body['collector_user_id'],
        )) {
          throw const TreasuryAccessChanged();
        }
      }
      Map<String, dynamic>? origin =
          records['credit'] as Map<String, dynamic>? ??
          records['exception'] as Map<String, dynamic>?;
      final accountId = collectorOwnActions.contains(command.action)
          ? requireTreasuryId(
              origin?['origin_account_id'] ?? origin?['account_id'],
            )
          : command.accountId;
      _collectorPermitted(command.action, accountId);
      final account = w.account(accountId);
      if (!collectorOwnActions.contains(command.action) &&
          account?.version != command.expectedVersion) {
        throw StateError('Account changed. Refresh and review before sending.');
      }
      final context = collectorOwnActions.contains(command.action)
          ? requireTreasuryId(origin?['ledger_context_id'])
          : account!.ledgerContextId;
      for (final row in records.values.whereType<Map<String, dynamic>>()) {
        if (row['ledger_context_id'] != null &&
            row['ledger_context_id'] != context) {
          throw const TreasuryAccessChanged();
        }
      }
      if (body['action_id'] != null && body['event_id'] != null) {
        final a = records['action_record'] as Map;
        if (a['event_id'] != body['event_id'] ||
            a['event_version'] != body['event_version'] ||
            body['reviewed_amount'] != null &&
                a['amount'] != body['reviewed_amount']) {
          throw StateError(
            'Review the unchanged actual return event and principal.',
          );
        }
      }
      if (command.action == TreasuryAction.collectorCountRecord ||
          command.action == TreasuryAction.collectorCountAccept) {
        final count = records['count'] as Map?;
        final remittance = body['remittance_id'] ?? count?['remittance_id'];
        final reviewed = _settlementPreview;
        if (command.action == TreasuryAction.collectorCountRecord &&
            (reviewed == null ||
                reviewed.raw['remittance_id'] != remittance ||
                reviewed.raw['retained_exception_id'] !=
                    body['retained_exception_id'] ||
                reviewed.raw['retained_exception_version'] !=
                    body['retained_exception_version'] ||
                reviewed.digest != body['source_digest'])) {
          throw StateError(
            'Review the current receiving snapshot before counting.',
          );
        }
        final fresh = await collectorSettlementPreview(
          remittance as String,
          accountId,
          retainedExceptionId:
              (count ?? body)['retained_exception_id'] as String?,
          retainedExceptionVersion:
              (count ?? body)['retained_exception_version'] as int?,
        );
        if (!fresh.canCount ||
            fresh.digest != body['source_digest'] ||
            fresh.raw['account_version'] != command.expectedVersion) {
          throw StateError(
            'Sources changed or count is blocked. Review again.',
          );
        }
        records['remittance'] = {
          'id': remittance,
          'collector_user_id': fresh.raw['collector_user_id'],
          'retained_cash_amount': fresh.raw['retained_cash_amount'] ?? '0.00',
        };
        if (count != null && count['disposition'] != 'counted_ready') {
          throw StateError('A short count cannot accept the full remittance.');
        }
      }
      if (body['source_digest'] != null &&
          records['case'] != null &&
          records['case']['source_digest'] != body['source_digest']) {
        throw StateError('The identification source changed. Review again.');
      }
      await _hold({
        'contract_version': 1,
        'surplus': true,
        'surplus_mode': w.mode,
        'scope': _initialScope,
        'external_device_id': deviceId,
        'actor_user_id': w.actor.userId,
        'device_id': w.actor.deviceId,
        'request_id': command.requestId,
        'action': command.action.code,
        'account_id': accountId,
        'ledger_context_id': context,
        'path': '/actions',
        'body': body,
        'surplus_records': records,
        'upload': null,
      });
      return await _send();
    } finally {
      _busy = false;
    }
  }

  @override
  Future<ClientDocumentFile> exportCollectorSurplus({
    CollectorSurplusKind kind = CollectorSurplusKind.credits,
    String? accountId,
  }) async {
    final w = await loadCollectorSurplus(kind: kind, accountId: accountId);
    final query = Uri(
      queryParameters: {
        'kind': kind.name,
        if (accountId != null) 'account_id': accountId,
        if (_surplusMode != null) 'mode': _surplusMode!,
      },
    ).query;
    final response = await _client.get(
      ApiConfig.endpoint('/api/v1/treasury/collector-surplus/export?$query'),
      headers: _headers(),
    );
    _current();
    if ([401, 403].contains(response.statusCode)) {
      await _redact();
      throw const TreasuryAccessChanged();
    }
    if (response.statusCode != 200 ||
        response.headers['content-type']?.split(';').first !=
            'application/json') {
      throw const FormatException('The private report is unavailable.');
    }
    final envelope = treasuryObject(
      jsonDecode(utf8.decode(response.bodyBytes)),
    );
    if (envelope['success'] != true ||
        w.mode == 'own' &&
            envelope.keys.any((key) => !{'success', 'data'}.contains(key))) {
      throw const FormatException('The private report is unavailable.');
    }
    final exported = treasuryObject(envelope['data']);
    validateCollectorWorkspaceMetadata(
      exported,
      expectedUserId: _initial.userId,
    );
    final page = exported['items'];
    if (exported['collector_surplus_contract_version'] != 1 ||
        exported['mode'] != w.mode ||
        treasuryObject(exported['actor'])['user_id'] != w.actor.userId ||
        treasuryObject(exported['actor'])['device_id'] != w.actor.deviceId ||
        exported['kind'] != kind.name ||
        page is! List ||
        exported['has_more'] != false ||
        exported['total_count'] != page.length) {
      throw const FormatException('The private report scope is incomplete.');
    }
    validateCollectorProjection({
      'items': page,
      'totals': exported['totals'],
    }, ownUserId: w.mode == 'own' ? _initial.userId : null);
    for (final row in page) {
      validateCollectorRecord(
        treasuryObject(row),
        kind,
        ownUserId: w.mode == 'own' ? _initial.userId : null,
      );
    }
    return ClientDocumentFile(
      filename: 'collector-excess-${kind.name}.json',
      bytes: Uint8List.fromList(response.bodyBytes),
      mediaType: 'application/json',
    );
  }

  TreasuryResult _validate(Object? raw, Map<String, dynamic> held) {
    try {
      if (held['surplus'] == true) return validateCollectorOutcome(raw, held);
      final value = TreasuryResult.fromJson(treasuryObject(raw));
      final result = value.result;
      if (value.raw['request_id'] != held['request_id'] ||
          value.raw['action'] != held['action'] ||
          result['actor_user_id'] != held['actor_user_id'] ||
          result['device_id'] != held['device_id'] ||
          result['account_id'] != held['account_id'] ||
          result['ledger_context_id'] != held['ledger_context_id'] ||
          held['target_id'] != null && value.targetId != held['target_id']) {
        throw const TreasuryUncertain();
      }
      if (value.status == 'saved') {
        final body = held['body'] as Map?;
        if (body != null) {
          final entity = switch (held['action']) {
            'receipt_verify' => result['receipt'],
            'disbursement_record' || 'transfer_record' => result['event'],
            'opening_prepare' => result['opening'],
            _ => null,
          };
          if (body.containsKey('amount') &&
              entity != null &&
              (entity is! Map || entity['amount'] != body['amount'])) {
            throw const TreasuryUncertain();
          }
          if (held['collector_source'] is Map) {
            validateCollectorDebitOutcome(value, held);
          }
          if (held['action'] == 'receipt_verify' &&
              (result['receipt'] is! Map ||
                  (result['receipt'] as Map)['client_id'] !=
                      body['client_id'])) {
            throw const TreasuryUncertain();
          }
          if (held['action'] == 'receipt_apply') {
            final application = result['application'];
            final ids = application is Map
                ? application['transaction_ids']
                : null;
            if (application is! Map ||
                application['status'] != 'recorded' ||
                application['amount'] != body['total_amount'] ||
                ids is! List ||
                ids.isEmpty ||
                ids.any((id) => !treasuryUuid(id)) ||
                ids.toSet().length != ids.length) {
              throw const TreasuryUncertain();
            }
          }
        }
        final keys = [
          'account',
          'claim',
          'receipt',
          'event',
          'opening',
          'reconciliation',
          'transfer',
          'evidence',
        ];
        if (!keys.any(
          (k) =>
              result[k] is Map &&
              (result[k] as Map)['id'] == value.targetId &&
              ((result[k] as Map)['version'] == null ||
                  (result[k] as Map)['version'] == value.version),
        )) {
          throw const TreasuryUncertain();
        }
        final upload = held['upload'];
        if (upload is Map) {
          final record = held['action'] == 'evidence_upload'
              ? result['evidence']
              : (result['claim'] as Map?)?['current_version'];
          if (record is! Map ||
              record['sha256'] != upload['sha256'] ||
              record['media_type'] != upload['media_type'] ||
              record['byte_count'] != upload['byte_count']) {
            throw const TreasuryUncertain();
          }
          final metadata = upload['metadata'];
          if (metadata is Map) {
            final claim = result['claim'];
            if (claim is! Map ||
                claim['account_id'] != metadata['account_id'] ||
                claim['client_id'] != metadata['client_id'] ||
                record['amount'] != metadata['amount'] ||
                record['reference'] != metadata['reference'] ||
                record['account_version'] != metadata['account_version'] ||
                canonicalTreasury(record['loan_ids']) !=
                    canonicalTreasury(metadata['loan_ids'])) {
              throw const TreasuryUncertain();
            }
          } else if (record['account_id'] != held['account_id'] ||
              record['purpose'] != upload['purpose']) {
            throw const TreasuryUncertain();
          }
        }
      }
      return value;
    } on Exception {
      throw const TreasuryUncertain();
    }
  }

  Future<TreasuryResult> _send() async {
    final held = _attempt!;
    final heldUpload = held['upload'];
    try {
      final upload = held['upload'] as Map?;
      Uint8List? bytes;
      final headers = <String, String>{};
      if (upload != null) {
        final file = XFile(upload['path'] as String);
        if (!await _images.owns(file)) throw const TreasuryUncertain();
        bytes = await _images.use(file, (f) => f.readAsBytes());
        if (bytes!.length != upload['byte_count'] ||
            sha256.convert(bytes).toString() != upload['sha256']) {
          throw const TreasuryUncertain();
        }
        headers['Content-Type'] = upload['media_type'] as String;
        if (upload['metadata'] != null) {
          headers['X-Treasury-Metadata'] = base64Encode(
            utf8.encode(jsonEncode(upload['metadata'])),
          );
        }
      }
      _online();
      final value = _validate(
        await _request(
          held['path'] as String,
          method: 'POST',
          body: held['body'],
          bytes: bytes,
          headers: headers,
        ),
        held,
      );
      if (heldUpload != null) await _images.cleanup();
      await _journal.clear();
      _attempt = null;
      return value;
    } on TreasuryAccessChanged {
      rethrow;
    } on Exception catch (error) {
      if (error is SpinaApiException &&
          error.statusCode != null &&
          error.statusCode! < 500) {
        if (heldUpload != null) await _images.cleanup();
        await _journal.clear();
        _attempt = null;
        rethrow;
      }
      throw const TreasuryUncertain();
    }
  }

  String? _commandTarget(TreasuryCommand command) {
    final body = command.toJson();
    return switch (command.action) {
      TreasuryAction.accountConfigure ||
      TreasuryAction.accountGrant => command.accountId,
      TreasuryAction.openingActivate => body['opening_id'] as String,
      TreasuryAction.claimReview => body['claim_id'] as String,
      TreasuryAction.receiptApply ||
      TreasuryAction.receiptApplicationReverse => body['receipt_id'] as String,
      TreasuryAction.movementClassify ||
      TreasuryAction.movementCorrect => body['event_id'] as String,
      TreasuryAction.transferRecord => body['transfer_id'] as String,
      TreasuryAction.reconciliationObserve ||
      TreasuryAction.reconciliationMatch ||
      TreasuryAction.reconciliationClose ||
      TreasuryAction.reconciliationSupersede =>
        body['reconciliation_id'] as String,
      _ => null,
    };
  }

  @override
  Future<TreasuryResult> execute(
    TreasuryCommand command, {
    String? targetId,
  }) async {
    if (isCollectorSurplusAction(command.action)) {
      return _executeCollectorSurplus(command);
    }
    _online();
    if (_busy || _attempt != null) {
      throw StateError(
        'Check the unchanged pending request before another action.',
      );
    }
    _busy = true;
    try {
      await loadWorkspace();
      _permitted(command.action.code, command.accountId);
      final account = _workspace!.account(command.accountId);
      if (account != null &&
          ![
            TreasuryAction.receiptApply,
            TreasuryAction.receiptApplicationReverse,
          ].contains(command.action) &&
          account.version != command.expectedVersion) {
        throw StateError('Account changed. Refresh and review before sending.');
      }
      if (command.action == TreasuryAction.receiptApply) {
        final p = _lastPreview;
        final body = command.toJson();
        if (p == null ||
            p['can_apply'] != true ||
            p['receipt_id'] != body['receipt_id'] ||
            p['digest'] != body['digest'] ||
            p['account_id'] != command.accountId ||
            p['receipt_version'] != command.expectedVersion ||
            applicationFields.any(
              (f) =>
                  canonicalTreasury(body[f.key]) !=
                  canonicalTreasury(_previewInput?[f.key]),
            )) {
          throw StateError(
            'Review a current unchanged server allocation before recording.',
          );
        }
      }
      Map<String, dynamic>? collectorSource;
      final submittedBody = command.toJson();
      if (command.action == TreasuryAction.disbursementRecord &&
          [
            'collector_surplus_return',
            'collector_custody_exception_return',
          ].contains(submittedBody['purpose'])) {
        await loadCollectorSurplus(mode: 'staff');
        collectorSource = await collectorSurplusDetail(
          CollectorSurplusKind.actions,
          requireTreasuryId(submittedBody['source_id']),
        );
        if (collectorSource['version'] != submittedBody['source_version'] ||
            collectorSource['status'] != 'reserved' ||
            collectorSource['amount'] != submittedBody['amount'] ||
            collectorSource['collector_user_id'] != submittedBody['payee_id'] ||
            collectorSource['paying_account_id'] != command.accountId ||
            collectorSource['ledger_context_id'] != account?.ledgerContextId ||
            submittedBody['direction'] != 'debit') {
          throw StateError(
            'The approved return changed. Refresh and review before recording an actual observation.',
          );
        }
      }
      final pending = _held(
        requestId: command.requestId,
        action: command.action.code,
        accountId: command.accountId,
        path: '/actions',
        body: submittedBody,
        targetId: targetId ?? _commandTarget(command),
      );
      if (collectorSource != null) {
        pending['collector_source'] = collectorSource;
      }
      await _hold(pending);
      return await _send();
    } finally {
      _busy = false;
    }
  }

  @override
  Future<TreasuryResult?> recover() async {
    _online();
    if (_busy) throw StateError('A request is already being checked.');
    if (_attempt == null) return null;
    _busy = true;
    try {
      await _authorizeAttempt(_attempt!);
      final held = _attempt!;
      final heldUpload = held['upload'];
      final raw = await _request('/requests/${held['request_id']}');
      if (raw == null) return null;
      final value = _validate(raw, held);
      if (heldUpload != null) await _images.cleanup();
      await _journal.clear();
      _attempt = null;
      return value;
    } finally {
      _busy = false;
    }
  }

  @override
  Future<TreasuryResult> retrySame() async {
    _online();
    if (_busy || _attempt == null) {
      throw StateError('There is no unchanged request to retry.');
    }
    _busy = true;
    try {
      await _authorizeAttempt(_attempt!);
      if (_attempt!['surplus'] == true) {
        // Recovery is read-only even after entry disable. Explicit resend still requires current capability.
        final action = TreasuryAction.fromCode(_attempt!['action'] as String);
        _collectorPermitted(action, _attempt!['account_id'] as String);
      } else {
        _permitted(
          _attempt!['action'] as String,
          _attempt!['account_id'] as String,
        );
      }
      return await _send();
    } finally {
      _busy = false;
    }
  }

  Future<TreasuryResult> _upload({
    required String action,
    required String requestId,
    required String accountId,
    required String path,
    required XFile file,
    Map<String, dynamic>? metadata,
    String? targetId,
    String? purpose,
  }) async {
    _online();
    if (_busy || _attempt != null) {
      throw StateError(
        'Check the unchanged pending request before another upload.',
      );
    }
    _busy = true;
    try {
      await loadWorkspace();
      _permitted(action, accountId);
      if (metadata != null) {
        if (_workspace!.account(accountId)?.version !=
            metadata['account_version']) {
          throw StateError(
            'Receiving account changed. Refresh and review the proof before sending.',
          );
        }
        if (_workspace!.raw.containsKey('borrower_choices')) {
          final choices = (_workspace!.raw['borrower_choices'] as List)
              .whereType<Map<String, dynamic>>();
          final borrower = choices
              .where(
                (r) =>
                    r['client_id'] == metadata['client_id'] &&
                    (r['allowed_account_ids'] as List? ?? []).contains(
                      accountId,
                    ),
              )
              .firstOrNull;
          if (borrower == null ||
              action == 'claim_submit' &&
                  (metadata['loan_ids'] as List).any(
                    (id) => !(borrower['loans'] as List? ?? [])
                        .whereType<Map<String, dynamic>>()
                        .any((loan) => loan['loan_id'] == id),
                  )) {
            throw StateError(
              'Current borrower or loan scope changed. Refresh your own portfolio or assigned route before sending.',
            );
          }
        }
      }
      requireTreasuryId(requestId);
      final type = await treasuryMediaType(file);
      final retained = await _images.retain(file);
      final bytes = await _images.use(retained, (f) => f.readAsBytes());
      _online();
      await _hold(
        _held(
          requestId: requestId,
          action: action,
          accountId: accountId,
          path: path,
          targetId: targetId,
          upload: {
            'path': retained.path,
            'name': retained.name,
            'media_type': type,
            'byte_count': bytes.length,
            'sha256': sha256.convert(bytes).toString(),
            'metadata': metadata,
            'purpose': purpose,
          },
        ),
      );
      return await _send();
    } finally {
      _busy = false;
    }
  }

  @override
  Future<TreasuryResult> uploadClaim(
    Map<String, dynamic> metadata,
    XFile file, {
    String? claimId,
  }) async {
    final allowed = [
      'request_id',
      'account_id',
      'account_version',
      'client_id',
      'loan_ids',
      'amount',
      'reference',
      'claimed_at',
      'sender_note',
      'expected_version',
    ];
    if (metadata.keys.any((k) => !allowed.contains(k))) {
      throw const FormatException('Invalid payment proof metadata.');
    }
    for (final key in ['request_id', 'account_id', 'client_id']) {
      requireTreasuryId(metadata[key]);
    }
    TreasuryMoney(metadata['amount'], positive: true);
    const TreasuryField(
      'loans',
      'Loan choices',
      TreasuryFieldKind.ids,
    ).parse(metadata['loan_ids']);
    const TreasuryField(
      'date',
      'Sent time',
      timeKind,
    ).parse(metadata['claimed_at']);
    const TreasuryField(
      'reference',
      'Reference',
      textKind,
      maxLength: 200,
    ).parse(metadata['reference']);
    if (metadata['account_version'] is! int ||
        metadata['account_version'] < 1 ||
        metadata['sender_note'] != null &&
            (metadata['sender_note'] is! String ||
                (metadata['sender_note'] as String).length > 1000)) {
      throw const FormatException(
        'Refresh the receiving account and proof details.',
      );
    }
    if (claimId != null) {
      requireTreasuryId(claimId);
      if (metadata['expected_version'] is! int ||
          metadata['expected_version'] < 1) {
        throw const FormatException('Choose the current proof version.');
      }
    }
    return _upload(
      action: claimId == null ? 'claim_submit' : 'claim_version',
      requestId: metadata['request_id'] as String,
      accountId: metadata['account_id'] as String,
      path: claimId == null ? '/claims' : '/claims/$claimId/versions',
      file: file,
      metadata: treasuryObject(immutableTreasury(metadata)),
      targetId: claimId,
    );
  }

  @override
  Future<TreasuryResult> uploadEvidence({
    required String requestId,
    required String accountId,
    required String purpose,
    required XFile file,
  }) async {
    if (![
      'recipient',
      'opening',
      'statement',
      'correction',
    ].contains(purpose)) {
      throw const FormatException('Choose a valid evidence purpose.');
    }
    requireTreasuryId(accountId);
    return _upload(
      action: 'evidence_upload',
      requestId: requestId,
      accountId: accountId,
      path:
          '/evidence?${Uri(queryParameters: {'request_id': requestId, 'account_id': accountId, 'purpose': purpose}).query}',
      file: file,
      purpose: purpose,
    );
  }

  @override
  Future<Map<String, dynamic>> preview(
    String receiptId,
    Map<String, dynamic> input,
  ) async {
    _online();
    if (_busy || _attempt != null) {
      throw StateError(
        'Check the pending request before preparing another allocation.',
      );
    }
    _lastPreview = null;
    _previewInput = null;
    requireTreasuryId(receiptId);
    final body = <String, dynamic>{
      'expected_version': input['expected_version'],
    };
    if (body['expected_version'] is! int || body['expected_version'] < 1) {
      throw const FormatException('Refresh the verified receipt.');
    }
    for (final f in applicationFields) {
      final parsed = f.parse(input[f.key]);
      if (parsed != null) body[f.key] = parsed;
    }
    await loadWorkspace();
    final value = treasuryObject(
      await _request(
        '/receipts/$receiptId/allocation-preview',
        method: 'POST',
        body: body,
      ),
    );
    final account = _workspace!.account(value['account_id'] as String? ?? '');
    if (value['contract_version'] != 1 ||
        canonicalTreasury(value['actor']) !=
            canonicalTreasury(_workspace!.actor.toJson()) ||
        account?.permits('receipt_apply') != true ||
        value['ledger_context_id'] != account!.ledgerContextId ||
        value['receipt_id'] != receiptId ||
        value['receipt_version'] != body['expected_version'] ||
        value['mode'] != body['mode'] ||
        value['total_amount'] != body['total_amount'] ||
        value['effective_date'] != body['effective_date'] ||
        canonicalTreasury(value['loans']) != canonicalTreasury(body['loans']) ||
        value['allocations'] is! List ||
        value['blockers'] is! List ||
        value['can_apply'] is! bool ||
        value['can_apply'] == true &&
            ((value['allocations'] as List).isEmpty ||
                (value['blockers'] as List).isNotEmpty) ||
        value['can_apply'] == false &&
            ((value['blockers'] as List).isEmpty || value['digest'] != null)) {
      throw const TreasuryUncertain();
    }
    if (value['can_apply'] == true || value['digest'] != null) {
      const TreasuryField(
        'digest',
        'Digest',
        TreasuryFieldKind.digest,
      ).parse(value['digest']);
    }
    for (final blocker in value['blockers'] as List) {
      treasuryBlockerMessage(blocker);
    }
    TreasuryMoney(value['remaining_amount']);
    for (final raw in value['allocations'] as List) {
      final row = treasuryObject(raw);
      if (!(body['loans'] as List).any((l) => l['loan_id'] == row['loan_id']) ||
          row['covered_dates'] is! List ||
          row['component'] is! String ||
          row['loan_type'] is! String ||
          row['intent'] is! String) {
        throw const TreasuryUncertain();
      }
      for (final k in ['amount', 'applied_amount', 'unallocated_amount']) {
        TreasuryMoney(row[k]);
      }
    }
    _previewInput = treasuryObject(immutableTreasury(body));
    _lastPreview = treasuryObject(immutableTreasury(value));
    return _lastPreview!;
  }

  @override
  Future<Uint8List> content({
    String? claimId,
    int? version,
    String? evidenceId,
    required String mediaType,
    String? digest,
    int? byteCount,
  }) async {
    _current();
    if (!['application/pdf', 'image/png', 'image/jpeg'].contains(mediaType)) {
      throw const FormatException('Unsupported private file.');
    }
    final path = claimId != null
        ? '/claims/${requireTreasuryId(claimId)}/versions/$version/content'
        : '/evidence/${requireTreasuryId(evidenceId)}/content';
    if (claimId != null && (version == null || version < 1)) {
      throw const FormatException('Choose the exact proof version.');
    }
    final response = await _client.get(
      ApiConfig.endpoint('/api/v1/treasury$path'),
      headers: _headers(),
    );
    _current();
    if ([401, 403].contains(response.statusCode)) {
      await _redact();
      throw const TreasuryAccessChanged();
    }
    final bytes = response.bodyBytes;
    if (response.statusCode != 200 ||
        response.headers['content-type']?.split(';').first.trim() !=
            mediaType ||
        bytes.isEmpty ||
        bytes.length > 10485760 ||
        byteCount != null && bytes.length != byteCount ||
        digest != null && sha256.convert(bytes).toString() != digest) {
      throw const FormatException(
        'The private file is unavailable or incomplete.',
      );
    }
    return bytes;
  }

  @override
  void dispose() {
    _disposed = true;
    _workspace = null;
    _surplus = null;
    _settlementPreview = null;
    _lastPreview = null;
    _previewInput = null;
    _attempt = null;
    if (_ownsClient) _client.close();
  }
}

Future<String> treasuryMediaType(XFile file) async {
  final bytes = await file.readAsBytes();
  if (bytes.isEmpty || bytes.length > 10485760) {
    throw const FormatException('Choose a PDF, PNG or JPEG of at most 10 MiB.');
  }
  bool starts(List<int> magic) =>
      bytes.length >= magic.length &&
      List.generate(magic.length, (i) => bytes[i] == magic[i]).every((v) => v);
  final type = starts([0x25, 0x50, 0x44, 0x46, 0x2d])
      ? 'application/pdf'
      : starts([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])
      ? 'image/png'
      : starts([0xff, 0xd8, 0xff])
      ? 'image/jpeg'
      : null;
  if (type == null || file.mimeType != null && file.mimeType != type) {
    throw const FormatException(
      'The selected private file has an unsupported type.',
    );
  }
  return type;
}

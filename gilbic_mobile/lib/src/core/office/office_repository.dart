import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_photo.dart';
import 'package:http/http.dart' as http;

typedef OfficeRecord = Map<String, dynamic>;
const officeReviewPermission = 'client_onboarding.requirement.review';
const _clients = '/api/v1/management/clients';
const _intake = '/api/v1/management/onboarding/applicants';
const _loans = '/api/v1/management/first-loans';
final _uuid = RegExp(
  r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
);
final _hash = RegExp(r'^[0-9a-f]{64}$');

class OfficeIdentity {
  OfficeIdentity(this.session, this.deviceId);
  final UserSession session;
  final String deviceId;
  bool accessDenied = false;
  bool get allowed =>
      !accessDenied &&
      [AppRole.employee, AppRole.management].contains(session.role) &&
      session.hasPermission(officeReviewPermission);
  bool can(String permission, {bool management = false}) =>
      allowed &&
      session.hasPermission(permission) &&
      (!management || session.role == AppRole.management);
  bool get manager => can('lending.first_loan.approve', management: true);
  bool get releaser => can('lending.first_loan.release');
}

String officeRequestId() {
  final random = Random.secure();
  final bytes = List.generate(16, (_) => random.nextInt(256));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  final text = bytes.map((v) => v.toRadixString(16).padLeft(2, '0')).join();
  return '${text.substring(0, 8)}-${text.substring(8, 12)}-${text.substring(12, 16)}-${text.substring(16, 20)}-${text.substring(20)}';
}

void officeCheck(
  bool valid, [
  String message =
      'The server record does not match this selection. Reload the saved record.',
]) {
  if (!valid) throw SpinaApiException(message, code: 'invalid_office_record');
}

bool officeUuid(Object? value) => value is String && _uuid.hasMatch(value);
bool officeHash(Object? value) => value is String && _hash.hasMatch(value);
bool officeSame(Object? a, Object? b) =>
    officeUuid(a) &&
    officeUuid(b) &&
    a.toString().toLowerCase() == b.toString().toLowerCase();
String _id(String value) {
  officeCheck(officeUuid(value));
  return Uri.encodeComponent(value);
}

String _query(Map<String, Object?> source) => Uri(
  queryParameters: source.map((key, value) => MapEntry(key, value.toString())),
).query;
List<OfficeRecord> officeRecords(Object? value) {
  officeCheck(value is List && value.every((item) => item is Map));
  return (value as List).map(stringMap).toList();
}

OfficeRecord cifInformation(OfficeRecord review) => {
  for (final field in ['full_name', 'phone_number', 'email', 'present_address'])
    field: review[field],
  if (review['identity_information'] != null)
    'identity_information': stringMap(review['identity_information']),
};

/// Office transport only. Business decisions remain in the existing backend.
class OfficeRepository {
  OfficeRepository({http.Client? client}) : _client = client ?? http.Client();
  final http.Client _client;

  void _guard(
    OfficeIdentity actor, {
    String? permission,
    bool management = false,
  }) {
    if (!actor.allowed ||
        actor.deviceId.trim().isEmpty ||
        (permission != null &&
            !actor.can(permission, management: management)) ||
        (management && actor.session.role != AppRole.management)) {
      actor.accessDenied = true;
      throw const SpinaApiException(
        'Authorized office access and an active device are required.',
        statusCode: 403,
      );
    }
  }

  Future<http.Response> _send(
    OfficeIdentity actor,
    String path, {
    String method = 'GET',
    OfficeRecord? body,
    Uint8List? bytes,
    String? mediaType,
    String? permission,
    bool management = false,
  }) async {
    _guard(actor, permission: permission, management: management);
    final request = http.Request(method, ApiConfig.endpoint(path));
    request.headers.addAll({
      'Authorization': 'Bearer ${actor.session.accessToken}',
      'X-Session-Id': actor.session.accessToken,
      'X-Device-Id': actor.deviceId,
      'Accept': 'application/json,application/pdf,image/png,image/jpeg',
      'Cache-Control': 'no-store',
      if (body != null) 'Content-Type': 'application/json',
      if (bytes != null) 'Content-Type': mediaType!,
    });
    if (body != null) request.body = jsonEncode(body);
    if (bytes != null) request.bodyBytes = bytes;
    late final http.Response response;
    try {
      response = await http.Response.fromStream(
        await _client.send(request),
      ).timeout(const Duration(seconds: 45));
    } on Exception {
      throw const SpinaApiException(
        'The office request could not reach the server. Reload the saved record before repeating a write.',
        code: 'network_unavailable',
      );
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      if ([401, 403, 426].contains(response.statusCode)) {
        actor.accessDenied = true;
      }
      OfficeRecord value = {};
      try {
        value = decodeJsonObject(response.body);
      } on Object {
        /* Safe fallback. */
      }
      final detail = stringMap(value['detail']);
      final validation = value['detail'] is List
          ? (value['detail'] as List)
                .take(4)
                .map((item) {
                  final row = stringMap(item);
                  final location = row['loc'] is List ? row['loc'] as List : [];
                  final name = location.isEmpty
                      ? 'Information'
                      : location.last.toString().replaceAll('_', ' ');
                  return '$name: ${row['msg'] ?? 'Check this value.'}';
                })
                .join('\n')
          : null;
      throw SpinaApiException(
        firstNonEmptyString([
              detail['message'],
              value['detail'] is String ? value['detail'] : null,
              validation,
              value['message'],
            ]) ??
            'The office request was rejected. Refresh the current record.',
        statusCode: response.statusCode,
        code: firstNonEmptyString([detail['code'], value['code']]),
      );
    }
    return response;
  }

  Future<OfficeRecord> _json(
    OfficeIdentity actor,
    String path, {
    String method = 'GET',
    OfficeRecord? body,
    Uint8List? bytes,
    String? mediaType,
    String? permission,
    bool management = false,
  }) async {
    final response = await _send(
      actor,
      path,
      method: method,
      body: body,
      bytes: bytes,
      mediaType: mediaType,
      permission: permission,
      management: management,
    );
    try {
      final value = unwrapSpinaData(
        decodeJsonObject(response.body),
        statusCode: response.statusCode,
      );
      officeCheck(value is Map);
      return stringMap(value);
    } on SpinaApiException {
      rethrow;
    } on Object {
      throw const SpinaApiException(
        'The office response is unreadable. Reload the saved record.',
        code: 'invalid_office_record',
      );
    }
  }

  Future<OfficeRecord> loadIntake(
    OfficeIdentity actor,
    String reference,
  ) async {
    final value = await _json(
      actor,
      '$_intake/by-reference/${Uri.encodeComponent(reference.trim())}/case',
    );
    officeCheck(
      value['application_reference']?.toString().toLowerCase() ==
              reference.trim().toLowerCase() &&
          officeUuid(value['applicant_id']) &&
          value['requirements'] is Map,
    );
    return value;
  }

  Future<OfficeRecord> submitIntake(
    OfficeIdentity actor,
    OfficeRecord information,
  ) async {
    final value = await _json(
      actor,
      _intake,
      method: 'POST',
      body: information,
    );
    officeCheck(
      value['application_reference'] is String &&
          (value['application_reference'] as String).isNotEmpty,
    );
    return value;
  }

  Future<OfficeRecord> reviewRequirements(
    OfficeIdentity actor,
    String applicantId,
    OfficeRecord decisions,
  ) => _json(
    actor,
    '$_intake/${_id(applicantId)}/document-requirements',
    method: 'PATCH',
    body: decisions,
  );
  Future<OfficeRecord> approveEligibility(
    OfficeIdentity actor,
    String applicantId, {
    OfficeRecord? bypass,
  }) => _json(
    actor,
    '$_intake/${_id(applicantId)}/eligibility${bypass == null ? '' : '/bypass'}',
    method: 'POST',
    body: bypass,
    permission: bypass == null ? null : 'client_onboarding.bypass',
    management: bypass != null,
  );
  Future<OfficeRecord> selectClient(
    OfficeIdentity actor,
    String reference,
  ) async {
    final value = await _json(
      actor,
      '$_intake/by-reference/${Uri.encodeComponent(reference.trim())}/cif-client',
    );
    officeCheck(
      officeUuid(value['client_id']) &&
          value['application_reference']?.toString().toLowerCase() ==
              reference.trim().toLowerCase(),
    );
    return value;
  }

  void _cif(OfficeRecord value, String clientId) {
    officeCheck(
      officeSame(value['client_id'], clientId) &&
          officeUuid(value['cif_version_id']) &&
          value['version_number'] is int &&
          value['version_number'] > 0 &&
          value['review_scope'] == 'cif_information_only' &&
          [
            'full_name',
            'phone_number',
            'present_address',
          ].every((key) => value[key] is String) &&
          (value['email'] == null || value['email'] is String),
    );
  }

  Future<OfficeRecord> loadCif(OfficeIdentity actor, String clientId) async {
    final value = await _json(
      actor,
      '$_clients/${_id(clientId)}/cif/review-summary?include_correction_availability=true&include_identity_information=true',
    );
    _cif(value, clientId);
    officeCheck(value['can_correct_information'] is bool);
    return value;
  }

  Future<OfficeRecord> beginCif(OfficeIdentity actor, String clientId) async {
    final value = await _json(
      actor,
      '$_clients/${_id(clientId)}/cif/draft',
      method: 'POST',
    );
    officeCheck(
      officeSame(value['client_id'], clientId) &&
          value['version_number'] is int &&
          value['version_number'] > 0,
    );
    return value;
  }

  Future<OfficeRecord> correctCif(
    OfficeIdentity actor,
    OfficeRecord original,
    OfficeRecord corrected,
    String reason, {
    required bool successor,
  }) async {
    final clientId = original['client_id'] as String;
    final value = await _json(
      actor,
      '$_clients/${_id(clientId)}/cif/${successor ? 'review-cycles' : 'draft-information'}',
      method: successor ? 'POST' : 'PATCH',
      body: {
        'cif_version_id': original['cif_version_id'],
        'expected_information': cifInformation(original),
        'corrected_information': corrected,
        'reason': reason,
      },
    );
    _cif(value, clientId);
    officeCheck(
      successor
          ? !officeSame(value['cif_version_id'], original['cif_version_id']) &&
                value['version_number'] > original['version_number']
          : officeSame(value['cif_version_id'], original['cif_version_id']) &&
                value['version_number'] == original['version_number'],
    );
    return value;
  }

  Future<OfficeRecord> confirmCif(
    OfficeIdentity actor,
    OfficeRecord review,
    String evidence,
  ) async {
    final value = await _json(
      actor,
      '$_clients/${_id(review['client_id'])}/cif/review-confirmations',
      method: 'POST',
      body: {
        'cif_version_id': review['cif_version_id'],
        'expected_information': cifInformation(review),
        'applicant_confirmation_evidence_reference': evidence,
      },
    );
    officeCheck(
      officeSame(value['client_id'], review['client_id']) &&
          officeSame(value['cif_version_id'], review['cif_version_id']) &&
          officeUuid(value['review_confirmation_id']),
    );
    return value;
  }

  Future<OfficeRecord> recordBaseline(
    OfficeIdentity actor,
    OfficeRecord review,
    String reference,
  ) async {
    final value = await _json(
      actor,
      '$_clients/${_id(review['client_id'])}/cif/baseline-live-face',
      method: 'PATCH',
      body: {
        'cif_version_id': review['cif_version_id'],
        'evidence_reference': reference,
        'liveness_status': 'passed',
      },
    );
    officeCheck(
      officeSame(value['client_id'], review['client_id']) &&
          value['version_number'] == review['version_number'] &&
          value['liveness_status'] == 'passed',
    );
    return value;
  }

  Future<OfficeRecord> activateCif(
    OfficeIdentity actor,
    OfficeRecord review,
  ) async {
    final value = await _json(
      actor,
      '$_clients/${_id(review['client_id'])}/cif/activate',
      method: 'POST',
      management: true,
      body: {'cif_version_id': review['cif_version_id']},
    );
    officeCheck(
      officeSame(value['client_id'], review['client_id']) &&
          value['version_number'] == review['version_number'] &&
          value['status'] == 'active',
    );
    return value;
  }

  void _evidenceMatch(
    OfficeRecord value,
    String clientId,
    OfficeRecord source,
  ) {
    officeCheck(
      officeSame(value['client_id'], clientId) &&
          officeSame(value['cif_version_id'], source['cif_version_id']) &&
          value['purpose'] == source['purpose'] &&
          officeHash(value['snapshot_sha256']) &&
          ['application_id', 'application_version_id'].every(
            (key) => source[key] == null
                ? value[key] == null
                : officeSame(value[key], source[key]),
          ),
    );
  }

  Future<OfficeRecord> reviewContext(
    OfficeIdentity actor,
    String clientId,
    OfficeRecord source,
  ) async {
    final value = await _json(
      actor,
      '$_clients/${_id(clientId)}/review-evidence/context?${_query(source)}',
    );
    _evidenceMatch(value, clientId, source);
    final snapshot = stringMap(value['review_snapshot']);
    officeCheck(
      officeSame(snapshot['client_id'], clientId) &&
          officeSame(snapshot['cif_version_id'], source['cif_version_id']) &&
          snapshot['information'] is Map &&
          (source['purpose'] != 'application_review' ||
              (officeSame(
                    snapshot['application_id'],
                    source['application_id'],
                  ) &&
                  officeSame(
                    snapshot['application_version_id'],
                    source['application_version_id'],
                  ) &&
                  snapshot['cif_information'] is Map)),
    );
    officeCheck(
      value['issuance_ready'] != false,
      'The controlled document is not ready for signing.',
    );
    return value;
  }

  Future<OfficeRecord> captureReview(
    OfficeIdentity actor,
    String clientId, {
    required OfficeRecord source,
    required String snapshotHash,
    required String requestId,
    required Uint8List bytes,
    required String mediaType,
  }) async {
    validateOfficeEvidence(bytes, mediaType);
    officeCheck(officeHash(snapshotHash) && officeUuid(requestId));
    final value = await _json(
      actor,
      '$_clients/${_id(clientId)}/review-evidence?${_query({...source, 'request_id': requestId, 'expected_snapshot_sha256': snapshotHash, 'witnessed_wet_signature': 'true'})}',
      method: 'POST',
      bytes: bytes,
      mediaType: mediaType,
    );
    _evidenceMatch(value, clientId, source);
    officeCheck(
      value['snapshot_sha256'] == snapshotHash &&
          value['content_sha256'] == sha256.convert(bytes).toString() &&
          value['media_type'] == mediaType &&
          value['byte_count'] == bytes.length &&
          officeUuid(value['evidence_id']) &&
          value['evidence_reference'] ==
              'office-evidence:${value['evidence_id']}',
    );
    return value;
  }

  Future<OfficeRecord> privacyContext(
    OfficeIdentity actor,
    String clientId,
    String cifVersionId,
    bool optional,
  ) async {
    final value = await _json(
      actor,
      '$_clients/${_id(clientId)}/privacy/context?${_query({'cif_version_id': cifVersionId, 'optional_service_communications': optional})}',
    );
    _evidenceMatch(value, clientId, {
      'purpose': 'privacy_acknowledgment',
      'cif_version_id': cifVersionId,
    });
    final snapshot = stringMap(value['review_snapshot']);
    officeCheck(
      value['issuable'] is bool &&
          snapshot['optional_service_communications'] == optional &&
          officeSame(snapshot['client_id'], clientId) &&
          officeSame(snapshot['cif_version_id'], cifVersionId),
    );
    if (value['issuable'] == true) {
      for (final kind in ['notice', 'consent']) {
        final item = stringMap(snapshot[kind]);
        officeCheck(item['version'] is String && officeHash(item['sha256']));
      }
    }
    return value;
  }

  Future<OfficeRecord> acknowledgePrivacy(
    OfficeIdentity actor,
    String clientId,
    OfficeRecord context,
    OfficeRecord evidence,
  ) async {
    final snapshot = stringMap(context['review_snapshot']);
    final value = await _json(
      actor,
      '$_clients/${_id(clientId)}/privacy/acknowledgments',
      method: 'POST',
      body: {
        'cif_version_id': context['cif_version_id'],
        'optional_service_communications':
            snapshot['optional_service_communications'],
        'evidence_reference': evidence['evidence_reference'],
      },
    );
    officeCheck(
      officeSame(value['client_id'], clientId) &&
          officeSame(value['cif_version_id'], context['cif_version_id']) &&
          officeSame(value['evidence_id'], evidence['evidence_id']) &&
          value['optional_service_communications'] ==
              snapshot['optional_service_communications'] &&
          ['notice', 'consent'].every(
            (kind) =>
                value['${kind}_version'] ==
                    stringMap(snapshot[kind])['version'] &&
                value['${kind}_sha256'] == stringMap(snapshot[kind])['sha256'],
          ),
    );
    return value;
  }

  Future<OfficeRecord> applicationContext(
    OfficeIdentity actor,
    String clientId,
  ) async {
    final value = await _json(
      actor,
      '$_clients/${_id(clientId)}/loan-applications/entry-context',
    );
    officeCheck(
      officeSame(value['client_id'], clientId) &&
          officeUuid(value['cif_version_id']),
    );
    for (final product in officeRecords(value['loan_types'])) {
      officeCheck(officeUuid(product['id']) && product['name'] is String);
    }
    return value;
  }

  void _application(OfficeRecord value, String clientId, String reference) {
    officeCheck(
      officeSame(value['client_id'], clientId) &&
          value['application_reference'] == reference &&
          [
            'application_id',
            'application_version_id',
            'cif_version_id',
          ].every((key) => officeUuid(value[key])) &&
          value['version_number'] is int &&
          value['version_number'] > 0 &&
          value['information'] is Map &&
          value['missing_fields'] is List &&
          value['review_scope'] == 'loan_application_information_only',
    );
  }

  Future<OfficeRecord> loadApplication(
    OfficeIdentity actor,
    String clientId,
    String reference,
  ) async {
    final value = await _json(
      actor,
      '$_clients/${_id(clientId)}/loan-applications/by-reference/${Uri.encodeComponent(reference)}/review-summary',
    );
    _application(value, clientId, reference);
    return value;
  }

  Future<OfficeRecord> saveApplication(
    OfficeIdentity actor,
    String clientId, {
    required String reference,
    required String cifVersionId,
    required OfficeRecord information,
    String? applicationId,
    int? expectedVersion,
  }) async {
    final path = applicationId == null
        ? 'drafts'
        : '${_id(applicationId)}/draft-versions';
    final value = await _json(
      actor,
      '$_clients/${_id(clientId)}/loan-applications/$path',
      method: 'POST',
      body: {
        'cif_version_id': cifVersionId,
        if (applicationId == null) 'application_reference': reference,
        if (applicationId != null) 'expected_version_number': expectedVersion,
        'information': information,
      },
    );
    _application(value, clientId, reference);
    officeCheck(
      officeSame(value['cif_version_id'], cifVersionId) &&
          (applicationId == null ||
              (officeSame(value['application_id'], applicationId) &&
                  value['version_number'] > expectedVersion!)),
    );
    return value;
  }

  Future<OfficeRecord> confirmApplication(
    OfficeIdentity actor,
    OfficeRecord review,
    String evidence,
  ) async {
    final value = await _json(
      actor,
      '$_clients/${_id(review['client_id'])}/loan-applications/${_id(review['application_id'])}/review-confirmations',
      method: 'POST',
      body: {
        'application_version_id': review['application_version_id'],
        'applicant_confirmation_evidence_reference': evidence,
      },
    );
    officeCheck(
      [
            'client_id',
            'cif_version_id',
            'application_id',
            'application_version_id',
          ].every((key) => officeSame(value[key], review[key])) &&
          officeUuid(value['review_confirmation_id']) &&
          value['review_scope'] == 'loan_application_information_only',
    );
    return value;
  }

  Future<OfficeRecord> firstLoanContext(OfficeIdentity actor) async {
    final value = await _json(actor, '$_loans/context');
    for (final item in officeRecords(value['products'])) {
      officeCheck(
        officeUuid(item['id']) &&
            item['name'] is String &&
            [
              'fixed_daily',
              'fixed_total',
              'seven_by_seven',
            ].contains(item['calculation_mode']),
      );
    }
    for (final item in officeRecords(value['templates'])) {
      officeCheck(
        item['version'] is String &&
            officeHash(item['content_sha256']) &&
            item['approved_for_execution'] is bool,
      );
    }
    return value;
  }

  Future<OfficeRecord> firstLoans(
    OfficeIdentity actor,
    OfficeRecord application,
  ) async {
    final value = await _json(
      actor,
      '$_loans/by-application/${_id(application['application_id'])}',
    );
    for (final loan in officeRecords(value['loans'])) {
      _loan(loan, application);
    }
    return value;
  }

  void _loan(OfficeRecord loan, OfficeRecord application) {
    final packet = stringMap(loan['packet']);
    officeCheck(
      officeUuid(loan['loan_id']) &&
          officeUuid(loan['packet_id']) &&
          officeHash(loan['packet_hash']) &&
          officeSame(loan['client_id'], application['client_id']) &&
          officeSame(packet['loan_id'], loan['loan_id']) &&
          officeSame(packet['packet_id'], loan['packet_id']) &&
          officeSame(packet['client_id'], application['client_id']) &&
          officeSame(
            stringMap(packet['application'])['application_id'],
            application['application_id'],
          ) &&
          [
            'approved_pending_release',
            'released',
            'cancelled',
          ].contains(loan['status']) &&
          packet['terms'] is Map &&
          packet['borrower'] is Map,
    );
    officeCheck(officeRecords(packet['schedule']).isNotEmpty);
    final money = RegExp(r'^\d+(?:\.\d{1,2})?$');
    bool exact(Object? value) => value is String && money.hasMatch(value);
    officeCheck(
      exact(stringMap(packet['terms'])['principal']) &&
          exact(packet['net_cash']) &&
          stringMap(packet['borrower'])['full_name'] is String,
    );
    for (final row in officeRecords(packet['schedule'])) {
      officeCheck(
        row['installment_number'] is int &&
            row['installment_number'] > 0 &&
            row['due_date'] is String &&
            RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(row['due_date']) &&
            [
              'contractual_amount',
              'principal_component',
              'interest_component',
            ].every((key) => exact(row[key])),
      );
    }
    if (loan['document'] != null) {
      officeCheck(
        officeUuid(stringMap(loan['document'])['id']) &&
            officeHash(stringMap(loan['document'])['content_sha256']),
      );
    }
    if (loan['authorization'] != null) {
      officeCheck(
        officeUuid(stringMap(loan['authorization'])['id']) &&
            stringMap(loan['authorization'])['revoked'] is bool,
      );
    }
    if (loan['evidence'] != null) {
      officeCheck(loan['evidence'] is Map);
      for (final item in stringMap(loan['evidence']).entries) {
        final reference = stringMap(item.value)['evidence_reference'];
        officeCheck(
          [
                'borrower_contract_signed',
                'borrower_cash_received',
              ].contains(item.key) &&
              reference is String &&
              RegExp(r'^office-evidence:[0-9a-f-]{36}$').hasMatch(reference),
        );
      }
    }
  }

  Future<OfficeRecord> approveLoan(
    OfficeIdentity actor,
    OfficeRecord application,
    OfficeRecord terms,
    String templateVersion,
    String requestId,
  ) async {
    final value = await _json(
      actor,
      '$_loans/approve',
      method: 'POST',
      permission: 'lending.first_loan.approve',
      management: true,
      body: {
        'request_id': requestId,
        'application_version_id': application['application_version_id'],
        'terms': terms,
        'template_version': templateVersion,
      },
    );
    _loan(value, application);
    final packet = stringMap(value['packet']);
    final approvedApplication = stringMap(packet['application']);
    officeCheck(
      officeSame(
            approvedApplication['id'],
            application['application_version_id'],
          ) &&
          approvedApplication['version_number'] ==
              application['version_number'] &&
          officeSame(packet['cif_version_id'], application['cif_version_id']) &&
          stringMap(packet['template'])['version'] == templateVersion &&
          value['status'] == 'approved_pending_release',
    );
    return value;
  }

  Future<OfficeRecord> rejectLoan(
    OfficeIdentity actor,
    OfficeRecord application,
    String reason,
    String requestId,
  ) => _json(
    actor,
    '$_loans/reject',
    method: 'POST',
    permission: 'lending.first_loan.approve',
    management: true,
    body: {
      'request_id': requestId,
      'application_version_id': application['application_version_id'],
      'reason': reason,
    },
  );
  Future<OfficeRecord> packetAction(
    OfficeIdentity actor,
    OfficeRecord loan,
    String action,
    OfficeRecord body,
  ) {
    officeCheck(
      [
        'documents',
        'authorize-release',
        'cancel-approval',
        'revoke-release',
      ].contains(action),
    );
    return _json(
      actor,
      '$_loans/${_id(loan['loan_id'])}/$action',
      method: 'POST',
      body: body,
      permission: 'lending.first_loan.approve',
      management: true,
    );
  }

  Future<OfficeRecord> reviewPricing(
    OfficeIdentity actor,
    OfficeRecord body,
  ) => _json(
    actor,
    '/api/v1/management/financial-accounting/contract-schedules/7x7-pricing-compliance/review',
    method: 'POST',
    body: body,
    permission: 'lending.contract_schedule.manage',
    management: true,
  );
  Future<OfficeRecord> captureLoan(
    OfficeIdentity actor,
    OfficeRecord loan, {
    required String purpose,
    required Uint8List bytes,
    required String mediaType,
    required String requestId,
    required bool witnessed,
  }) async {
    validateOfficeEvidence(bytes, mediaType);
    officeCheck(
      ['borrower_contract_signed', 'borrower_cash_received'].contains(purpose),
    );
    if (purpose == 'borrower_contract_signed' && !witnessed) {
      throw const SpinaApiException(
        'Witness the named borrower signing this exact packet.',
        statusCode: 422,
      );
    }
    final value = await _json(
      actor,
      '$_loans/${_id(loan['loan_id'])}/evidence',
      method: 'POST',
      permission: 'lending.first_loan.release',
      body: {
        'request_id': requestId,
        'packet_hash': loan['packet_hash'],
        'purpose': purpose,
        'media_type': mediaType,
        'content_base64': base64Encode(bytes),
        'witnessed_wet_signature': witnessed,
        'authorization_id': purpose == 'borrower_cash_received'
            ? stringMap(loan['authorization'])['id']
            : null,
      },
    );
    officeCheck(
      value['packet_hash'] == loan['packet_hash'] &&
          value['purpose'] == purpose &&
          value['evidence_reference'] is String &&
          RegExp(
            r'^office-evidence:[0-9a-f-]{36}$',
          ).hasMatch(value['evidence_reference']),
    );
    return value;
  }

  Future<OfficeRecord> releaseLoan(
    OfficeIdentity actor,
    OfficeRecord loan,
    OfficeRecord application, {
    required String contractEvidence,
    required String cashEvidence,
    required String cashAmount,
    required String requestId,
  }) async {
    final value = await _json(
      actor,
      '$_loans/${_id(loan['loan_id'])}/release',
      method: 'POST',
      permission: 'lending.first_loan.release',
      body: {
        'request_id': requestId,
        'packet_hash': loan['packet_hash'],
        'authorization_id': stringMap(loan['authorization'])['id'],
        'contract_evidence_reference': contractEvidence,
        'cash_evidence_reference': cashEvidence,
        'cash_amount': cashAmount,
        'borrower_confirmed': true,
      },
    );
    _loan(value, application);
    final receipt = stringMap(stringMap(value['release'])['receipt']);
    officeCheck(
      value['status'] == 'released' &&
          officeSame(value['loan_id'], loan['loan_id']) &&
          officeSame(value['packet_id'], loan['packet_id']) &&
          value['packet_hash'] == loan['packet_hash'] &&
          officeSame(
            stringMap(value['authorization'])['id'],
            stringMap(loan['authorization'])['id'],
          ) &&
          stringMap(value['authorization'])['revoked'] == false &&
          officeSame(receipt['loan_id'], loan['loan_id']) &&
          officeSame(receipt['client_id'], loan['client_id']) &&
          officeSame(receipt['packet_id'], loan['packet_id']) &&
          receipt['packet_hash'] == loan['packet_hash'] &&
          receipt['contract_evidence_reference'] == contractEvidence &&
          receipt['cash_evidence_reference'] == cashEvidence &&
          receipt['releasing_staff_id'] == actor.session.userId &&
          receipt['receipt_reference'] is String &&
          (receipt['receipt_reference'] as String).isNotEmpty &&
          _exactCents(cashAmount) != null &&
          _exactCents(receipt['actual_cash_received']) ==
              _exactCents(cashAmount),
    );
    return value;
  }

  Future<OfficeRecord> credentials(OfficeIdentity actor, String loanId) =>
      _json(
        actor,
        '$_loans/${_id(loanId)}/credentials',
        method: 'POST',
        permission: 'client.credential.manage',
      );

  Future<ClientDocumentFile> _download(
    OfficeIdentity actor,
    String path,
    String filename, {
    String? expectedHash,
    bool pdfOnly = false,
  }) async {
    final response = await _send(actor, path);
    final type =
        response.headers['content-type']?.split(';').first.trim() ?? '';
    officeCheck(
      !pdfOnly || type == 'application/pdf',
      'The server did not return the selected PDF document.',
    );
    try {
      validateOfficeEvidence(response.bodyBytes, type);
    } on Object {
      throw const SpinaApiException(
        'The server did not return a valid protected document.',
        code: 'invalid_office_document',
      );
    }
    if (expectedHash != null) {
      officeCheck(
        officeHash(expectedHash) &&
            sha256.convert(response.bodyBytes).toString() == expectedHash,
        'The document changed. Reload its saved record before signing.',
      );
    }
    return ClientDocumentFile(
      filename: filename,
      bytes: response.bodyBytes,
      mediaType: type,
    );
  }

  Future<ClientDocumentFile> downloadPrivacy(
    OfficeIdentity actor,
    String clientId,
    String cifVersionId,
    String kind,
    String expectedHash,
  ) {
    officeCheck(['notice', 'consent'].contains(kind));
    return _download(
      actor,
      '$_clients/${_id(clientId)}/privacy/documents/$kind?${_query({'cif_version_id': cifVersionId, 'expected_sha256': expectedHash})}',
      'privacy-$kind.pdf',
      expectedHash: expectedHash,
      pdfOnly: true,
    );
  }

  Future<ClientDocumentFile> downloadPacket(
    OfficeIdentity actor,
    OfficeRecord loan,
  ) => _download(
    actor,
    '$_loans/${_id(loan['loan_id'])}/documents',
    'loan-packet-${loan['loan_id']}.pdf',
    expectedHash: stringMap(loan['document'])['content_sha256'],
    pdfOnly: true,
  );
  Future<ClientDocumentFile> downloadEvidence(
    OfficeIdentity actor,
    String clientId,
    OfficeRecord evidence,
  ) async {
    officeCheck(officeHash(evidence['content_sha256']));
    final extension = evidence['media_type'] == 'image/png'
        ? 'png'
        : evidence['media_type'] == 'image/jpeg'
        ? 'jpg'
        : 'pdf';
    return _download(
      actor,
      '$_clients/${_id(clientId)}/review-evidence/${_id(evidence['evidence_id'])}',
      'review-evidence-${evidence['evidence_id']}.$extension',
      expectedHash: evidence['content_sha256'],
    );
  }
}

BigInt? _exactCents(Object? value) {
  if (value is! String) return null;
  final match = RegExp(r'^(\d+)(?:\.(\d{1,2}))?$').firstMatch(value);
  if (match == null) return null;
  return BigInt.parse(match[1]!) * BigInt.from(100) +
      BigInt.parse((match[2] ?? '').padRight(2, '0'));
}

void validateOfficeEvidence(Uint8List bytes, String mediaType) {
  final pdf =
      mediaType == 'application/pdf' &&
      bytes.length >= 5 &&
      String.fromCharCodes(bytes.take(5)) == '%PDF-';
  final image =
      ['image/png', 'image/jpeg'].contains(mediaType) &&
      RemittancePhotoDraft.detectContentType(bytes) == mediaType;
  if (bytes.isEmpty || bytes.length > 10 * 1024 * 1024 || (!pdf && !image)) {
    throw const SpinaApiException(
      'Choose a signed PDF, PNG or JPEG of at most 10 MiB.',
      statusCode: 422,
    );
  }
}

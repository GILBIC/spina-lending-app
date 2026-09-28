import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart';

const _base = '/api/v1/collector/onboarding/applicants';
const _statuses = [
  'requirements_incomplete',
  'under_verification',
  'eligible_for_cif',
  'requirements_rejected',
];

class ResidenceVisitCase {
  ResidenceVisitCase._(
    this.applicantId,
    this.reference,
    this.name,
    this.phone,
    this.address,
    this.visitStatus,
    this.note,
    this.evidenceReference,
  );
  final String applicantId, reference, name, phone, address, visitStatus;
  final String? note, evidenceReference;

  factory ResidenceVisitCase.fromPayload(
    Map<String, dynamic> data,
    String reference,
  ) {
    final visit = stringMap(data['collector_visit']);
    final id = data['applicant_id'];
    if (id is! String ||
        !RegExp(
          r'^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$',
        ).hasMatch(id) ||
        data['application_reference'] is! String ||
        (data['application_reference'] as String).trim().toLowerCase() !=
            reference.trim().toLowerCase() ||
        !_statuses.contains(data['status']) ||
        ![
          'full_name',
          'phone_number',
          'present_address',
        ].every((key) => data[key] is String) ||
        !['pending', 'passed', 'failed'].contains(visit['status']) ||
        !['note', 'evidence_reference'].every(
          (key) =>
              visit.containsKey(key) &&
              (visit[key] == null || visit[key] is String),
        )) {
      throw const SpinaApiException(
        'The intake case is incomplete or does not match this reference.',
      );
    }
    return ResidenceVisitCase._(
      id,
      data['application_reference'],
      data['full_name'],
      data['phone_number'],
      data['present_address'],
      visit['status'],
      visit['note'],
      visit['evidence_reference'],
    );
  }
}

class CollectorResidenceVisitRepository {
  CollectorResidenceVisitRepository(this.client);
  final StaffOperationsClient client;

  void _authorize(UserSession session) {
    if (!session.hasRole(AppRole.collector) ||
        !session.hasPermission('client_onboarding.visit.record')) {
      throw const SpinaApiException(
        'Collector residence-visit permission is required.',
        statusCode: 403,
      );
    }
  }

  Future<ResidenceVisitCase> load(UserSession session, String reference) async {
    _authorize(session);
    if (reference.trim().isEmpty) {
      throw const SpinaApiException('Enter the office intake reference.');
    }
    return ResidenceVisitCase.fromPayload(
      await client.request(
        session,
        'GET',
        '$_base/by-reference/${Uri.encodeComponent(reference.trim())}/visit-case',
      ),
      reference,
    );
  }

  Future<void> record(
    UserSession session,
    ResidenceVisitCase record, {
    required String result,
    required String note,
    required String evidenceReference,
  }) async {
    _authorize(session);
    if (!['passed', 'failed'].contains(result) ||
        note.length > 500 ||
        evidenceReference.length > 500) {
      throw const SpinaApiException(
        'Choose the observed visit result and keep notes within 500 characters.',
        statusCode: 422,
      );
    }
    // This API has no idempotency/revision key. Never replay an uncertain write.
    final response = await client.request(
      session,
      'POST',
      '$_base/${record.applicantId}/visit',
      body: {
        'result': result,
        'note': note.trim(),
        'evidence_reference': evidenceReference.trim().isEmpty
            ? null
            : evidenceReference.trim(),
      },
    );
    if (!_statuses.contains(response['status'])) {
      throw const SpinaApiException(
        'The saved visit could not be confirmed. Reload the intake case.',
      );
    }
  }
}

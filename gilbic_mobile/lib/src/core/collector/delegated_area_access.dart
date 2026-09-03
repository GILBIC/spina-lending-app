import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class DelegatedAreaScope {
  const DelegatedAreaScope({
    required this.assignmentId,
    required this.ownerUserId,
    required this.ownerName,
    required this.areaPath,
    required this.sortOrder,
    this.includeDescendants = false,
  });

  final String assignmentId;
  final String ownerUserId;
  final String ownerName;
  final String areaPath;
  final int sortOrder;
  final bool includeDescendants;

  static DelegatedAreaScope? fromPayload(Object? value) {
    final data = stringMap(value);
    final assignmentId = firstNonEmptyString(<Object?>[data['assignment_id']]);
    final ownerUserId = firstNonEmptyString(<Object?>[data['owner_user_id']]);
    final areaPath = firstNonEmptyString(<Object?>[data['area_path']]);
    if (assignmentId == null || ownerUserId == null || areaPath == null) {
      return null;
    }
    return DelegatedAreaScope(
      assignmentId: assignmentId,
      ownerUserId: ownerUserId,
      ownerName: firstNonEmptyString(<Object?>[data['owner_name']]) ?? 'Collector',
      areaPath: areaPath,
      sortOrder: firstNumber(<Object?>[data['sort_order']])?.toInt() ?? 0,
      includeDescendants: _boolValue(data['include_descendants']),
    );
  }
}

class DelegatedAreaRequest {
  const DelegatedAreaRequest({
    required this.requestId,
    required this.requesterUserId,
    required this.requesterName,
    required this.requestedOwnerUserId,
    required this.requestedOwnerName,
    required this.scopeMode,
    required this.reason,
    required this.requestedExpiresAt,
    required this.status,
    required this.decisionReason,
    required this.createdAt,
    required this.scopes,
  });

  final String requestId;
  final String requesterUserId;
  final String requesterName;
  final String requestedOwnerUserId;
  final String requestedOwnerName;
  final String scopeMode;
  final String reason;
  final DateTime? requestedExpiresAt;
  final String status;
  final String decisionReason;
  final DateTime? createdAt;
  final List<DelegatedAreaScope> scopes;

  bool get isPending => status.toLowerCase() == 'pending';

  static DelegatedAreaRequest? fromPayload(Object? value) {
    final data = stringMap(value);
    final requestId = firstNonEmptyString(<Object?>[data['request_id']]);
    final requesterUserId =
        firstNonEmptyString(<Object?>[data['requester_user_id']]);
    final requestedOwnerUserId =
        firstNonEmptyString(<Object?>[data['requested_owner_user_id']]);
    if (requestId == null ||
        requesterUserId == null ||
        requestedOwnerUserId == null) {
      return null;
    }
    return DelegatedAreaRequest(
      requestId: requestId,
      requesterUserId: requesterUserId,
      requesterName:
          firstNonEmptyString(<Object?>[data['requester_name']]) ?? 'Collector',
      requestedOwnerUserId: requestedOwnerUserId,
      requestedOwnerName:
          firstNonEmptyString(<Object?>[data['requested_owner_name']]) ??
              'Collector',
      scopeMode:
          firstNonEmptyString(<Object?>[data['scope_mode']]) ?? 'selected_paths',
      reason: firstNonEmptyString(<Object?>[data['reason']]) ?? '',
      requestedExpiresAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['requested_expires_at']]) ?? '',
      ),
      status: firstNonEmptyString(<Object?>[data['status']]) ?? 'pending',
      decisionReason:
          firstNonEmptyString(<Object?>[data['decision_reason']]) ?? '',
      createdAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['created_at']]) ?? '',
      ),
      scopes: _scopeList(data['scopes']),
    );
  }
}

class DelegatedAreaGrant {
  const DelegatedAreaGrant({
    required this.grantId,
    required this.sourceRequestId,
    required this.grantorUserId,
    required this.grantorName,
    required this.visitingCollectorUserId,
    required this.visitingCollectorName,
    required this.effectiveAt,
    required this.expiresAt,
    required this.revokedAt,
    required this.revocationReason,
    required this.scopes,
  });

  final String grantId;
  final String? sourceRequestId;
  final String grantorUserId;
  final String grantorName;
  final String visitingCollectorUserId;
  final String visitingCollectorName;
  final DateTime? effectiveAt;
  final DateTime? expiresAt;
  final DateTime? revokedAt;
  final String revocationReason;
  final List<DelegatedAreaScope> scopes;

  static DelegatedAreaGrant? fromPayload(Object? value) {
    final data = stringMap(value);
    final grantId = firstNonEmptyString(<Object?>[data['grant_id']]);
    final grantorUserId = firstNonEmptyString(<Object?>[data['grantor_user_id']]);
    final visitingCollectorUserId =
        firstNonEmptyString(<Object?>[data['visiting_collector_user_id']]);
    if (grantId == null ||
        grantorUserId == null ||
        visitingCollectorUserId == null) {
      return null;
    }
    return DelegatedAreaGrant(
      grantId: grantId,
      sourceRequestId:
          firstNonEmptyString(<Object?>[data['source_request_id']]),
      grantorUserId: grantorUserId,
      grantorName:
          firstNonEmptyString(<Object?>[data['grantor_name']]) ?? 'Collector',
      visitingCollectorUserId: visitingCollectorUserId,
      visitingCollectorName:
          firstNonEmptyString(<Object?>[data['visiting_collector_name']]) ??
              'Collector',
      effectiveAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['effective_at']]) ?? '',
      ),
      expiresAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['expires_at']]) ?? '',
      ),
      revokedAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['revoked_at']]) ?? '',
      ),
      revocationReason:
          firstNonEmptyString(<Object?>[data['revocation_reason']]) ?? '',
      scopes: _scopeList(data['scopes']),
    );
  }
}

List<DelegatedAreaScope> _scopeList(Object? value) {
  if (value is! Iterable) {
    return const <DelegatedAreaScope>[];
  }
  return value
      .map(DelegatedAreaScope.fromPayload)
      .whereType<DelegatedAreaScope>()
      .toList(growable: false);
}

bool _boolValue(Object? value) {
  if (value is bool) {
    return value;
  }
  final normalized = value?.toString().trim().toLowerCase() ?? '';
  return normalized == 'true' || normalized == '1' || normalized == 'yes';
}

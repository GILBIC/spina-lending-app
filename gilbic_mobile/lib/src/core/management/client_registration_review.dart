import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ClientRegistrationReview {
  const ClientRegistrationReview({
    required this.userId,
    required this.username,
    required this.email,
    required this.fullName,
    required this.claimedClientCode,
    required this.claimedPhoneNumber,
    required this.registrationStatus,
    required this.submittedAt,
  });

  final String userId;
  final String username;
  final String? email;
  final String fullName;
  final String claimedClientCode;
  final String? claimedPhoneNumber;
  final String registrationStatus;
  final DateTime? submittedAt;

  static ClientRegistrationReview? fromPayload(Object? value) {
    final data = stringMap(value);
    final userId = firstNonEmptyString(<Object?>[data['user_id']]);
    final username = firstNonEmptyString(<Object?>[data['username']]);
    final fullName = firstNonEmptyString(<Object?>[data['full_name']]);
    final clientCode =
        firstNonEmptyString(<Object?>[data['claimed_client_code']]);
    if (userId == null ||
        username == null ||
        fullName == null ||
        clientCode == null) {
      return null;
    }
    return ClientRegistrationReview(
      userId: userId,
      username: username,
      email: firstNonEmptyString(<Object?>[data['email']]),
      fullName: fullName,
      claimedClientCode: clientCode,
      claimedPhoneNumber:
          firstNonEmptyString(<Object?>[data['claimed_phone_number']]),
      registrationStatus:
          firstNonEmptyString(<Object?>[data['registration_status']]) ??
              'pending',
      submittedAt: DateTime.tryParse(data['submitted_at']?.toString() ?? ''),
    );
  }
}

class ClientLinkCandidate {
  const ClientLinkCandidate({
    required this.id,
    required this.clientCode,
    required this.fullName,
    required this.phoneNumber,
    required this.area,
  });

  final String id;
  final String clientCode;
  final String fullName;
  final String? phoneNumber;
  final String? area;

  static ClientLinkCandidate? fromPayload(Object? value) {
    final data = stringMap(value);
    final id = firstNonEmptyString(<Object?>[data['id']]);
    final clientCode = firstNonEmptyString(<Object?>[data['client_code']]);
    final fullName = firstNonEmptyString(<Object?>[data['full_name']]);
    if (id == null || clientCode == null || fullName == null) {
      return null;
    }
    return ClientLinkCandidate(
      id: id,
      clientCode: clientCode,
      fullName: fullName,
      phoneNumber: firstNonEmptyString(<Object?>[data['phone_number']]),
      area: firstNonEmptyString(<Object?>[data['area']]),
    );
  }
}

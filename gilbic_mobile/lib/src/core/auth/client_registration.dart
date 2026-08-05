class ClientRegistrationDraft {
  const ClientRegistrationDraft({
    required this.fullName,
    required this.clientCode,
    required this.phoneNumber,
    required this.email,
    required this.username,
    required this.password,
  });

  final String fullName;
  final String clientCode;
  final String phoneNumber;
  final String email;
  final String username;
  final String password;
}

class ClientRegistrationResult {
  const ClientRegistrationResult({
    required this.approvalStatus,
    required this.message,
    required this.requiresEmailConfirmation,
  });

  final String approvalStatus;
  final String message;
  final bool requiresEmailConfirmation;
}

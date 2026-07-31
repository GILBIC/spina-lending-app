import 'package:gilbic_mobile/src/core/auth/app_role.dart';

class UserSession {
  const UserSession({
    required this.userId,
    required this.displayName,
    required this.role,
    required this.accessToken,
  });

  final String userId;
  final String displayName;
  final AppRole role;
  final String accessToken;
}

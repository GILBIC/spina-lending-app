class ApiConfig {
  const ApiConfig._();

  static const String baseUrl = String.fromEnvironment(
    'GILBIC_API_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );

  static const String loginPath = String.fromEnvironment(
    'GILBIC_LOGIN_PATH',
    defaultValue: '/api/mobile/v1/auth/login',
  );

  static const String refreshPath = String.fromEnvironment(
    'GILBIC_REFRESH_PATH',
    defaultValue: '/api/mobile/v1/auth/refresh',
  );

  static const String logoutPath = String.fromEnvironment(
    'GILBIC_LOGOUT_PATH',
    defaultValue: '/api/mobile/v1/auth/logout',
  );

  static const String collectorRoutePath = String.fromEnvironment(
    'GILBIC_COLLECTOR_ROUTE_PATH',
    defaultValue: '/api/mobile/v1/collector/routes/today',
  );

  static const String otherAreaSearchPath = String.fromEnvironment(
    'GILBIC_OTHER_AREA_SEARCH_PATH',
    defaultValue: '/api/mobile/v1/collector/other-area-clients/search',
  );

  static const String paymentSubmissionPath = String.fromEnvironment(
    'GILBIC_PAYMENT_SUBMISSION_PATH',
    defaultValue: '/api/mobile/v1/collector/collections',
  );

  static const String activityNotificationsPath = String.fromEnvironment(
    'GILBIC_ACTIVITY_NOTIFICATIONS_PATH',
    defaultValue: '/api/mobile/v1/activity-notifications',
  );

  static Uri get loginEndpoint => endpoint(loginPath);

  static Uri get refreshEndpoint => endpoint(refreshPath);

  static Uri get logoutEndpoint => endpoint(logoutPath);

  static Uri get collectorRouteEndpoint => endpoint(collectorRoutePath);

  static Uri get otherAreaSearchEndpoint => endpoint(otherAreaSearchPath);

  static Uri get paymentSubmissionEndpoint => endpoint(paymentSubmissionPath);

  static Uri get activityNotificationsEndpoint =>
      endpoint(activityNotificationsPath);

  static Uri endpoint(String path) {
    final cleanBase = baseUrl.endsWith('/')
        ? baseUrl.substring(0, baseUrl.length - 1)
        : baseUrl;
    final normalizedPath = path.startsWith('/') ? path : '/$path';
    return Uri.parse('$cleanBase$normalizedPath');
  }
}

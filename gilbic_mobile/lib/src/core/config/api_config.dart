class ApiConfig {
  const ApiConfig._();

  static const String baseUrl = String.fromEnvironment(
    'GILBIC_API_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );

  static const String registerPath = String.fromEnvironment(
    'GILBIC_REGISTER_PATH',
    defaultValue: '/api/mobile/v1/auth/register',
  );

  static const String loginPath = String.fromEnvironment(
    'GILBIC_LOGIN_PATH',
    defaultValue: '/api/mobile/v1/auth/login',
  );

  static const String refreshPath = String.fromEnvironment(
    'GILBIC_REFRESH_PATH',
    defaultValue: '/api/mobile/v1/auth/refresh',
  );

  static const String mePath = String.fromEnvironment(
    'GILBIC_ME_PATH',
    defaultValue: '/api/mobile/v1/auth/me',
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

  static const String delegatedAreaWorkPath = String.fromEnvironment(
    'GILBIC_DELEGATED_AREA_WORK_PATH',
    defaultValue: '/api/mobile/v1/collector/delegated-area/work',
  );

  static const String delegatedAreaAvailableScopesPath = String.fromEnvironment(
    'GILBIC_DELEGATED_AREA_AVAILABLE_SCOPES_PATH',
    defaultValue: '/api/mobile/v1/collector/delegated-area/available-scopes',
  );

  static const String delegatedAreaIncomingRequestsPath = String.fromEnvironment(
    'GILBIC_DELEGATED_AREA_INCOMING_REQUESTS_PATH',
    defaultValue: '/api/mobile/v1/collector/delegated-area/requests/incoming',
  );

  static const String delegatedAreaOutgoingRequestsPath = String.fromEnvironment(
    'GILBIC_DELEGATED_AREA_OUTGOING_REQUESTS_PATH',
    defaultValue: '/api/mobile/v1/collector/delegated-area/requests/outgoing',
  );

  static const String delegatedAreaActiveGrantsPath = String.fromEnvironment(
    'GILBIC_DELEGATED_AREA_ACTIVE_GRANTS_PATH',
    defaultValue: '/api/mobile/v1/collector/delegated-area/grants/active',
  );

  static const String paymentSubmissionPath = String.fromEnvironment(
    'GILBIC_PAYMENT_SUBMISSION_PATH',
    defaultValue: '/api/mobile/v1/collector/collections',
  );

  static const String combinedPaymentSubmissionPath = String.fromEnvironment(
    'GILBIC_COMBINED_PAYMENT_SUBMISSION_PATH',
    defaultValue: '/api/mobile/v1/collector/collections/combined',
  );

  static const String collectorRenewalsPath = String.fromEnvironment(
    'GILBIC_COLLECTOR_RENEWALS_PATH',
    defaultValue: '/api/mobile/v1/collector/renewals',
  );

  static const String activityNotificationsPath = String.fromEnvironment(
    'GILBIC_ACTIVITY_NOTIFICATIONS_PATH',
    defaultValue: '/api/mobile/v1/activity-notifications',
  );

  static Uri get registerEndpoint => endpoint(registerPath);

  static Uri get loginEndpoint => endpoint(loginPath);

  static Uri get refreshEndpoint => endpoint(refreshPath);

  static Uri get meEndpoint => endpoint(mePath);

  static Uri get logoutEndpoint => endpoint(logoutPath);

  static Uri get collectorRouteEndpoint => endpoint(collectorRoutePath);

  static Uri get otherAreaSearchEndpoint => endpoint(otherAreaSearchPath);

  static Uri get delegatedAreaWorkEndpoint => endpoint(delegatedAreaWorkPath);

  static Uri get delegatedAreaAvailableScopesEndpoint =>
      endpoint(delegatedAreaAvailableScopesPath);

  static Uri get delegatedAreaIncomingRequestsEndpoint =>
      endpoint(delegatedAreaIncomingRequestsPath);

  static Uri get delegatedAreaOutgoingRequestsEndpoint =>
      endpoint(delegatedAreaOutgoingRequestsPath);

  static Uri get delegatedAreaActiveGrantsEndpoint =>
      endpoint(delegatedAreaActiveGrantsPath);

  static Uri get delegatedAreaRequestsEndpoint =>
      endpoint('/api/mobile/v1/collector/delegated-area/requests');

  static Uri delegatedAreaRequestActionEndpoint(
    String requestId,
    String action,
  ) =>
      endpoint(
        '/api/mobile/v1/collector/delegated-area/requests/'
        '${Uri.encodeComponent(requestId)}/${Uri.encodeComponent(action)}',
      );

  static Uri delegatedAreaGrantRevokeEndpoint(String grantId) => endpoint(
        '/api/mobile/v1/collector/delegated-area/grants/'
        '${Uri.encodeComponent(grantId)}/revoke',
      );

  static Uri get paymentSubmissionEndpoint => endpoint(paymentSubmissionPath);

  static Uri get combinedPaymentSubmissionEndpoint =>
      endpoint(combinedPaymentSubmissionPath);

  static Uri get collectorRenewalsEndpoint => endpoint(collectorRenewalsPath);

  static Uri collectorRenewalActionEndpoint(
    String requestId,
    String action,
  ) =>
      endpoint(
        '/api/mobile/v1/collector/renewals/'
        '${Uri.encodeComponent(requestId)}/${Uri.encodeComponent(action)}',
      );

  static Uri get activityNotificationsEndpoint =>
      endpoint(activityNotificationsPath);

  static Uri get managementClientRegistrationsEndpoint =>
      endpoint('/api/v1/management/client-registrations');

  static Uri managementClientCandidatesEndpoint(String query) => endpoint(
        '/api/v1/management/client-link-candidates?q=${Uri.encodeQueryComponent(query)}',
      );

  static Uri managementApproveClientRegistrationEndpoint(String userId) =>
      endpoint('/api/v1/management/client-registrations/$userId/approve');

  static Uri managementRejectClientRegistrationEndpoint(String userId) =>
      endpoint('/api/v1/management/client-registrations/$userId/reject');

  static Uri endpoint(String path) {
    final cleanBase = baseUrl.endsWith('/')
        ? baseUrl.substring(0, baseUrl.length - 1)
        : baseUrl;
    final normalizedPath = path.startsWith('/') ? path : '/$path';
    return Uri.parse('$cleanBase$normalizedPath');
  }
}
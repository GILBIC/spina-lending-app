const action = (key, label, path, options = {}) =>
  Object.freeze({ key, label, path, ...options });

export const ROLE_ENDPOINTS = Object.freeze({
  client: Object.freeze([
    action('client-account', 'My account', '/api/v1/account', { section: 'Account' }),
    action('client-loans', 'My loans', '/api/v1/client/loans', { section: 'Loans' }),
    action('client-payments', 'Payments & receipts', '/api/v1/client/payments', { section: 'Loans' }),
    action('client-renewals', 'Renewal requests', '/api/v1/client/renewals', { section: 'Requests' }),
    action('client-support', 'Support', '/api/v1/client/support', { section: 'Requests' }),
    action('client-gcash', 'Payment instructions', '/api/v1/client/gcash/config', { section: 'Payments' }),
    action('client-activity', 'Updates', '/api/v1/activity-notifications', { section: 'Updates' }),
  ]),
  employee: Object.freeze([
    action('employee-account', 'My account & devices', '/api/v1/account', { section: 'Updates & account' }),
    action('employee-activity', 'Updates', '/api/v1/activity-notifications', { section: 'Updates & account' }),
    action('employee-remittance', 'Remittance notifications', '/api/v1/notifications', {
      section: 'Pay & requests',
      permission: 'remittance.view',
    }),
    action('employee-support', 'Client support queue', '/api/v1/management/support', {
      section: 'Office functions',
      permission: 'support.manage',
    }),
  ]),
  collector: Object.freeze([
    action('collector-account', 'My account & devices', '/api/v1/account', { section: 'Account' }),
    action('collector-route', "Today's route", '/api/v1/collector/routes/today', {
      section: 'Collection',
      permission: 'route.view',
    }),
    action('collector-submit', 'Record collection', '/api/v1/collector/collections', {
      section: 'Collection',
      permission: 'collection.create',
      method: 'POST',
      financial: true,
    }),
    action('collector-remittance', 'Remittance notifications', '/api/v1/notifications', {
      section: 'Remittance',
      permission: 'remittance.view',
    }),
    action('collector-activity', 'Updates', '/api/v1/activity-notifications', { section: 'Updates' }),
  ]),
  management: Object.freeze([
    action('management-account', 'My account & devices', '/api/v1/account', { section: 'Administration' }),
    action('management-overview', 'Live overview', '/api/v1/management/dashboard-overview', {
      section: 'Overview',
      permission: 'management.dashboard.view',
    }),
    action('management-loans', 'Clients & loans', '/api/v1/management/loans', { section: 'Portfolio' }),
    action('management-alerts', 'Alerts & audit', '/api/v1/management/alerts-audit', {
      section: 'Overview',
      permission: 'management.dashboard.view',
    }),
    action('management-renewals', 'Renewal review', '/api/v1/management/renewals', {
      section: 'Review',
      permission: 'renewal.manage',
    }),
    action('management-support', 'Support review', '/api/v1/management/support', {
      section: 'Review',
      permission: 'support.manage',
    }),
    action('management-staff-devices', 'Staff & devices', '/api/v1/management/accounts', {
      section: 'Administration',
      permission: 'device.manage',
    }),
    action('management-remittance', 'Remittance review', '/api/v1/notifications', {
      section: 'Review',
      permission: 'remittance.view',
    }),
    action('management-client-registration', 'Client registrations', '/api/v1/management/client-registrations', {
      section: 'Review',
      permission: 'client.registration.approve',
    }),
    action('management-activity', 'Updates', '/api/v1/activity-notifications', { section: 'Updates' }),
  ]),
});

export function normalizeRole(value) {
  const normalized = String(value ?? '').trim().toLowerCase();
  return Object.hasOwn(ROLE_ENDPOINTS, normalized) ? normalized : 'unknown';
}

export function availableRoleActions(role, permissions = []) {
  const canonical = normalizeRole(role);
  if (canonical === 'unknown') {
    return [];
  }
  const allowed = new Set(
    Array.isArray(permissions)
      ? permissions.map((permission) => String(permission).trim()).filter(Boolean)
      : [],
  );
  return ROLE_ENDPOINTS[canonical].filter(
    (entry) => !entry.permission || allowed.has(entry.permission),
  );
}

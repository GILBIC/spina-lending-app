import { classifyLoanType } from './collector-contract.js';
import { availableRoleActions } from './roles.js';

const list = (value) => (Array.isArray(value) ? value : []);
const statusIs = (record, ...statuses) =>
  statuses.includes(String(record?.status ?? '').trim().toLowerCase());

function permissionsFromSession(session) {
  const values = [
    ...list(session?.permissions),
    ...list(session?.user?.permissions),
  ];
  return [...new Set(values.map((value) => String(value).trim()).filter(Boolean))];
}

export function buildClientViewModel({
  account = {},
  loans = {},
  payments = {},
  renewals = {},
  support = {},
  gcash = {},
  notifications = [],
} = {}) {
  const loanItems = list(loans.loans);
  const regularLoans = loanItems.filter(
    (loan) => classifyLoanType(loan.loan_type_name ?? loan.loan_type_code) === 'regular',
  );
  const sevenBySevenLoans = loanItems.filter(
    (loan) => classifyLoanType(loan.loan_type_name ?? loan.loan_type_code) === 'seven-by-seven',
  );
  const activeLoans = loanItems.filter((loan) => statusIs(loan, 'active'));
  const renewalItems = list(renewals.requests);
  const supportItems = list(support.requests);

  return {
    role: 'client',
    displayName:
      account?.profile?.full_name || loans?.client?.client_name || 'Client',
    client: loans.client ?? payments.client ?? renewals.client ?? support.client ?? null,
    allLoans: loanItems,
    activeLoans,
    regularLoans,
    sevenBySevenLoans,
    otherLoans: loanItems.filter(
      (loan) => classifyLoanType(loan.loan_type_name ?? loan.loan_type_code) === 'other',
    ),
    activeLoanCount: activeLoans.length,
    payments: list(payments.payments),
    renewals: renewalItems,
    supportRequests: supportItems,
    pendingRenewalCount: renewalItems.filter((request) => statusIs(request, 'pending')).length,
    openSupportCount: supportItems.filter((request) => statusIs(request, 'open', 'answered')).length,
    paymentInstructions: gcash && typeof gcash === 'object' ? gcash : {},
    notifications: list(notifications),
    account,
  };
}

export function buildCollectorRouteViewModel(route = {}) {
  const entries = list(route.entries);
  const orderedAreas = list(route.areas).map((value) => String(value));
  const discoveredAreas = [];
  for (const entry of entries) {
    const area = String(entry?.area ?? 'Unassigned');
    if (!orderedAreas.includes(area) && !discoveredAreas.includes(area)) {
      discoveredAreas.push(area);
    }
  }
  const areaOrder = [...orderedAreas, ...discoveredAreas];
  const areaGroups = areaOrder.map((name) => {
    const areaEntries = entries.filter(
      (entry) => String(entry?.area ?? 'Unassigned') === name,
    );
    return {
      name,
      entries: areaEntries,
      processedCount: areaEntries.filter((entry) => entry.processed_today === true).length,
      totalCount: areaEntries.length,
      unresolvedCount: areaEntries.filter(
        (entry) => entry.processed_today !== true || entry.attention_required === true,
      ).length,
    };
  });
  const unresolved = entries.filter(
    (entry) => entry.processed_today !== true || entry.attention_required === true,
  );

  return {
    role: 'collector',
    routeDate: route.route_date ?? null,
    collectorName: route.collector_name ?? 'Collector',
    expectedTotal: route.expected_total ?? '0.00',
    recordedTotal: route.recorded_total ?? route.collected_total ?? null,
    entries,
    areaGroups,
    unresolved,
    processedCount: entries.filter((entry) => entry.processed_today === true).length,
    totalCount: entries.length,
    routeRevision: route.route_revision ?? null,
    offline: route.offline === true,
  };
}

export function buildEmployeeViewModel({
  session = {},
  account = {},
  notifications = [],
  remittances = [],
  support = {},
} = {}) {
  const permissions = permissionsFromSession(session);
  const supportItems = list(support.requests);
  return {
    role: 'employee',
    displayName:
      account?.profile?.full_name || session?.user?.full_name || 'Employee',
    permissions,
    connectedActions: availableRoleActions('employee', permissions),
    notifications: list(notifications),
    remittances: list(remittances),
    supportRequests: supportItems,
    openSupportCount: supportItems.filter((request) => statusIs(request, 'open', 'answered')).length,
    account,
    unavailable: [
      { key: 'attendance', label: 'Attendance', message: 'Not connected in this MVP.' },
      { key: 'payroll', label: 'Payroll & payslips', message: 'Not connected in this MVP.' },
      { key: 'leave', label: 'Leave requests', message: 'Not connected in this MVP.' },
    ],
  };
}

export function buildManagementViewModel({
  account = {},
  overview = {},
  loans = {},
  alerts = {},
  renewals = {},
  support = {},
  registrations = {},
} = {}) {
  return {
    role: 'management',
    displayName: account?.profile?.full_name || 'Management',
    generatedAt: overview.generated_at ?? null,
    metrics: list(overview.metrics),
    loanSummary: loans.summary ?? {},
    loans: list(loans.loans),
    alerts: list(alerts.alerts),
    recentEvents: list(alerts.events),
    pendingRenewals: list(renewals.requests),
    openSupport: list(support.requests),
    pendingRegistrations: list(registrations.registrations),
    account,
  };
}

const CACHE_NAME = 'spina-company-shell-v23-treasury';
const SHELL_ASSETS = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/assets/app.css',
  '/assets/app.js',
  '/assets/treasury-api.js',
  '/assets/treasury-workspace.js',
  '/assets/treasury-payment-claim.js',
  '/assets/treasury-role-tasks.js',
  '/assets/api.js',
  '/assets/config.js',
  '/assets/session.js',
  '/assets/session-refresh.js',
  '/assets/screen-sharing.js',
  '/assets/roles.js',
  '/assets/ui.js',
  '/assets/presenters.js',
  '/assets/collector-contract.js',
  '/assets/collector-write-guard.js',
  '/assets/collector-workflow-contract.js',
  '/assets/collector-workflows.js',
  '/assets/collector-other-area.js',
  '/assets/collector-renewals.js',
  '/assets/collector-remittance.js',
  '/assets/collector-route-view.js',
  '/assets/collector-schedule-view.js',
  '/assets/collector-activity.js',
  '/assets/remittance-review.js',
  '/assets/staff-invite.js',
  '/assets/management-devices.js',
  '/assets/client-schedule.js',
  '/assets/client-workspace-state.js',
  '/assets/client-payment-details.js',
  '/assets/client-gcash.js',
  '/assets/client-statement.js',
  '/assets/employee-operations.js',
  '/assets/employee-workspace.js',
  '/assets/employee-workspace-content.js',
  '/assets/employee-workday.js',
  '/assets/employee-office-case.js',
  '/assets/employee-payslip-print.js',
  '/assets/cash-disbursement.js',
  '/assets/account-credentials.js',
  '/assets/client-account-admin.js',
  '/assets/client-documents.js',
  '/assets/payment-proofs.js',
  '/assets/area-management.js',
  '/assets/office-cif-selection.js',
  '/assets/office-cif-workflow.js',
  '/assets/office-onboarding.js',
  '/assets/office-privacy.js',
  '/assets/office-evidence-capture.js',
  '/assets/office-first-loan.js',
  '/assets/first-loan-disclosure.js',
  '/assets/collector-onboarding-visit.js',
  '/assets/office-cif-review.js',
  '/assets/office-cif-correction.js',
  '/assets/office-application-review.js',
  '/assets/office-application-entry.js',
  '/assets/management-financial-statements.js',
  '/assets/management-portfolio.js',
  '/assets/management-personal-updates.js',
  '/assets/management-support.js',
  '/assets/management-renewals.js',
  '/assets/management-workspace-tasks.js',
  '/assets/management-general-journal.js',
  '/assets/management-collection-actions.js',
  '/assets/management-journal-actions.js',
  '/assets/management-accounting.js',
  '/assets/management-tax-ecl.js',
  '/assets/management-tax-evidence.js',
  '/assets/management-loan-operations.js',
  '/assets/management-past-due-report.js',
  '/assets/management-alerts-audit.js',
  '/assets/roles/client.js',
  '/assets/roles/employee.js',
  '/assets/roles/collector.js',
  '/assets/roles/management.js',
  '/assets/spina-icon.svg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      cache.addAll(SHELL_ASSETS.map((asset) => new Request(asset, { cache: 'reload' }))),
    ),
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))),
  );
  self.clients.claim();
});

async function shellResponse(request, cacheKey = request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(cacheKey);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) {
    try {
      await cache.put(cacheKey, response.clone());
    } catch {
      // A storage quota failure must not discard an available network response.
    }
  }
  return response;
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  const { pathname } = url;

  if (
    request.method !== 'GET' ||
    url.origin !== self.location.origin ||
    pathname.startsWith('/api/') ||
    pathname.startsWith('/health/')
  ) {
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(shellResponse(request, '/index.html'));
    return;
  }

  event.respondWith(shellResponse(request));
});

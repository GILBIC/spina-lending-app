import { normalizeRole } from './roles.js';
import { emptyState, errorCard, escapeHtml, hasPermission, loadingPanel } from './ui.js';

const currentRequests = new WeakMap();
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function isUuid(value) {
  return typeof value === 'string' && UUID_PATTERN.test(value);
}

function isReviewForClient(review, clientId) {
  return review !== null
    && typeof review === 'object'
    && isUuid(review.client_id)
    && review.client_id.toLowerCase() === clientId.toLowerCase()
    && isUuid(review.cif_version_id)
    && review.review_scope === 'cif_information_only'
    && Number.isSafeInteger(review.version_number)
    && review.version_number > 0
    && typeof review.full_name === 'string'
    && typeof review.phone_number === 'string'
    && typeof review.present_address === 'string'
    && (review.email === null || typeof review.email === 'string');
}

function reviewMarkup(review) {
  const fields = [
    ['Full name', review.full_name],
    ['Phone number', review.phone_number],
    ['Email', review.email ?? 'Not provided'],
    ['Present address', review.present_address],
  ];
  return `<article class="data-card" data-client-id="${escapeHtml(review.client_id)}" data-cif-version-id="${escapeHtml(review.cif_version_id)}">
    <h3>CIF information review</h3>
    <p class="meta">CIF version ${review.version_number}</p>
    <p>Review the applicant's recorded name and contact information.</p>
    <div class="detail-grid">${fields.map(([label, value]) => `
      <div class="detail-item"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join('')}
    </div>
  </article>`;
}

export async function mountOfficeCifReview({ root, api, session, clientId }) {
  const request = {};
  currentRequests.set(root, request);
  root.innerHTML = '';

  const role = normalizeRole(session?.user?.role || session?.user?.roles?.[0]);
  if (!['employee', 'management'].includes(role)
    || !hasPermission(session, 'client_onboarding.requirement.review')) {
    root.innerHTML = emptyState('Office access and onboarding review permission are required.');
    return;
  }
  if (clientId == null || clientId === '') {
    root.innerHTML = emptyState('Select a Client for CIF information review.');
    return;
  }
  if (!isUuid(clientId)) {
    root.innerHTML = errorCard(new Error('A valid Client selection is required.'));
    return;
  }

  root.innerHTML = loadingPanel('Loading CIF information for review…');
  try {
    const review = await api.request(
      `/api/v1/management/clients/${encodeURIComponent(clientId)}/cif/review-summary`,
    );
    if (currentRequests.get(root) !== request) return;
    if (!isReviewForClient(review, clientId)) {
      throw new Error('The CIF review response is invalid or does not match the selected Client.');
    }
    root.innerHTML = reviewMarkup(review);
    return review;
  } catch (error) {
    if (currentRequests.get(root) !== request) return;
    root.innerHTML = errorCard(error, 'CIF information is unavailable.');
  }
}

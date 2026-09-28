import { escapeHtml as esc } from './ui.js';

const COMPONENTS = {
  principal: 'Principal', contractual_interest: 'Contractual interest',
  dst_upfront: 'DST deducted upfront', grt_in_repayments: 'GRT in repayments',
  renewal_offset: 'Renewal offset', other_upfront_deductions: 'Other upfront deductions',
  other_scheduled_charges: 'Other scheduled charges', total_upfront_deductions: 'Total upfront deductions',
  net_proceeds: 'Net proceeds', total_scheduled_payable: 'Total scheduled payable',
};
const VALUES = { amount_financed: 'Amount Financed', finance_charge_total: 'Finance charges', non_finance_charge_total: 'Non-finance charges' };
const object = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
const exact = (value) => typeof value === 'string' && /^\d{1,16}\.\d{2}$/.test(value);
const fail = () => { throw new Error('The saved disclosure response is invalid or belongs to another application.'); };

// Copy only public financial fields, even if an older/misconfigured server adds metadata.
export function publicDisclosureSnapshot(value) {
  if (!object(value) || !object(value.components) || !object(value.disclosure_values) || !Array.isArray(value.charge_items) || value.charge_items.length > 30) fail();
  const components = {};
  for (const key of Object.keys(COMPONENTS)) { if (!exact(value.components[key])) fail(); components[key] = value.components[key]; }
  const disclosure_values = {};
  for (const key of Object.keys(VALUES)) { const amount = value.disclosure_values[key]; if (amount !== null && !exact(amount)) fail(); disclosure_values[key] = amount; }
  const rate = value.disclosure_values.effective_interest_rate;
  if (rate !== null && (typeof rate !== 'string' || rate.length > 128 || !/^\d+(?:\.\d+)?$/.test(rate))) fail();
  disclosure_values.effective_interest_rate = rate;
  for (const key of ['rate_period', 'calculation_method']) { const text = value.disclosure_values[key]; if (text !== null && (typeof text !== 'string' || !text.trim() || text.length > 500)) fail(); disclosure_values[key] = text; }
  const charge_items = value.charge_items.map((item) => {
    if (!object(item) || typeof item.item_id !== 'string' || item.item_id.length > 200 || !['dst', 'grt_recovery', 'other_upfront', 'other_scheduled'].includes(item.kind) || !['upfront', 'repayments'].includes(item.timing) || !exact(item.amount)) fail();
    return { item_id: item.item_id, kind: item.kind, timing: item.timing, amount: item.amount };
  });
  return { components, disclosure_values, charge_items };
}

export function savedDisclosureSelection(value, application, reference) {
  if (!object(value) || value.id !== reference || value.application_version_id !== application.application_version_id || value.cif_version_id !== application.cif_version_id
      || !/^[0-9a-f]{64}$/.test(value.review_digest) || typeof value.approval_ready !== 'boolean' || !Array.isArray(value.blockers) || !value.blockers.every((item) => typeof item === 'string')) fail();
  const financial_snapshot = publicDisclosureSnapshot(value.financial_snapshot);
  if (value.approval_ready && (value.blockers.length || Object.values(financial_snapshot.disclosure_values).some((item) => item === null))) fail();
  return { id: reference, review_digest: value.review_digest, financial_snapshot, approval_ready: value.approval_ready };
}

export function disclosureBreakdown(value) {
  const { components, disclosure_values: values, charge_items: items } = publicDisclosureSnapshot(value);
  const row = (label, value) => `<div><strong>${esc(label)}:</strong> ${value === null ? 'Not provided' : esc(value)}</div>`;
  return `<section aria-label="Saved disclosure breakdown"><h4>Saved disclosure breakdown</h4><div class="detail-grid">
    ${Object.entries(COMPONENTS).map(([key, label]) => row(`${label} (PHP)`, components[key])).join('')}
    ${Object.entries(VALUES).map(([key, label]) => row(`${label} (PHP)`, values[key])).join('')}
    ${row('Effective interest rate', values.effective_interest_rate)}${row('Rate period', values.rate_period)}${row('Calculation method', values.calculation_method)}</div>
    <h5>Itemized charges</h5>${items.length ? items.map((item) => `<p>${esc(item.item_id)} · ${esc(item.timing)} · PHP ${esc(item.amount)}</p>`).join('') : '<p>No charges recorded.</p>'}</section>`;
}

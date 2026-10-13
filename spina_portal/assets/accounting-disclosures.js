import { escapeHtml as h, formatMoney } from './ui.js';

export const disclosureLabels = {
  cash_operating: 'Cash · operating', cash_investing: 'Cash · investing', cash_financing: 'Cash · financing', cash_internal: 'Cash · internal transfer',
  noncash_investing: 'Noncash · investing', noncash_financing: 'Noncash · financing', noncash_investing_financing: 'Noncash · investing and financing',
  noncash_operating: 'Noncash · operating adjustment', noncash_reclassification: 'Noncash · other reclassification',
};
export const disclosureStatusLabels = { complete_for_posted_ledger: 'Reviewed for the posted ledger', disclosure_policy_required: 'Financing policy needs review', disclosure_review_required: 'Journal disclosure review required', financing_reconciliation_required: 'Financing reconciliation required' };
const id = value => typeof value === 'string' && /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(value);
const check = (value, message = 'Disclosure evidence is incomplete. Refresh before continuing.') => { if (!value) throw Error(message); };
const exact = value => typeof value === 'string' && /^-?(0|[1-9]\d{0,15})\.\d{2}$/.test(value);
const cents = value => { check(exact(value)); return BigInt(value.replace('.', '')); };
const text = value => { const negative = value < 0n; const digits = (negative ? -value : value).toString().padStart(3, '0'); return `${negative ? '-' : ''}${digits.slice(0, -2)}.${digits.slice(-2)}`; };
const fingerprint = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const evidence = part => check(typeof part.evidence_reference === 'string' && part.evidence_reference.trim() === part.evidence_reference && part.evidence_reference.length > 0 && part.evidence_reference.length <= 1000 && fingerprint(part.evidence_digest));

export function disclosureRemaining(lines, parts) {
  const remaining = Object.fromEntries(lines.map(line => [line.id, cents(line.debit) + cents(line.credit)]));
  for (const part of parts) for (const key of ['debit_line_id', 'credit_line_id']) {
    check(Object.hasOwn(remaining, part[key])); remaining[part[key]] -= cents(part.amount);
  }
  return Object.fromEntries(Object.entries(remaining).map(([key, value]) => [key, text(value)]));
}

export function disclosureComponents(lines, parts, cashCodes, verifyCashPolicy = true) {
  check(Array.isArray(parts) && parts.length > 0 && parts.length <= 1000 && Array.isArray(lines) && lines.length > 1);
  const byId = new Map(lines.map(line => [line.id, line])), pairs = new Set(), cash = new Map();
  check(byId.size === lines.length);
  for (const part of parts) {
    evidence(part); check(Object.keys(part).sort().join(',') === 'amount,classification,credit_line_id,debit_line_id,evidence_digest,evidence_reference');
    const debit = byId.get(part.debit_line_id), credit = byId.get(part.credit_line_id), category = part.classification, amount = cents(part.amount);
    check(amount > 0n && debit && credit && Object.hasOwn(disclosureLabels, category));
    check(cents(debit.debit) > 0n && cents(debit.credit) === 0n && cents(credit.credit) > 0n && cents(credit.debit) === 0n);
    const pair = `${debit.id}/${credit.id}/${category}`; check(!pairs.has(pair), 'Combine duplicate debit, credit and category portions.'); pairs.add(pair);
    if (verifyCashPolicy) check([debit, credit].some(line => cashCodes.includes(line.account_code)) === category.startsWith('cash_'), 'Cash-connected portions must remain cash.');
    for (const [line, sign] of [[debit, 1n], [credit, -1n]]) if (cashCodes.includes(line.account_code)) {
      const key = `${line.id}/${category.slice(5)}`; cash.set(key, (cash.get(key) || 0n) + amount * sign);
    }
  }
  check(Object.values(disclosureRemaining(lines, parts)).every(value => value === '0.00'), 'Allocate every debit and credit exactly before review.');
  // A stale review can be displayed for editing under a new cash policy, but
  // its retained line identities, evidence and exact coverage must still parse.
  if (!verifyCashPolicy) return structuredClone(parts);
  const expected = new Map();
  for (const line of lines) if (cashCodes.includes(line.account_code)) {
    check(Array.isArray(line.cash_allocations) && line.cash_allocations.length > 0, 'Review cash-flow classifications first.');
    for (const part of line.cash_allocations) { const key = `${line.id}/${part.category}`; expected.set(key, (expected.get(key) || 0n) + cents(part.amount)); }
  }
  check(cash.size === expected.size && [...cash].every(([key, value]) => expected.get(key) === value), 'Match the retained cash-flow classifications.');
  return structuredClone(parts);
}

export function validateDisclosures(value) {
  check(value && Object.hasOwn(disclosureStatusLabels, value.status) && value.scope === 'all_posted_journals');
  check(id(value.book_id) && id(value.period?.id) && ['open', 'review', 'closed'].includes(value.period.status) && Array.isArray(value.cash_account_codes));
  check(Array.isArray(value.journals) && Array.isArray(value.blockers) && Array.isArray(value.noncash_components) && Array.isArray(value.financing_liabilities) && Array.isArray(value.financing_account_options));
  if (value.policy !== null) {
    const policy = value.policy;
    check(id(policy.id) && policy.book_id === value.book_id && policy.fiscal_period_id === value.period.id && id(policy.reporting_policy_id) && Number.isSafeInteger(policy.version) && policy.version > 0 && typeof policy.definition_valid === 'boolean');
    check(Array.isArray(policy.financing_account_codes) && policy.financing_account_codes.every(code => typeof code === 'string') && new Set(policy.financing_account_codes).size === policy.financing_account_codes.length);
    if (policy.definition_valid) check(policy.financing_account_codes.slice().sort().join(',') === value.financing_liabilities.map(row => row.account_code).sort().join(','));
  }
  const financing = new Map(value.financing_liabilities.map(row => [row.account_code, { cash: 0n, noncash: 0n, opening: 0n }]));
  check(financing.size === value.financing_liabilities.length);
  const coverage = value.coverage;
  for (const key of ['journal_count', 'reviewed_count', 'excluded_count', 'blocked_count']) check(Number.isSafeInteger(coverage?.[key]) && coverage[key] >= 0);
  check(coverage.journal_count === value.journals.length && coverage.journal_count === coverage.reviewed_count + coverage.excluded_count + coverage.blocked_count && coverage.blocked_count === value.blockers.length);
  const seen = new Set(), disclosed = [], counted = { reviewed_count: 0, excluded_count: 0, blocked_count: 0 };
  for (const row of value.journals) {
    check(id(row.journal_entry_id) && !seen.has(row.journal_entry_id) && typeof row.entry_number === 'string' && typeof row.posting_date === 'string' && Array.isArray(row.lines) && Number.isSafeInteger(row.review_version) && row.review_version >= 0);
    seen.add(row.journal_entry_id);
    check(row.reversal_of_entry_id === null || id(row.reversal_of_entry_id));
    check(row.source_digest === null || fingerprint(row.source_digest));
    for (const line of row.lines) check(id(line.id) && typeof line.account_code === 'string' && typeof line.account_name === 'string' && cents(line.debit) >= 0n && cents(line.credit) >= 0n && (cents(line.debit) === 0n) !== (cents(line.credit) === 0n));
    if (row.components !== null && (row.source_status !== 'current' || row.review_status !== 'current')) disclosureComponents(row.lines, row.components, value.cash_account_codes, false);
    if (row.source_status !== 'current' || (!row.protected_kind && row.review_status !== 'current')) counted.blocked_count++;
    else if (row.protected_kind) {
      check(['opening', 'opening_reversal', 'period_close'].includes(row.protected_kind)); counted.excluded_count++;
      if (row.protected_kind !== 'period_close') for (const line of row.lines) if (financing.has(line.account_code)) financing.get(line.account_code).opening += cents(line.credit) - cents(line.debit);
    }
    else {
      check(row.review_version > 0 && id(row.review_id) && fingerprint(row.source_digest));
      disclosureComponents(row.lines, row.components, value.cash_account_codes); counted.reviewed_count++;
      const byId = new Map(row.lines.map(line => [line.id, line]));
      for (const part of row.components) for (const [key, sign] of [['debit_line_id', -1n], ['credit_line_id', 1n]]) {
        const code = byId.get(part[key]).account_code;
        if (financing.has(code)) financing.get(code)[part.classification.startsWith('cash_') ? 'cash' : 'noncash'] += cents(part.amount) * sign;
      }
      for (const part of row.components) if (part.classification.startsWith('noncash_')) disclosed.push({ journal_entry_id: row.journal_entry_id, ...part });
    }
  }
  for (const key of Object.keys(counted)) check(coverage[key] === counted[key]);
  for (const blocker of value.blockers) check(seen.has(blocker.journal_entry_id) && typeof blocker.reason === 'string');
  if (value.policy?.definition_valid === true) {
    check(disclosed.length === value.noncash_components.length);
    for (let index = 0; index < disclosed.length; index++) for (const [key, expected] of Object.entries(disclosed[index])) check(value.noncash_components[index][key] === expected);
  } else check(value.status === 'disclosure_policy_required' && value.noncash_components.length === 0);
  for (const row of value.financing_liabilities) {
    check(typeof row.account_code === 'string' && typeof row.account_name === 'string' && typeof row.reconciled === 'boolean');
    const opening = cents(row.opening_balance), closing = cents(row.closing_balance);
    if (row.cash_changes === null || row.noncash_changes === null || row.opening_adjustments === null) check(!row.reconciled && row.difference === null && value.status !== 'complete_for_posted_ledger');
    else {
      check(coverage.blocked_count === 0 && value.policy?.definition_valid === true);
      const expected = financing.get(row.account_code);
      check(cents(row.cash_changes) === expected.cash && cents(row.noncash_changes) === expected.noncash && cents(row.opening_adjustments) === expected.opening);
      const difference = closing - opening - cents(row.cash_changes) - cents(row.noncash_changes) - cents(row.opening_adjustments);
      check(difference === cents(row.difference) && row.reconciled === (difference === 0n));
    }
  }
  if (value.status === 'complete_for_posted_ledger') check(value.policy?.definition_valid === true && coverage.blocked_count === 0 && value.financing_liabilities.every(row => row.reconciled));
  return value;
}

export function disclosureMarkup(value) {
  try { validateDisclosures(value); } catch { return '<p role="alert">Disclosure evidence is incomplete. Refresh before relying on these figures.</p>'; }
  const amount = value => value === null ? 'Unavailable' : formatMoney(value);
  return `<article class="data-card"><h3>Cash and noncash disclosure review</h3><p>${h(disclosureStatusLabels[value.status])}</p><p>${value.coverage.reviewed_count} reviewed · ${value.coverage.excluded_count} protected opening/closing entries · ${value.coverage.blocked_count} need review · ${value.coverage.journal_count} posted journals</p>
    ${value.blockers.map(row => `<p>${h(row.entry_number)} · ${h(row.reason.replaceAll('_', ' '))}</p>`).join('')}
    <h4>Reviewed noncash components</h4>${value.noncash_components.map(row => `<p>${h(row.entry_number)} · ${h(disclosureLabels[row.classification])} · ${h(amount(row.amount))}${row.reversal_of_entry_id ? ' · Reversal of an earlier journal' : ''}</p>`).join('') || '<p>No reviewed noncash components returned.</p>'}
    <h4>Financing liabilities</h4>${value.financing_liabilities.map(row => `<section><h5>${h(row.account_code)} · ${h(row.account_name)}</h5>${[['Opening', 'opening_balance'], ['Cash changes', 'cash_changes'], ['Noncash changes', 'noncash_changes'], ['Opening adjustments', 'opening_adjustments'], ['Closing', 'closing_balance'], ['Difference', 'difference']].map(([label, key]) => `<p>${label}: ${h(amount(row[key]))}</p>`).join('')}</section>`).join('') || '<p>No financing accounts selected in the retained policy.</p>'}
    <p>Coverage is limited to posted journals and selected financing liabilities. Gross noncash components are shown separately; no overall noncash total is inferred.</p></article>`;
}

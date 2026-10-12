import { sessionHasRole } from './roles.js';
import { escapeHtml as h, hasPermission, formatMoney } from './ui.js';
import { createSourceAccountingClient } from './management-source-accounting.js';
import { disclosureComponents, disclosureRemaining, disclosureMarkup, disclosureLabels, validateDisclosures } from './accounting-disclosures.js';

const scope = session => JSON.stringify([session?.user, session?.permissions, session?.access_token, session?.device_id]);
const check = (ok, message) => { if (!ok) throw Error(message); };
const button = (attribute, label) => `<button type="button" class="button button-outline" ${attribute}>${h(label)}</button>`;
const input = (name, label, value = '') => `<label>${h(label)}<input name="${name}" value="${h(value)}" required maxlength="${name === 'evidence_digest' ? 64 : 1000}"></label>`;
const select = (name, label, options) => `<label>${h(label)}<select name="${name}" required><option value="">Choose…</option>${options.map(([value, label]) => `<option value="${h(value)}">${h(label)}</option>`).join('')}</select></label>`;
const evidence = () => input('evidence_reference', 'Retained evidence reference') + input('evidence_digest', 'Evidence fingerprint (SHA-256)');
const fields = form => Object.fromEntries([...form.querySelectorAll('[name]')].map(element => [element.getAttribute('name'), element.value.trim()]));

export async function mountJournalDisclosures({ root, api, session, getSession = () => session, signal }) {
  const initial = scope(getSession());
  let disposed = false, busy = false, generation = 0, periods = [], periodId = '', report = null, selected = null, components = [], held = null, removers = [];
  const client = createSourceAccountingClient({ api, session, getSession, signal, onDenied: dispose });
  const canRead = () => sessionHasRole(getSession(), 'management') && hasPermission(getSession(), 'accounting.view');
  const canManage = () => canRead() && hasPermission(getSession(), 'accounting.journal.manage');
  function clearListeners() { for (const remove of removers) remove(); removers = []; }
  function dispose() { if (disposed) return; disposed = true; generation++; clearListeners(); client.dispose(); report = selected = held = null; components = []; periods = []; root.innerHTML = ''; signal?.removeEventListener('abort', dispose); }
  function live() { if (!canRead() || scope(getSession()) !== initial || signal?.aborted) dispose(); return !disposed; }
  function on(selector, event, action) { for (const element of root.querySelectorAll(selector)) { const listener = async e => { e.preventDefault(); if (!live() || busy) return; try { await action(element); } catch (error) { if (live()) failure(error); } }; element.addEventListener(event, listener); removers.push(() => element.removeEventListener(event, listener)); } }
  function frame(markup) { if (!live()) return; clearListeners(); root.innerHTML = `<h3>Cash and noncash disclosures</h3><div role="alert" data-disclosure-error></div>${markup}`; }
  function failure(error) {
    const target = root.querySelector('[data-disclosure-error]'); if (!target) return;
    target.innerHTML = `<p>${h(error.message)}</p>${client.pending() ? button('data-disclosure-retry', 'Retry unchanged request') + button('data-disclosure-restart', 'Refresh and start a new review') : ''}`;
    on('[data-disclosure-retry]', 'click', () => save(true));
    on('[data-disclosure-restart]', 'click', async () => { client.reset(); held = null; await load(); });
  }
  async function load() {
    if (!live() || client.pending()) return; const version = ++generation; busy = true; frame('<p role="status">Loading retained disclosure evidence…</p>');
    try {
      if (!periods.length) { const data = await client.get(''); check(Array.isArray(data.fiscal_periods), 'Accounting periods are unavailable.'); periods = data.fiscal_periods; }
      if (!live() || version !== generation) return;
      if (!periods.length) { frame('<p>No accounting period is available.</p>'); return; }
      periodId ||= periods[0].period_id;
      const data = await client.get(`/statements/disclosures?period_id=${encodeURIComponent(periodId)}`);
      if (!live() || version !== generation) return;
      report = validateDisclosures(data.disclosures); check(report.period.id === periodId, 'Disclosure report does not match the selected period.'); show();
    } catch (error) { if (live()) { frame(button('data-disclosure-reload', 'Reload disclosures')); failure(error); on('[data-disclosure-reload]', 'click', load); } }
    finally { busy = false; }
  }
  function show() {
    frame(`<label>Accounting period<select data-disclosure-period>${periods.map(period => `<option value="${h(period.period_id)}"${period.period_id === periodId ? ' selected' : ''}>${h(period.label)}</option>`).join('')}</select></label>${disclosureMarkup(report)}${canManage() && report.period.status === 'open' && report.reporting_policy_id ? button('data-disclosure-policy', 'Review financing accounts') : ''}
      ${report.journals.map((journal, index) => `<article class="data-card"><h4>${h(journal.entry_number)} · ${h(journal.posting_date)}</h4><p>${h((journal.protected_kind || journal.source_status !== 'current' && journal.source_status || journal.review_status).replaceAll('_', ' '))}</p>${canManage() && report.period.status === 'open' && report.policy?.definition_valid && !journal.protected_kind && journal.source_status === 'current' ? button(`data-disclosure-journal="${index}"`, 'Review components') : ''}</article>`).join('')}`);
    on('[data-disclosure-period]', 'change', async element => { periodId = element.value; await load(); });
    on('[data-disclosure-policy]', 'click', policyForm);
    on('[data-disclosure-journal]', 'click', element => { selected = report.journals[Number(element.getAttribute('data-disclosure-journal'))]; components = structuredClone(selected.components || []); journalForm(); });
  }
  function policyForm() {
    frame(`<h4>Financing liability accounts</h4><p>Select every liability whose cash flows are financing activities. An empty selection records that none apply to this period.</p><form data-disclosure-policy-form>${report.financing_account_options.map(row => `<label>${h(row.code)} · ${h(row.name)}<select name="finance_${h(row.code)}"><option value="no"${!report.policy?.financing_account_codes.includes(row.code) ? ' selected' : ''}>Exclude</option><option value="yes"${report.policy?.financing_account_codes.includes(row.code) ? ' selected' : ''}>Include</option></select></label>`).join('')}${evidence()}<button type="submit">Review financing policy</button></form>${button('data-disclosure-back', 'Back')}`);
    on('[data-disclosure-back]', 'click', show);
    on('[data-disclosure-policy-form]', 'submit', form => {
      const values = fields(form), codes = report.financing_account_options.filter(row => values[`finance_${row.code}`] === 'yes').map(row => row.code);
      confirm('/statements/disclosure-policy', { request_id: crypto.randomUUID(), book_id: report.book_id, reporting_policy_id: report.reporting_policy_id, expected_version: report.policy?.version || 0, financing_account_codes: codes, evidence_reference: values.evidence_reference, evidence_digest: values.evidence_digest, reviewed: true }, 'policy_id', `<p>Financing accounts: ${h(codes.join(', ') || 'None')}</p>`, policyForm);
    });
  }
  function partsMarkup(editable = true) { return components.map((part, index) => { const debit = selected.lines.find(line => line.id === part.debit_line_id), credit = selected.lines.find(line => line.id === part.credit_line_id); return `<p>${h(debit?.account_name || 'Unavailable debit')} → ${h(credit?.account_name || 'Unavailable credit')} · ${h(disclosureLabels[part.classification])} · ${h(formatMoney(part.amount))} · ${h(part.evidence_reference)} ${editable ? button(`data-disclosure-remove="${index}"`, 'Remove portion') : ''}</p>`; }).join(''); }
  function journalForm() {
    const remaining = disclosureRemaining(selected.lines, components);
    frame(`<h4>${h(selected.entry_number)} · ${h(selected.posting_date)}</h4>${selected.reversal_of_entry_id ? '<p>This reverses an earlier journal. Review the reversal separately.</p>' : ''}
      ${selected.lines.map(line => `<p>${h(line.account_code)} · ${h(line.account_name)} · Debit ${h(formatMoney(line.debit))} · Credit ${h(formatMoney(line.credit))} · Remaining ${h(formatMoney(remaining[line.id]))}</p>`).join('')}${partsMarkup()}
      <form data-disclosure-part>${select('debit_line_id', 'Debit account', selected.lines.filter(line => line.debit !== '0.00').map(line => [line.id, `${line.account_code} · ${line.account_name}`]))}${select('credit_line_id', 'Credit account', selected.lines.filter(line => line.credit !== '0.00').map(line => [line.id, `${line.account_code} · ${line.account_name}`]))}${input('amount', 'Portion amount (PHP, two decimals)')}${select('classification', 'Cash or noncash disclosure', Object.entries(disclosureLabels))}${evidence()}<button type="submit">Add portion</button></form>
      <form data-disclosure-review>${input('reason', 'Reason for this disclosure', selected.reason || '')}${evidence()}<button type="submit">Review complete journal</button></form>${button('data-disclosure-back', 'Back')}`);
    on('[data-disclosure-back]', 'click', show);
    on('[data-disclosure-remove]', 'click', element => { components.splice(Number(element.getAttribute('data-disclosure-remove')), 1); journalForm(); });
    on('[data-disclosure-part]', 'submit', form => {
      const part = fields(form); check(/^(0|[1-9]\d{0,15})\.\d{2}$/.test(part.amount) && part.amount !== '0.00', 'Enter a positive amount with two decimals.');
      check(selected.lines.some(line => line.id === part.debit_line_id && line.debit !== '0.00') && selected.lines.some(line => line.id === part.credit_line_id && line.credit !== '0.00'), 'Choose the original debit and credit accounts.');
      check(Object.values(disclosureRemaining(selected.lines, [...components, part])).every(value => !value.startsWith('-')), 'This portion exceeds a remaining line amount.');
      components.push(part); journalForm();
    });
    on('[data-disclosure-review]', 'submit', form => {
      const values = fields(form), exact = disclosureComponents(selected.lines, components, report.cash_account_codes);
      check(values.reason.length > 0, 'Retain the reason for this classification.');
      confirm('/statements/disclosure-reviews', { request_id: crypto.randomUUID(), book_id: report.book_id, disclosure_policy_id: report.policy.id, journal_entry_id: selected.journal_entry_id, expected_version: selected.review_version, source_digest: selected.source_digest, components: exact, ...values, reviewed: true }, 'review_id', `<p>${h(selected.entry_number)} · ${h(values.reason)}</p>${partsMarkup(false)}`, journalForm);
    });
  }
  function confirm(path, body, resultKey, summary, back) {
    check(body.evidence_reference.length > 0 && /^[a-f0-9]{64}$/.test(body.evidence_digest), 'Retain an evidence reference and SHA-256 fingerprint.');
    held = { path, body, resultKey };
    frame(`<h4>Review before retaining</h4>${summary}<p>Evidence: ${h(body.evidence_reference)}</p><p>The current book, period, source and review version will be checked when saved.</p>${button('data-disclosure-save', 'Retain reviewed evidence')}${button('data-disclosure-back', 'Back to edit')}`);
    on('[data-disclosure-save]', 'click', () => save(false)); on('[data-disclosure-back]', 'click', back);
  }
  async function save(retry) {
    check(canManage() && held, 'Current Management accounting access is required.'); busy = true;
    try { if (retry) await client.retry(); else { const attempt = held; await client.submit(attempt.path, attempt.body, result => result[attempt.resultKey] === attempt.body.request_id); } held = null; }
    finally { busy = false; }
    await load();
  }
  signal?.addEventListener('abort', dispose, { once: true });
  await load(); return dispose;
}

import { sessionHasRole } from './roles.js';
import { escapeHtml as h, formatMoney, hasPermission } from './ui.js';
import { createTreasuryClient } from './treasury-api.js';
import { createSourceAccountingClient } from './management-source-accounting.js';

const families = {
  settlement: ['Accepted cash count', 'Transfers the actual accepted count from existing Collector custody cash and records any unidentified excess. Loan principal and interest are not recognized again.'],
  recognition: ['Recognized Collector credit', 'Moves identified excess into Collector credit payable. This step does not move cash.'],
  credit_application: ['Credit used for remittance', 'Reduces Collector credit payable and settles the approved part of the custody obligation on the acceptance date. Actual cash received has its own accounting review.'],
  return_debit: ['Actual return debit', 'Records actual cash paid and its separately evidenced fee. The principal remains awaiting the Collector’s received confirmation.'],
  return_confirmation: ['Received return confirmation', 'Clears the confirmed credit payable and return amount awaiting receipt. This step does not move cash again.'],
  return_reversal: ['Actual incoming return reversal', 'Records only the principal actually received back and restores that amount of Collector credit. The earlier fee remains unchanged.'],
};
const id = (v) => typeof v === 'string' && /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(v);
const digest = (v) => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
const money = (v) => typeof v === 'string' && /^(0|[1-9]\d{0,15})\.\d{2}$/.test(v);
const date = (v) => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(v)) && new Date(v).toISOString().slice(0, 10) === v;
const check = (ok, message = 'The retained Collector accounting evidence is incomplete. Reload current evidence before continuing.') => { if (!ok) throw Error(message); };
const pick = (v, keys) => Object.fromEntries(keys.map((key) => [key, v[key]]));
const cents = (v) => BigInt(v.replace('.', ''));
const button = (key, label) => `<button type="button" class="button button-outline" ${key}>${h(label)}</button>`;
const choice = (name, label, rows, selected) => `<label>${h(label)}<select name="${name}" required><option value="">Choose…</option>${rows.map(([value, text]) => `<option value="${h(value)}"${value === selected ? ' selected' : ''}>${h(text)}</option>`).join('')}</select></label>`;
const facts = (rows) => `<dl>${rows.map(([label, value]) => `<dt>${h(label)}</dt><dd>${h(value)}</dd>`).join('')}</dl>`;
const mounts = new WeakMap();

export function collectorSource(value, { bookId, accountId, sourceKind, sourceId }) {
  check(Object.hasOwn(families, sourceKind) && value?.book_id === bookId && value.treasury_account_id === accountId && value.source_kind === sourceKind && value.source_id === sourceId && [bookId, accountId, sourceId, value.fiscal_period_id].every(id) && digest(value.source_digest) && date(value.posting_date) && money(value.amount) && value.amount !== '0.00' && money(value.fee));
  const rows = value.lines;
  check(Array.isArray(rows) && rows.length >= 2 && rows.length <= 3);
  for (const line of rows) check(Number.isInteger(line.line_number) && line.line_number > 0 && ['1010', '1030', '1020', '1060', '2210', '2220', '5240'].includes(line.account_code) && typeof line.account_snapshot?.name === 'string' && line.account_snapshot.name.trim() && money(line.debit) && money(line.credit) && (line.debit === '0.00') !== (line.credit === '0.00'));
  check(new Set(rows.map((line) => line.line_number)).size === rows.length && new Set(rows.map((line) => line.account_code)).size === rows.length);
  check(rows.reduce((n, line) => n + cents(line.debit) - cents(line.credit), 0n) === 0n);
  function exact(code, side, amount) { const line = rows.find((row) => row.account_code === code); check(line && cents(line[side]) === amount && line[side === 'debit' ? 'credit' : 'debit'] === '0.00'); }
  const amount = cents(value.amount), fee = cents(value.fee), cash = rows.filter((row) => ['1010', '1030'].includes(row.account_code));
  let split;
  if (value.custody_split !== undefined) {
    check(['settlement', 'credit_application'].includes(sourceKind));
    const keys = ['gross_obligation', 'authorized_credit_amount', 'physical_cash_required', 'physical_amount', 'excess_amount'];
    check(value.custody_split && keys.every(key => money(value.custody_split[key])));
    split = pick(value.custody_split, keys);
    check(cents(split.authorized_credit_amount) > 0n && cents(split.gross_obligation) === cents(split.authorized_credit_amount) + cents(split.physical_cash_required) && cents(split.physical_amount) === cents(split.physical_cash_required) + cents(split.excess_amount));
  }
  if (sourceKind !== 'return_debit') check(fee === 0n);
  if (sourceKind === 'settlement') {
    check(cash.length === 1); exact(cash[0].account_code, 'debit', amount);
    const custody = rows.find((row) => row.account_code === '1020');
    if (split) {
      check(cents(split.physical_amount) === amount);
      const principal = cents(split.physical_cash_required), excess = cents(split.excess_amount);
      check(rows.length === 1 + (principal ? 1 : 0) + (excess ? 1 : 0));
      if (principal) exact('1020', 'credit', principal); else check(!custody);
      if (excess) exact('2210', 'credit', excess);
    } else {
      check(custody && custody.debit === '0.00' && cents(custody.credit) > 0n && cents(custody.credit) <= amount);
      const excess = amount - cents(custody.credit); check(rows.length === (excess ? 3 : 2)); if (excess) exact('2210', 'credit', excess);
    }
  } else if (sourceKind === 'credit_application') {
    check(split && cents(split.authorized_credit_amount) === amount && cash.length === 0 && rows.length === 2);
    exact('2220', 'debit', amount); exact('1020', 'credit', amount);
  } else if (sourceKind === 'recognition' || sourceKind === 'return_confirmation') {
    check(rows.length === 2 && cash.length === 0);
    exact(sourceKind === 'recognition' ? '2210' : '2220', 'debit', amount);
    exact(sourceKind === 'recognition' ? '2220' : '1060', 'credit', amount);
  } else {
    check(cash.length === 1 && rows.length === (fee ? 3 : 2));
    exact(cash[0].account_code, sourceKind === 'return_debit' ? 'credit' : 'debit', amount + fee);
    exact(sourceKind === 'return_debit' ? '1060' : '2220', sourceKind === 'return_debit' ? 'debit' : 'credit', amount);
    if (fee) exact('5240', 'debit', fee);
  }
  return { ...pick(value, ['book_id', 'source_kind', 'source_id', 'treasury_account_id', 'fiscal_period_id', 'posting_date', 'amount', 'fee', 'source_digest']), ...(split ? {custody_split: split} : {}), lines: rows.map((line) => ({ ...pick(line, ['line_number', 'account_code', 'debit', 'credit']), name: line.account_snapshot.name })) };
}

export async function mountCollectorAccounting({ root, api, session, getSession = () => session, signal }) {
  mounts.get(root)?.();
  const controller = new AbortController();
  let disposed = false, generation = 0, busy = false, listeners = [], book, wallets = [], accountId = '', sourceKind = 'settlement', reference = '', source, prepared, intent;
  const can = () => sessionHasRole(getSession(), 'management') && hasPermission(getSession(), 'accounting.view') && hasPermission(getSession(), 'accounting.journal.manage');
  const sessionScope = (value) => JSON.stringify([value?.user, value?.permissions, value?.access_token, value?.device_id]);
  const initialScope = sessionScope(session);
  function current(g = generation) { if (!disposed && sessionScope(getSession()) !== initialScope) denied(); return !disposed && !signal?.aborted && g === generation; }
  function clearListeners() { listeners.forEach((remove) => remove()); listeners = []; }
  function dispose() { if (disposed) return; disposed = true; generation++; controller.abort(); client.dispose(); treasury.dispose(); clearListeners(); book = source = prepared = intent = null; wallets = []; root.innerHTML = ''; signal?.removeEventListener('abort', dispose); if (mounts.get(root) === dispose) mounts.delete(root); }
  function denied() { dispose(); root.innerHTML = '<p role="alert">Accounting access changed. Reopen with current permissions.</p>'; }
  const client = createSourceAccountingClient({ api, session, getSession, signal: controller.signal, onDenied: denied });
  const treasury = createTreasuryClient(api, { getSession, signal: controller.signal, onDenied: denied });
  function frame(markup) { if (!current()) return; clearListeners(); root.innerHTML = `<p data-message role="status"></p>${markup}`; }
  function message(text) { const node = root.querySelector('[data-message]'); if (node) node.textContent = text; }
  function lock(value) { busy = value; for (const tag of ['button', 'input', 'select']) for (const node of root.querySelectorAll(tag)) node.disabled = value; }
  function listen(selector, event, action) { for (const node of root.querySelectorAll(selector)) { const handler = async (e) => { e.preventDefault(); if (!current() || busy) return; try { await action(node); } catch (error) { if (current()) message(error.message); } }; node.addEventListener(event, handler); listeners.push(() => node.removeEventListener(event, handler)); } }
  const scope = (sourceId) => ({ bookId: book.book_id, accountId, sourceKind, sourceId });
  async function freshBook(g) { const result = await client.get('/book'); if (!current(g)) return; const value = result.book; check(value?.status === 'configured' && id(value.book_id) && typeof value.entity_label === 'string', 'Configure the accounting book before reviewing Collector accounting.'); if (book && book.book_id !== value.book_id) { denied(); throw Error('Accounting book changed.'); } book = value; }
  async function load() {
    check(!client.pending(), 'Recover the unchanged request first.'); const g = ++generation; source = prepared = intent = null; frame('<p>Loading authorized Treasury accounts…</p>'); lock(true);
    try { check(can(), 'Current Management journal permission is required.'); await freshBook(g); if (!current(g)) return; const workspace = await treasury.workspace(); if (!current(g)) return; check(workspace.enabled && workspace.owner_configured, 'Treasury account access must be configured first.'); wallets = workspace.accounts.filter((row) => row.balance !== null && row.active !== false && ['physical_cash', 'gcash', 'bank'].includes(row.kind)); check(wallets.every((row) => id(row.id) && typeof row.alias === 'string')); render(); }
    catch (error) { if (current(g)) { frame(`<p role="alert">${h(error.message)}</p>${button('data-load', 'Retry read')}`); listen('[data-load]', 'click', load); } }
    finally { if (current(g)) lock(false); }
  }
  function details(value) { return [['Accounting step', families[value.source_kind][0]], ['Source reference', value.source_id], ['Treasury account', wallets.find((row) => row.id === value.treasury_account_id)?.alias || value.treasury_account_id], ['Actual posting date', value.posting_date], ['Source amount', formatMoney(value.amount)], ['Actual transaction fee', formatMoney(value.fee)], ...(value.custody_split ? [['Gross custody settled', formatMoney(value.custody_split.gross_obligation)], ['Credit applied', formatMoney(value.custody_split.authorized_credit_amount)], ['Actual cash received', formatMoney(value.custody_split.physical_amount)], ['Cash excess', formatMoney(value.custody_split.excess_amount)]] : []), ...value.lines.map((line) => [`${line.account_code} · ${line.name}`, `Debit ${formatMoney(line.debit)} · Credit ${formatMoney(line.credit)}`])]; }
  function coordinates(value) { return JSON.stringify({ ...value, lines: value.lines.map(({ name, ...line }) => line) }); }
  function validatePreparation(value, expected = null, requestId = null, preparationId = null) {
    const row = value?.preparation; check(row && id(row.id) && row.actor_user_id === getSession()?.user?.id && digest(row.confirmation_token) && (!requestId || row.request_id === requestId) && (!preparationId || row.id === preparationId));
    const projected = collectorSource({ ...row.snapshot, source_digest: row.source_digest }, scope(row.source_id));
    for (const key of ['book_id', 'source_kind', 'source_id']) check(row[key] === projected[key]);
    if (expected) check(coordinates(projected) === coordinates(expected));
    if (value.posting !== null) { const posted = value.posting; check(posted && posted.preparation_id === row.id && id(posted.journal_entry_id) && typeof posted.exact_posted === 'boolean' && typeof posted.correction_pending === 'boolean'); for (const key of ['book_id', 'source_kind', 'source_id']) check(posted[key] === row[key]); check(posted.posting_date === projected.posting_date && posted.amount === projected.amount); }
    return true;
  }
  async function lookup(recover = false) {
    check(wallets.some((row) => row.id === accountId) && Object.hasOwn(families, sourceKind) && id(reference), 'Choose an authorized account, accounting step and existing source or preparation reference.');
    const g = ++generation; source = prepared = intent = null; render(); lock(true);
    try { await freshBook(g); if (!current(g)) return;
      if (recover) { const result = await client.get(`/collector/preparations/${reference}`); if (!current(g)) return; validatePreparation(result, null, null, reference); prepared = result; source = collectorSource({ ...result.preparation.snapshot, source_digest: result.preparation.source_digest }, scope(result.preparation.source_id)); }
      else { const result = await client.get(`/collector/${sourceKind}/${reference}/review`); if (!current(g)) return; source = collectorSource(result, scope(reference)); }
      render();
    } catch (error) { if (current(g)) { source = prepared = null; render(); message(error.message); } }
    finally { if (current(g)) lock(false); }
  }
  function review(posting) {
    check(can() && source && !client.pending()); const expected = source, requestId = crypto.randomUUID(), held = prepared;
    const title = posting ? 'Post Collector accounting' : 'Prepare Collector accounting';
    intent = posting ? { path: `/collector/preparations/${held.preparation.id}/post`, body: { source_digest: held.preparation.source_digest, confirmation_token: held.preparation.confirmation_token, confirm: true }, validate: (v) => validatePreparation(v, expected, null, held.preparation.id) && v.posting?.exact_posted === true && v.journal_entry_id === v.posting.journal_entry_id } : { path: `/collector/${expected.source_kind}/${expected.source_id}/prepare`, body: { source_digest: expected.source_digest, request_id: requestId }, validate: (v) => validatePreparation(v, expected, requestId) };
    frame(`<article><h4 tabindex="-1" data-title>${h(title)}</h4>${facts(details(expected))}<p>${h(families[expected.source_kind][1])}</p><p>${posting ? 'Posts this exact reviewed source to the General Ledger. It does not approve, initiate or transfer operational money.' : 'Retains this exact evidence. Posting requires a separate confirmation.'}</p>${button('data-confirm', `Confirm: ${title}`)}${button('data-cancel', 'Cancel')}</article>`); root.querySelector('[data-title]')?.focus(); listen('[data-confirm]', 'click', () => send(false)); listen('[data-cancel]', 'click', render);
  }
  async function send(retry) { const g = generation, held = intent; check(can() && held); lock(true); try { await freshBook(g); if (!current(g)) return; const value = retry ? await client.retry() : await client.submit(held.path, held.body, held.validate); if (!current(g)) return; prepared = value; source = collectorSource({ ...value.preparation.snapshot, source_digest: value.preparation.source_digest }, scope(value.preparation.source_id)); intent = null; render(); } catch (error) { if (current(g)) { frame(`<p role="alert">${h(error.message)}</p><p>The result is not confirmed. Retry this unchanged request to recover it.</p>${button('data-retry', 'Retry unchanged request')}${[409, 422].includes(error.status) ? button('data-reload', 'Reload current evidence') : ''}`); listen('[data-retry]', 'click', () => send(true)); listen('[data-reload]', 'click', () => { client.reset(); return load(); }); } } finally { if (current(g)) lock(false); } }
  function render() {
    frame(`<h4>${h(book.entity_label)}</h4><p>Review existing accepted cash counts, recognized credits and actual return steps. A reservation does not create another liability. Balanced journal lines alone do not establish accounting readiness.</p><p>Credit applications have separate cash and liability reviews. Opening balances, historical corrections and disputed custody need additional reviewed evidence. Current permissions for every affected account are required.</p><form data-collector-lookup>${choice('account_id', 'Treasury account for this step', wallets.map((row) => [row.id, row.alias]), accountId)}${choice('source_kind', 'Accounting step', Object.entries(families).map(([key, row]) => [key, row[0]]), sourceKind)}<label>Existing source or saved preparation reference<input name="reference" maxlength="36" required /></label><p>Use the accepted settlement reference for a cash count, credit-entry reference for recognition or receipt confirmation, and action reference for an actual return debit.</p><button type="submit" class="button button-primary">Load Collector accounting review</button>${button('data-recover', 'Open saved preparation')}</form><section data-evidence>${source ? `${facts(details(source))}<p>${h(families[source.source_kind][1])}</p>${prepared ? `<h4>${prepared.posting?.exact_posted ? 'Collector accounting posted' : 'Collector accounting prepared for review'}</h4><p>Preparation ${h(prepared.preparation.id)}</p>${prepared.posting ? `<p>Journal ${h(prepared.posting.journal_entry_id)}</p><p>${prepared.posting.correction_pending ? 'A later source change requires correction review.' : 'Retained exact posting evidence is available.'}</p>` : button('data-post-collector', 'Review Collector posting')}` : button('data-prepare-collector', 'Prepare Collector accounting')}` : ''}</section>`);
    root.querySelector('[name="reference"]').value = reference;
    function formValues(form) { const value = (key) => String(form.querySelector(`[name="${key}"]`)?.value || '').trim(); accountId = value('account_id'); sourceKind = value('source_kind'); reference = value('reference'); }
    listen('[data-collector-lookup]', 'submit', (form) => { formValues(form); return lookup(); }); listen('[data-recover]', 'click', () => { formValues(root.querySelector('[data-collector-lookup]')); return lookup(true); });
    for (const event of ['input', 'change']) listen('[data-collector-lookup]', event, () => { source = prepared = intent = null; root.querySelector('[data-evidence]').innerHTML = ''; });
    listen('[data-prepare-collector]', 'click', () => review(false)); listen('[data-post-collector]', 'click', () => review(true));
  }
  mounts.set(root, dispose); signal?.addEventListener('abort', dispose, { once: true }); if (signal?.aborted) { dispose(); return dispose; } await load(); return dispose;
}

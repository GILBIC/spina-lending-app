import { sessionHasRole } from './roles.js';
import { escapeHtml as h, formatMoney, hasPermission } from './ui.js';
import { createTreasuryClient } from './treasury-api.js';
import { createSourceAccountingClient } from './management-source-accounting.js';

const id = (v) => typeof v === 'string' && /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(v);
const digest = (v) => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
const money = (v) => typeof v === 'string' && /^(0|[1-9]\d{0,15})\.\d{2}$/.test(v);
const date = (v) => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(v)) && new Date(v).toISOString().slice(0, 10) === v;
const check = (ok, text = 'The retained payout accounting evidence is incomplete. Reload before continuing.') => { if (!ok) throw Error(text); };
const pick = (v, keys) => Object.fromEntries(keys.map((key) => [key, v[key]]));
const cents = (v) => BigInt(v.replace('.', ''));
const button = (key, text) => `<button type="button" class="button button-outline" ${key}>${h(text)}</button>`;
const choice = (name, label, rows, selected) => `<label>${h(label)}<select name="${name}" required><option value="">Choose…</option>${rows.map(([value, text]) => `<option value="${h(value)}"${value === selected ? ' selected' : ''}>${h(text)}</option>`).join('')}</select></label>`;
const facts = (rows) => `<dl>${rows.map(([label, value]) => `<dt>${h(label)}</dt><dd>${h(value)}</dd>`).join('')}</dl>`;
const mounts = new WeakMap();

export function payoutSource(value, { bookId, accountId, payoutId, stage }) {
  check(['debit', 'completion'].includes(stage) && value?.book_id === bookId && value.payout_id === payoutId && value.stage === stage && value.treasury_account_id === accountId && [value.event_id, value.loan_id, value.client_id, value.fiscal_period_id].every(id) && (stage === 'completion' ? id(value.disbursement_event_id) : value.disbursement_event_id === null) && digest(value.source_digest) && date(value.posting_date) && money(value.amount) && value.amount !== '0.00' && money(value.fee) && (stage === 'debit' || value.fee === '0.00'));
  check(Array.isArray(value.lines) && value.lines.length === (value.fee === '0.00' ? 2 : 3));
  const rows = value.lines;
  for (const line of rows) check(Number.isInteger(line.line_number) && line.line_number > 0 && ['1030', '1050', '1100', '5240'].includes(line.account_code) && typeof line.account_snapshot?.name === 'string' && money(line.debit) && money(line.credit));
  check(new Set(rows.map((line) => line.line_number)).size === rows.length);
  const transit = rows.filter((line) => line.account_code === '1050'), counter = rows.filter((line) => line.account_code === (stage === 'debit' ? '1030' : '1100')), fee = rows.filter((line) => line.account_code === '5240');
  check(transit.length === 1 && counter.length === 1 && fee.length === (value.fee === '0.00' ? 0 : 1));
  check(transit[0][stage === 'debit' ? 'debit' : 'credit'] === value.amount && transit[0][stage === 'debit' ? 'credit' : 'debit'] === '0.00');
  check(cents(counter[0][stage === 'debit' ? 'credit' : 'debit']) === cents(value.amount) + cents(value.fee) && counter[0][stage === 'debit' ? 'debit' : 'credit'] === '0.00');
  if (fee.length) check(fee[0].debit === value.fee && fee[0].credit === '0.00');
  return { ...pick(value, ['book_id', 'payout_id', 'stage', 'event_id', 'loan_id', 'client_id', 'disbursement_event_id', 'treasury_account_id', 'fiscal_period_id', 'posting_date', 'amount', 'fee', 'source_digest']), lines: rows.map((line) => ({ ...pick(line, ['line_number', 'account_code', 'debit', 'credit']), name: line.account_snapshot.name })) };
}

export async function mountPayoutAccounting({ root, api, session, getSession = () => session, signal }) {
  mounts.get(root)?.();
  const controller = new AbortController();
  let disposed = false, generation = 0, busy = false, listeners = [], book, wallets = [], accountId = '', stage = 'debit', reference = '', source, prepared, intent;
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
  function scope(payoutId) { return { bookId: book.book_id, accountId, payoutId, stage }; }
  async function freshBook(g) { const result = await client.get('/book'); if (!current(g)) return; const value = result.book; check(value?.status === 'configured' && id(value.book_id) && typeof value.entity_label === 'string', 'Configure the accounting book before reviewing payouts.'); if (book && book.book_id !== value.book_id) { denied(); throw Error('Accounting book changed.'); } book = value; }
  async function load() {
    check(!client.pending(), 'Recover the unchanged request first.'); const g = ++generation; source = prepared = intent = null; frame('<p>Loading authorized wallets…</p>'); lock(true);
    try { check(can(), 'Current Management journal permission is required.'); await freshBook(g); if (!current(g)) return; const workspace = await treasury.workspace(); if (!current(g)) return; check(workspace.enabled && workspace.owner_configured); wallets = workspace.accounts.filter((row) => row.balance !== null && row.active !== false && ['gcash', 'bank'].includes(row.kind)); check(wallets.every((row) => id(row.id) && typeof row.alias === 'string')); render(); }
    catch (error) { if (current(g)) { frame(`<p role="alert">${h(error.message)}</p>${button('data-load', 'Retry read')}`); listen('[data-load]', 'click', load); } }
    finally { if (current(g)) lock(false); }
  }
  function details(value) { return [['Payout reference', value.payout_id], ['Actual stage', value.stage === 'debit' ? 'Verified wallet debit' : 'Borrower completion'], ['Funding wallet', wallets.find((row) => row.id === value.treasury_account_id)?.alias || value.treasury_account_id], ['Loan reference', value.loan_id], ['Actual posting date', value.posting_date], ['Principal', formatMoney(value.amount)], ['Actual wallet fee', formatMoney(value.fee)], ...value.lines.map((line) => [`${line.account_code}  -  ${line.name}`, `Debit ${formatMoney(line.debit)}  -  Credit ${formatMoney(line.credit)}`])]; }
  function validatePreparation(value, expected = null, requestId = null, preparationId = null) {
    const row = value?.preparation; check(row && id(row.id) && row.actor_user_id === getSession()?.user?.id && digest(row.confirmation_token) && (!requestId || row.request_id === requestId) && (!preparationId || row.id === preparationId));
    const projected = payoutSource({ ...row.snapshot, source_digest: row.source_digest }, scope(row.payout_id));
    for (const key of ['book_id', 'payout_id', 'stage', 'event_id', 'treasury_account_id', 'loan_id', 'client_id', 'disbursement_event_id']) check(row[key] === projected[key]);
    if (expected) check(JSON.stringify(projected) === JSON.stringify(expected));
    if (value.posting !== null) { const posted = value.posting; check(posted && posted.preparation_id === row.id && id(posted.journal_entry_id) && typeof posted.exact_posted === 'boolean' && typeof posted.correction_pending === 'boolean'); for (const key of ['book_id', 'payout_id', 'stage', 'event_id', 'treasury_account_id', 'loan_id', 'client_id', 'disbursement_event_id', 'source_digest']) check(posted[key] === row[key]); }
    return true;
  }
  async function lookup(recover = false) {
    check(wallets.some((row) => row.id === accountId) && id(reference), 'Choose the authorized funding wallet and an existing payout or preparation reference.');
    const g = ++generation; source = prepared = intent = null; render(); lock(true);
    try { await freshBook(g); if (!current(g)) return;
      if (recover) { const result = await client.get(`/treasury/payout-preparations/${reference}`); if (!current(g)) return; validatePreparation(result, null, null, reference); prepared = result; source = payoutSource({ ...result.preparation.snapshot, source_digest: result.preparation.source_digest }, scope(result.preparation.payout_id)); }
      else { const query = new URLSearchParams({ stage }); const result = await client.get(`/treasury/payouts/${reference}/review?${query}`); if (!current(g)) return; source = payoutSource(result, scope(reference)); }
      render();
    } catch (error) { if (current(g)) { source = prepared = null; render(); message(error.message); } }
    finally { if (current(g)) lock(false); }
  }
  function review(posting) {
    check(can() && source && !client.pending()); const expected = source, requestId = crypto.randomUUID(), held = prepared;
    const title = posting ? 'Post payout stage accounting' : 'Prepare payout stage accounting';
    intent = posting ? { path: `/treasury/payout-preparations/${held.preparation.id}/post`, body: { source_digest: held.preparation.source_digest, confirmation_token: held.preparation.confirmation_token, confirm: true }, validate: (v) => validatePreparation(v, expected, null, held.preparation.id) && v.posting?.exact_posted === true && v.journal_entry_id === v.posting.journal_entry_id } : { path: `/treasury/payouts/${expected.payout_id}/prepare`, body: { stage, source_digest: expected.source_digest, request_id: requestId }, validate: (v) => validatePreparation(v, expected, requestId) };
    frame(`<article><h4 tabindex="-1" data-title>${h(title)}</h4>${facts(details(expected))}<p>${posting ? 'Posts this exact actual stage. A debit records cash leaving for loan payout transit; borrower completion moves that same principal into the approved loan receivable without another cash credit.' : 'Retains these exact actual-stage coordinates. Posting requires a separate confirmation.'}</p>${button('data-confirm', `Confirm: ${title}`)}${button('data-cancel', 'Cancel')}</article>`); root.querySelector('[data-title]')?.focus(); listen('[data-confirm]', 'click', () => send(false)); listen('[data-cancel]', 'click', render);
  }
  async function send(retry) { const g = generation, held = intent; check(can() && held); lock(true); try { await freshBook(g); if (!current(g)) return; const value = retry ? await client.retry() : await client.submit(held.path, held.body, held.validate); if (!current(g)) return; prepared = value; intent = null; render(); } catch (error) { if (current(g)) { frame(`<p role="alert">${h(error.message)}</p><p>The result is not confirmed. Retry this unchanged request to recover it.</p>${button('data-retry', 'Retry unchanged request')}${[409, 422].includes(error.status) ? button('data-reload', 'Reload current evidence') : ''}`); listen('[data-retry]', 'click', () => send(true)); listen('[data-reload]', 'click', () => { client.reset(); return load(); }); } } finally { if (current(g)) lock(false); } }
  function render() {
    frame(`<h4>${h(book.entity_label)}</h4><p>Review the actual wallet debit separately from protected borrower completion. Receipt by a Collector leaves the amount in loan payout transit. Overall accounting readiness remains a separate review.</p><form data-payout-lookup>${choice('account_id', 'Funding wallet', wallets.map((row) => [row.id, row.alias]), accountId)}${choice('stage', 'Actual stage', [['debit', 'Verified wallet debit'], ['completion', 'Borrower completion']], stage)}<label>Existing payout or saved preparation reference<input name="reference" maxlength="36" required /></label><button type="submit" class="button button-primary">Load payout accounting review</button>${button('data-recover', 'Open saved preparation')}</form><section data-evidence>${source ? `${facts(details(source))}${prepared ? `<h4>${prepared.posting?.exact_posted ? 'Payout stage accounting posted' : 'Payout stage prepared for review'}</h4><p>Preparation ${h(prepared.preparation.id)}</p>${prepared.posting ? `<p>Journal ${h(prepared.posting.journal_entry_id)}</p><p>${prepared.posting.correction_pending ? 'A later source change requires correction review.' : 'Retained exact posting evidence is available.'}</p>` : button('data-post-payout', 'Review payout stage posting')}` : button('data-prepare-payout', 'Prepare payout stage accounting')}` : ''}</section>`);
    root.querySelector('[name="reference"]').value = reference;
    function formValues(form) { const value = (key) => String(form.querySelector(`[name="${key}"]`)?.value || '').trim(); accountId = value('account_id'); stage = value('stage'); reference = value('reference'); }
    listen('[data-payout-lookup]', 'submit', (form) => { formValues(form); return lookup(); }); listen('[data-recover]', 'click', () => { formValues(root.querySelector('[data-payout-lookup]')); return lookup(true); });
    for (const event of ['input', 'change']) listen('[data-payout-lookup]', event, () => { source = prepared = intent = null; root.querySelector('[data-evidence]').innerHTML = ''; });
    listen('[data-prepare-payout]', 'click', () => review(false)); listen('[data-post-payout]', 'click', () => review(true));
  }
  mounts.set(root, dispose); signal?.addEventListener('abort', dispose, { once: true }); if (signal?.aborted) { dispose(); return dispose; } await load(); return dispose;
}

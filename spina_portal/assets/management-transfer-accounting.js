import { sessionHasRole } from './roles.js';
import { escapeHtml as h, formatMoney, hasPermission } from './ui.js';
import { createTreasuryClient } from './treasury-api.js';
import { createSourceAccountingClient } from './management-source-accounting.js';

const id = (v) => typeof v === 'string' && /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(v);
const digest = (v) => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
const money = (v) => typeof v === 'string' && /^(0|[1-9]\d{0,15})\.\d{2}$/.test(v);
const date = (v) => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(v)) && new Date(v).toISOString().slice(0, 10) === v;
const check = (ok, text = 'The retained transfer accounting evidence is incomplete. Reload before continuing.') => { if (!ok) throw Error(text); };
const pick = (v, keys) => Object.fromEntries(keys.map((key) => [key, v[key]]));
const cents = (v) => BigInt(v.replace('.', ''));
const button = (key, text) => `<button type="button" class="button button-outline" ${key}>${h(text)}</button>`;
const choice = (name, label, rows, selected) => `<label>${h(label)}<select name="${name}" required><option value="">Choose…</option>${rows.map(([value, text]) => `<option value="${h(value)}"${value === selected ? ' selected' : ''}>${h(text)}</option>`).join('')}</select></label>`;
const facts = (rows) => `<dl>${rows.map(([label, value]) => `<dt>${h(label)}</dt><dd>${h(value)}</dd>`).join('')}</dl>`;
const mounts = new WeakMap();

export function transferSource(value, { bookId, sourceAccountId, destinationAccountId, transferId, leg }) {
  check(['source', 'destination'].includes(leg) && sourceAccountId !== destinationAccountId && value?.book_id === bookId && value.transfer_id === transferId && value.leg === leg && value.source_account_id === sourceAccountId && value.destination_account_id === destinationAccountId && value.treasury_account_id === (leg === 'source' ? sourceAccountId : destinationAccountId) && [value.event_id, value.fiscal_period_id].every(id) && digest(value.source_digest) && date(value.posting_date) && money(value.amount) && value.amount !== '0.00' && money(value.fee) && (leg === 'source' || value.fee === '0.00'));
  check(Array.isArray(value.lines) && value.lines.length === (value.fee === '0.00' ? 2 : 3));
  const rows = value.lines;
  for (const line of rows) check(Number.isInteger(line.line_number) && line.line_number > 0 && ['1010', '1030', '1040', '5240'].includes(line.account_code) && typeof line.account_snapshot?.name === 'string' && money(line.debit) && money(line.credit));
  check(new Set(rows.map((line) => line.line_number)).size === rows.length);
  const transit = rows.filter((line) => line.account_code === '1040'), cash = rows.filter((line) => ['1010', '1030'].includes(line.account_code)), fee = rows.filter((line) => line.account_code === '5240');
  check(transit.length === 1 && cash.length === 1 && fee.length === (value.fee === '0.00' ? 0 : 1));
  check(transit[0][leg === 'source' ? 'debit' : 'credit'] === value.amount && transit[0][leg === 'source' ? 'credit' : 'debit'] === '0.00');
  check(cents(cash[0][leg === 'source' ? 'credit' : 'debit']) === cents(value.amount) + cents(value.fee) && cash[0][leg === 'source' ? 'debit' : 'credit'] === '0.00');
  if (fee.length) check(fee[0].debit === value.fee && fee[0].credit === '0.00');
  return { ...pick(value, ['book_id', 'transfer_id', 'leg', 'event_id', 'source_account_id', 'destination_account_id', 'treasury_account_id', 'fiscal_period_id', 'posting_date', 'amount', 'fee', 'source_digest']), lines: rows.map((line) => ({ ...pick(line, ['line_number', 'account_code', 'debit', 'credit']), name: line.account_snapshot.name })) };
}

export async function mountTransferAccounting({ root, api, session, getSession = () => session, signal }) {
  mounts.get(root)?.();
  const controller = new AbortController();
  let disposed = false, generation = 0, busy = false, listeners = [], book, wallets = [], sourceAccountId = '', destinationAccountId = '', leg = 'source', reference = '', source, prepared, mappingIds, intent;
  const can = () => sessionHasRole(getSession(), 'management') && hasPermission(getSession(), 'accounting.view') && hasPermission(getSession(), 'accounting.journal.manage');
  const sessionScope = (value) => JSON.stringify([value?.user, value?.permissions, value?.access_token, value?.device_id]);
  const initialScope = sessionScope(session);
  function current(g = generation) { if (!disposed && sessionScope(getSession()) !== initialScope) denied(); return !disposed && !signal?.aborted && g === generation; }
  function clearListeners() { listeners.forEach((remove) => remove()); listeners = []; }
  function dispose() { if (disposed) return; disposed = true; generation++; controller.abort(); client.dispose(); treasury.dispose(); clearListeners(); book = source = prepared = mappingIds = intent = null; wallets = []; root.innerHTML = ''; signal?.removeEventListener('abort', dispose); if (mounts.get(root) === dispose) mounts.delete(root); }
  function denied() { dispose(); root.innerHTML = '<p role="alert">Accounting access changed. Reopen with current permissions.</p>'; }
  const client = createSourceAccountingClient({ api, session, getSession, signal: controller.signal, onDenied: denied });
  const treasury = createTreasuryClient(api, { getSession, signal: controller.signal, onDenied: denied });
  function frame(markup) { if (!current()) return; clearListeners(); root.innerHTML = `<p data-message role="status"></p>${markup}`; }
  function message(text) { const node = root.querySelector('[data-message]'); if (node) node.textContent = text; }
  function lock(value) { busy = value; for (const tag of ['button', 'input', 'select']) for (const node of root.querySelectorAll(tag)) node.disabled = value; }
  function listen(selector, event, action) { for (const node of root.querySelectorAll(selector)) { const handler = async (e) => { e.preventDefault(); if (!current() || busy) return; try { await action(node); } catch (error) { if (current()) message(error.message); } }; node.addEventListener(event, handler); listeners.push(() => node.removeEventListener(event, handler)); } }
  function scope(transferId) { return { bookId: book.book_id, sourceAccountId, destinationAccountId, transferId, leg }; }
  async function freshBook(g) { const result = await client.get('/book'); if (!current(g)) return; const value = result.book; check(value?.status === 'configured' && id(value.book_id) && typeof value.entity_label === 'string', 'Configure the accounting book before reviewing transfers.'); if (book && book.book_id !== value.book_id) { denied(); throw Error('Accounting book changed.'); } book = value; }
  async function load() {
    check(!client.pending(), 'Recover the unchanged request first.'); const g = ++generation; source = prepared = mappingIds = intent = null; frame('<p>Loading authorized wallets…</p>'); lock(true);
    try { check(can(), 'Current Management journal permission is required.'); await freshBook(g); if (!current(g)) return; const workspace = await treasury.workspace(); if (!current(g)) return; check(workspace.enabled && workspace.owner_configured); wallets = workspace.accounts.filter((row) => row.balance !== null && row.active !== false && ['physical_cash', 'gcash', 'bank'].includes(row.kind)); check(wallets.every((row) => id(row.id) && typeof row.alias === 'string')); render(); }
    catch (error) { if (current(g)) { frame(`<p role="alert">${h(error.message)}</p>${button('data-load', 'Retry read')}`); listen('[data-load]', 'click', load); } }
    finally { if (current(g)) lock(false); }
  }
  function details(value) { return [['Transfer reference', value.transfer_id], ['Actual leg', value.leg === 'source' ? 'Source debit' : 'Destination credit'], ['Source wallet', wallets.find((row) => row.id === value.source_account_id)?.alias || value.source_account_id], ['Destination wallet', wallets.find((row) => row.id === value.destination_account_id)?.alias || value.destination_account_id], ['Actual posting date', value.posting_date], ['Principal', formatMoney(value.amount)], ['Source transaction fee', formatMoney(value.fee)], ...value.lines.map((line) => [`${line.account_code} · ${line.name}`, `Debit ${formatMoney(line.debit)} · Credit ${formatMoney(line.credit)}`])]; }
  function validatePreparation(value, expected = null, requestId = null, preparationId = null) {
    const row = value?.preparation; check(row && id(row.id) && row.actor_user_id === getSession()?.user?.id && digest(row.confirmation_token) && (!requestId || row.request_id === requestId) && (!preparationId || row.id === preparationId) && id(row.source_mapping_id) && id(row.destination_mapping_id));
    const projected = transferSource({ ...row.snapshot, source_digest: row.source_digest }, scope(row.transfer_id));
    for (const key of ['book_id', 'transfer_id', 'leg', 'event_id', 'source_account_id', 'destination_account_id']) check(row[key] === projected[key]);
    if (expected) check(JSON.stringify(projected) === JSON.stringify(expected) && row.source_mapping_id === mappingIds.source_mapping_id && row.destination_mapping_id === mappingIds.destination_mapping_id);
    if (value.posting !== null) { const posted = value.posting; check(posted && posted.preparation_id === row.id && id(posted.journal_entry_id) && typeof posted.exact_posted === 'boolean' && typeof posted.correction_pending === 'boolean'); for (const key of ['book_id', 'transfer_id', 'leg', 'event_id', 'source_account_id', 'destination_account_id', 'source_digest']) check(posted[key] === row[key]); }
    return true;
  }
  async function lookup(recover = false) {
    check(wallets.some((row) => row.id === sourceAccountId) && wallets.some((row) => row.id === destinationAccountId) && sourceAccountId !== destinationAccountId && id(reference), 'Choose two authorized wallets and an existing transfer or preparation reference.');
    const g = ++generation; source = prepared = mappingIds = intent = null; render(); lock(true);
    try { await freshBook(g); if (!current(g)) return;
      if (recover) { const result = await client.get(`/treasury/transfer-preparations/${reference}`); if (!current(g)) return; validatePreparation(result, null, null, reference); prepared = result; mappingIds = pick(result.preparation, ['source_mapping_id', 'destination_mapping_id']); source = transferSource({ ...result.preparation.snapshot, source_digest: result.preparation.source_digest }, scope(result.preparation.transfer_id)); }
      else { mappingIds = {}; for (const [key, accountId] of [['source_mapping_id', sourceAccountId], ['destination_mapping_id', destinationAccountId]]) { const result = await client.get(`/treasury/accounts/${accountId}/cash-mapping`); if (!current(g)) return; check(result.book_id === book.book_id && result.treasury_account_id === accountId && id(result.mapping?.id) && result.mapping.book_id === book.book_id && result.mapping.treasury_account_id === accountId, 'Both wallets need an explicit cash mapping before transfer review.'); mappingIds[key] = result.mapping.id; } const query = new URLSearchParams({ leg, ...mappingIds }); const result = await client.get(`/treasury/transfers/${reference}/review?${query}`); if (!current(g)) return; source = transferSource(result, scope(reference)); }
      render();
    } catch (error) { if (current(g)) { source = prepared = mappingIds = null; render(); message(error.message); } }
    finally { if (current(g)) lock(false); }
  }
  function review(posting) {
    check(can() && source && !client.pending()); const expected = source, requestId = crypto.randomUUID(), held = prepared;
    const title = posting ? 'Post transfer leg accounting' : 'Prepare transfer leg accounting';
    intent = posting ? { path: `/treasury/transfer-preparations/${held.preparation.id}/post`, body: { source_digest: held.preparation.source_digest, confirmation_token: held.preparation.confirmation_token, confirm: true }, validate: (v) => validatePreparation(v, expected, null, held.preparation.id) && v.posting?.exact_posted === true && v.journal_entry_id === v.posting.journal_entry_id } : { path: `/treasury/transfers/${expected.transfer_id}/prepare`, body: { leg, ...mappingIds, source_digest: expected.source_digest, request_id: requestId }, validate: (v) => validatePreparation(v, expected, requestId) };
    frame(`<article><h4 tabindex="-1" data-title>${h(title)}</h4>${facts(details(expected))}<p>${posting ? 'Posts only this verified actual leg to cash and transfer funds in transit, including its actual source fee. This does not record or initiate a bank transfer.' : 'Retains these exact actual-leg coordinates. Posting requires a separate confirmation.'}</p>${button('data-confirm', `Confirm: ${title}`)}${button('data-cancel', 'Cancel')}</article>`); root.querySelector('[data-title]')?.focus(); listen('[data-confirm]', 'click', () => send(false)); listen('[data-cancel]', 'click', render);
  }
  async function send(retry) { const g = generation, held = intent; check(can() && held); lock(true); try { await freshBook(g); if (!current(g)) return; const value = retry ? await client.retry() : await client.submit(held.path, held.body, held.validate); if (!current(g)) return; prepared = value; intent = null; render(); } catch (error) { if (current(g)) { frame(`<p role="alert">${h(error.message)}</p><p>The result is not confirmed. Retry this unchanged request to recover it.</p>${button('data-retry', 'Retry unchanged request')}${[409, 422].includes(error.status) ? button('data-reload', 'Reload current evidence') : ''}`); listen('[data-retry]', 'click', () => send(true)); listen('[data-reload]', 'click', () => { client.reset(); return load(); }); } } finally { if (current(g)) lock(false); } }
  function render() {
    frame(`<h4>${h(book.entity_label)}</h4><p>Review each independently verified transfer leg on its own actual date. Funds can remain in transit until the destination arrives. Overall accounting readiness remains a separate review.</p><form data-transfer-lookup>${choice('source_account_id', 'Source wallet', wallets.map((row) => [row.id, row.alias]), sourceAccountId)}${choice('destination_account_id', 'Destination wallet', wallets.map((row) => [row.id, row.alias]), destinationAccountId)}${choice('leg', 'Actual leg', [['source', 'Source debit'], ['destination', 'Destination credit']], leg)}<label>Existing transfer or saved preparation reference<input name="reference" maxlength="36" required /></label><button type="submit" class="button button-primary">Load transfer accounting review</button>${button('data-recover', 'Open saved preparation')}</form><section data-evidence>${source ? `${facts(details(source))}${prepared ? `<h4>${prepared.posting?.exact_posted ? 'Transfer leg accounting posted' : 'Transfer leg prepared for review'}</h4><p>Preparation ${h(prepared.preparation.id)}</p>${prepared.posting ? `<p>Journal ${h(prepared.posting.journal_entry_id)}</p><p>${prepared.posting.correction_pending ? 'A later source change requires correction review.' : 'Retained exact posting evidence is available.'}</p>` : button('data-post-transfer', 'Review transfer leg posting')}` : button('data-prepare-transfer', 'Prepare transfer leg accounting')}` : ''}</section>`);
    root.querySelector('[name="reference"]').value = reference;
    function formValues(form) { const value = (key) => String(form.querySelector(`[name="${key}"]`)?.value || '').trim(); sourceAccountId = value('source_account_id'); destinationAccountId = value('destination_account_id'); leg = value('leg'); reference = value('reference'); }
    listen('[data-transfer-lookup]', 'submit', (form) => { formValues(form); return lookup(); }); listen('[data-recover]', 'click', () => { formValues(root.querySelector('[data-transfer-lookup]')); return lookup(true); });
    for (const event of ['input', 'change']) listen('[data-transfer-lookup]', event, () => { source = prepared = mappingIds = intent = null; root.querySelector('[data-evidence]').innerHTML = ''; });
    listen('[data-prepare-transfer]', 'click', () => review(false)); listen('[data-post-transfer]', 'click', () => review(true));
  }
  mounts.set(root, dispose); signal?.addEventListener('abort', dispose, { once: true }); if (signal?.aborted) { dispose(); return dispose; } await load(); return dispose;
}

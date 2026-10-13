import { sessionHasRole } from './roles.js';
import { escapeHtml as h, hasPermission } from './ui.js';
import { createSourceAccountingClient } from './management-source-accounting.js';

const roles = { '1060': ['debit', 'Returns awaiting confirmation'], '2210': ['credit', 'Unidentified excess owed'], '2220': ['credit', 'Collector credit owed'] };
const id = v => typeof v === 'string' && /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(v);
const day = v => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(v)) && new Date(v).toISOString().slice(0, 10) === v;
const money = (v, signed = false) => typeof v === 'string' && (signed ? /^-?(0|[1-9]\d{0,15})\.\d{2}$/ : /^(0|[1-9]\d{0,15})\.\d{2}$/).test(v);
const integer = v => Number.isSafeInteger(v) && v >= 0;
const cents = v => BigInt(v.replace('.', ''));
const check = ok => { if (!ok) throw Error('Collector control evidence is incomplete. Refresh before continuing.'); };
const pick = (v, keys) => Object.fromEntries(keys.map(key => [key, v[key]]));
const mounts = new WeakMap();
export function collectorControlSchedule(value, bookId) {
  check(value?.book?.status === 'configured' && value.book.book_id === bookId && id(bookId) && typeof value.book.entity_label === 'string' && day(value.as_of) && value.business_timezone === 'Asia/Manila' && value.balance_basis === 'debit_minus_credit' && value.comprehensive_source_coverage === false && typeof value.controls_reconciled === 'boolean');
  check(['movement_count', 'unproven_movement_count', 'correction_count', 'limit', 'offset'].every(key => integer(value[key])) && value.limit >= 1 && value.limit <= 500 && value.unproven_movement_count <= value.movement_count);
  check(Array.isArray(value.controls) && value.controls.length === 3 && new Set(value.controls.map(row => row.account_code)).size === 3);
  for (const row of value.controls) {
    check(Object.hasOwn(roles, row.account_code) && roles[row.account_code][0] === row.normal_balance && ['source_balance', 'ledger_balance', 'difference', 'source_amount', 'ledger_amount'].every(key => money(row[key], true)) && integer(row.unregistered_line_count));
    const direction = row.normal_balance === 'debit' ? 1n : -1n;
    check(cents(row.source_amount) === direction * cents(row.source_balance) && cents(row.ledger_amount) === direction * cents(row.ledger_balance) && cents(row.difference) === cents(row.ledger_balance) - cents(row.source_balance));
  }
  check(Array.isArray(value.movements) && value.movements.length === Math.min(value.limit, Math.max(0, value.movement_count - value.offset)));
  for (const row of value.movements) check(roles[row.account_code] && day(row.effective_date) && row.effective_date <= value.as_of && money(row.signed_amount, true) && ['collector_case', 'collector_resolution', 'collector_credit', 'collector_return_debit', 'collector_entry'].includes(row.source_type) && id(row.source_id) && typeof row.exact_posted === 'boolean');
  const capacity = value.current_capacity;
  check(capacity && typeof capacity.observed_at === 'string' && /(?:Z|\+00:00)$/.test(capacity.observed_at) && !Number.isNaN(Date.parse(capacity.observed_at)) && ['unidentified_amount', 'outstanding_amount', 'reserved_amount', 'available_amount'].every(key => money(capacity[key])));
  check(cents(capacity.outstanding_amount) - cents(capacity.reserved_amount) === cents(capacity.available_amount));
  if (value.controls_reconciled) check(value.unproven_movement_count === 0 && value.correction_count === 0 && value.controls.every(row => row.difference === '0.00' && row.unregistered_line_count === 0) && value.movements.every(row => row.exact_posted));
  return { ...pick(value, ['as_of', 'business_timezone', 'balance_basis', 'movement_count', 'unproven_movement_count', 'correction_count', 'limit', 'offset', 'controls_reconciled', 'comprehensive_source_coverage']), book: pick(value.book, ['status', 'book_id', 'kind', 'entity_label']), current_capacity: pick(capacity, ['observed_at', 'unidentified_amount', 'outstanding_amount', 'reserved_amount', 'available_amount']), controls: value.controls.map(row => pick(row, ['account_code', 'normal_balance', 'source_balance', 'ledger_balance', 'difference', 'source_amount', 'ledger_amount', 'unregistered_line_count'])), movements: value.movements.map(row => pick(row, ['account_code', 'effective_date', 'signed_amount', 'source_type', 'source_id', 'exact_posted'])) };
}

export async function mountCollectorControls({ root, api, session, getSession = () => session, signal }) {
  mounts.get(root)?.();
  const controller = new AbortController(), scope = user => JSON.stringify([user?.user, user?.permissions, user?.access_token, user?.device_id]), initial = scope(session);
  let disposed = false, generation = 0, busy = false, listeners = [], bookId = null, value = null, asOf = '', offset = 0;
  const client = createSourceAccountingClient({ api, session, getSession, signal: controller.signal, onDenied: denied });
  function clearListeners() { listeners.forEach(remove => remove()); listeners = []; }
  function dispose() { if (disposed) return; disposed = true; generation++; value = null; bookId = null; client.dispose(); controller.abort(); clearListeners(); root.innerHTML = ''; signal?.removeEventListener('abort', dispose); if (mounts.get(root) === dispose) mounts.delete(root); }
  function denied() { dispose(); root.innerHTML = '<p role="alert">Collector control access changed. Reopen with current permissions.</p>'; }
  function current(g = generation) { if (!disposed && scope(getSession()) !== initial) denied(); return !disposed && !signal?.aborted && g === generation; }
  function listen(selector, event, action) { const node = root.querySelector(selector); if (!node) return; const handler = e => { e.preventDefault(); if (current() && !busy) void action(node); }; node.addEventListener(event, handler); listeners.push(() => node.removeEventListener(event, handler)); }
  function render(message = '') {
    if (!current()) return; clearListeners();
    const capacity = value?.current_capacity;
    root.innerHTML = `<p role="status">${h(message)}</p><form data-controls-filter><label>Balances through Manila date<input name="as_of" type="date" value="${h(asOf)}" /></label><button type="submit">Load Collector controls</button></form><section data-controls-evidence>${value ? `<h4>${h(value.book.entity_label)}</h4><p>Balances through ${h(value.as_of)} · Asia/Manila</p><p>${value.controls_reconciled ? 'These Collector controls reconcile.' : 'Collector control evidence needs review.'} Full accounting readiness remains a separate review.</p>${value.controls.map(row => `<article><h4>${h(row.account_code)} · ${roles[row.account_code][1]}</h4><p>Ledger amount: PHP ${h(row.ledger_amount)}</p><p>Source amount: PHP ${h(row.source_amount)}</p><p>Normal balance: ${h(row.normal_balance)}</p><p>Difference (debits less credits): PHP ${h(row.difference)}</p><p>Unregistered lines: ${row.unregistered_line_count}</p></article>`).join('')}<h4>Current operational capacity</h4><p>Observed ${h(capacity.observed_at)}. These current amounts are separate from the selected historical cutoff.</p><p>Unidentified excess: PHP ${h(capacity.unidentified_amount)}</p><p>Outstanding credit: PHP ${h(capacity.outstanding_amount)}</p><p>Reserved within outstanding: PHP ${h(capacity.reserved_amount)}</p><p>Available credit: PHP ${h(capacity.available_amount)}</p><p>Reservations are included in outstanding credit; they do not add another liability.</p><h4>Dated source movements</h4><p>${value.movements.length ? `${value.offset + 1}–${value.offset + value.movements.length}` : '0'} of ${value.movement_count} source movements</p><p>Unproven movements: ${value.unproven_movement_count} · Sources needing correction: ${value.correction_count}</p>${value.movements.map(row => `<article><p>${h(row.effective_date)} · ${h(row.account_code)} · PHP ${h(row.signed_amount)} (debits less credits)</p><p>${h(row.source_type)} · ${h(row.source_id)}</p><p>${row.exact_posted ? 'Current exact posting proof' : 'Exact posting proof required'}</p></article>`).join('')}${value.offset > 0 ? '<button type="button" data-controls-previous>Previous source page</button>' : ''}${value.offset + value.movements.length < value.movement_count ? '<button type="button" data-controls-next>Next source page</button>' : ''}` : ''}</section>`;
    listen('[name="as_of"]', 'input', node => { asOf = node.value; offset = 0; value = null; generation++; root.querySelector('[data-controls-evidence]').innerHTML = ''; });
    listen('[data-controls-filter]', 'submit', () => { offset = 0; return load(); });
    listen('[data-controls-previous]', 'click', () => { offset = Math.max(0, offset - 100); return load(); });
    listen('[data-controls-next]', 'click', () => { offset += 100; return load(); });
  }
  async function load() {
    const g = ++generation; value = null; render('Loading private Collector controls…'); busy = true;
    try {
      check(sessionHasRole(getSession(), 'management') && hasPermission(getSession(), 'accounting.view') && (!asOf || day(asOf)));
      const result = await client.get('/book'); if (!current(g)) return;
      check(result.book?.status === 'configured' && id(result.book.book_id));
      if (bookId && bookId !== result.book.book_id) { denied(); return; } bookId = result.book.book_id;
      const query = new URLSearchParams({ limit: '100', offset: String(offset), ...(asOf ? { as_of: asOf } : {}) });
      const payload = await client.get(`/collector/control-schedule?${query}`); if (!current(g)) return;
      value = collectorControlSchedule(payload, bookId); check(value.offset === offset && value.limit === 100 && (!asOf || value.as_of === asOf)); asOf = value.as_of; render();
    } catch (error) { if (current(g)) { value = null; render(error.message); } }
    finally { if (current(g)) busy = false; }
  }
  mounts.set(root, dispose); signal?.addEventListener('abort', dispose, { once: true });
  if (signal?.aborted) { dispose(); return dispose; } await load(); return dispose;
}

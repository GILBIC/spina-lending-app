import {buildCollectionSubmission, classifyLoanType, normalizeMoney} from './collector-contract.js';
import {formatAuthoritativeMoney} from './client-schedule.js';

export async function collectorMutation({api,path,options,guard,verify}) {
  let result;
  try { result=await api.request(path,{...options,financial:true}); }
  catch(error) {
    if(error.code === 'network_uncertain' || error.status >= 500) guard.lock('SPINA could not confirm the saved result. Refresh the authoritative record before another attempt.');
    throw error;
  }
  let verified=false;
  try {verified=Boolean(result && typeof result === 'object' && !Array.isArray(result) && verify(result));} catch {verified=false;}
  if(!verified) {
    const error=new Error('SPINA could not verify the saved result. Refresh the authoritative record before another attempt.');
    error.code='financial_result_unverified';guard.lock(error.message);throw error;
  }
  return result;
}

export const collectionResultMatches = request => result =>
  ['accepted','duplicate'].includes(result.status) &&
  result.client_transaction_id === request.body.client_transaction_id &&
  typeof result.receipt_number === 'string' && result.receipt_number.length > 0;

export const EXTRA_CHOICES = {
  seven_by_seven_advance: '7x7 Advance',
  seven_by_seven_extra_principal: '7x7 Extra Principal',
  regular_advance: 'Regular Advance',
  regular_principal_reduction: 'Regular Principal Reduction',
};

export function combinedPairs(entries) {
  const clients = new Map();
  for (const entry of entries) {
    if (entry.can_enter_payment !== true || entry.processed_today === true) continue;
    const items = clients.get(entry.client_id) || [];
    items.push(entry);
    clients.set(entry.client_id, items);
  }
  return [...clients.values()].filter(items => items.length === 2 &&
    items.filter(entry => classifyLoanType(entry.loan_type) === 'regular').length === 1 &&
    items.filter(entry => classifyLoanType(entry.loan_type) === 'seven-by-seven').length === 1);
}

export function buildCombinedSubmission({entries, amount, extraChoice = '', pastDueFollowup = null, ...identity}) {
  if (combinedPairs(entries).length !== 1 || entries.length !== 2 || entries.some(entry => !String(entry.route_revision || '').trim()) || entries[0].client_id !== entries[1].client_id || entries[0].loan_id === entries[1].loan_id) {
    throw new TypeError('Combined Pay requires one available Regular and one 7x7 loan for the same client. Refresh the route.');
  }
  if (extraChoice && !Object.hasOwn(EXTRA_CHOICES, extraChoice)) throw new TypeError('Choose a supported extra allocation.');
  const request = buildCollectionSubmission({...identity, entry: entries[0], entryType:'payment', amount, pastDueFollowup});
  const second = buildCollectionSubmission({...identity, entry:entries[1], entryType:'payment', amount});
  return {headers:request.headers, loanTypes:Object.fromEntries(entries.map(entry => [entry.loan_id, classifyLoanType(entry.loan_type) === 'regular' ? 'regular' : 'seven_by_seven'])), body:{
    client_transaction_id:request.body.client_transaction_id,
    client_id:request.body.client_id,
    collection_date:request.body.collection_date,
    recorded_at:request.body.recorded_at,
    device_id:request.body.device_id,
    device_sequence:request.body.device_sequence,
    cash_received_amount:request.body.amount,
    ...(extraChoice ? {extra_allocation_choice:extraChoice} : {}),
    ...(pastDueFollowup ? {regular_past_due_followup:request.body.past_due_followup} : {}),
    legs:[request.body,second.body].map(item => ({route_entry_id:item.route_entry_id, loan_id:item.loan_id, route_revision:item.route_revision})),
  }};
}

function serverMoney(value) {
  if(typeof value !== 'string' || !/^(0|[1-9]\d*)\.\d{2}$/.test(value)) throw new Error('The server preview contains an invalid money value. Preview again.');
  return value;
}

export function formatServerMoney(value) {
  return formatAuthoritativeMoney(serverMoney(value));
}

function validateCombinedPreview(result,draft) {
  const invalid=()=>{throw new Error('The server preview does not match this payment. Preview again.');};
  if(!result || !['exact','short','excess','extra_choice_required'].includes(result.status) ||
    ['requires_review','extra_choice_required','regular_past_due_followup_required'].some(key=>typeof result[key] !== 'boolean') ||
    !/^[0-9a-f]{64}$/.test(result.allocation_hash || '') ||
    result.cash_received_amount !== draft.body.cash_received_amount ||
    result.requires_review !== (result.status !== 'exact') ||
    result.extra_choice_required !== (result.status === 'extra_choice_required') ||
    (result.extra_allocation_choice ?? null) !== (draft.body.extra_allocation_choice ?? null) ||
    JSON.stringify(result.allocation_order) !== JSON.stringify(['seven_by_seven','regular']) ||
    !Array.isArray(result.legs) || result.legs.length !== 2) invalid();
  for(const key of ['cash_received_amount','expected_total_amount','short_amount','extra_amount']) serverMoney(result[key]);
  const cents=value=>BigInt(serverMoney(value).replace('.',''));
  const seen=new Set();let allocated=0n;let collectible=0n;
  for(const leg of result.legs) {
    const expected=draft.body.legs.find(item=>item.loan_id===leg?.loan_id);
    if(!expected || seen.has(leg.loan_id) || leg.route_entry_id!==expected.route_entry_id || leg.route_revision!==expected.route_revision || leg.loan_type!==draft.loanTypes[leg.loan_id]) invalid();
    seen.add(leg.loan_id);
    for(const key of ['collectible_amount','scheduled_amount','extra_amount','total_amount']) serverMoney(leg[key]);
    if(!Array.isArray(leg.projected_covered_dates)) invalid();
    selectedDates(leg.projected_covered_dates);
    if(cents(leg.scheduled_amount)+cents(leg.extra_amount)!==cents(leg.total_amount)) invalid();
    allocated+=cents(leg.total_amount);collectible+=cents(leg.collectible_amount);
  }
  // Reconcile the response's own figures, without deciding the loan split.
  if(allocated+(result.extra_choice_required ? cents(result.extra_amount) : 0n)!==cents(result.cash_received_amount) || collectible!==cents(result.expected_total_amount)) invalid();
}

// A reviewed server split is bound to the exact submitted draft. Form edits,
// cancellation and workspace disposal invalidate even an in-flight preview.
export function createCombinedReview(api) {
  let generation = 0;
  let reviewed = null;
  return {
    invalidate() { generation += 1; reviewed = null; },
    async preview(draft) {
      const version = ++generation;
      reviewed = null;
      const snapshot = structuredClone(draft);
      const result = await api.request('/api/v1/collector/collections/combined/preview', {method:'POST', headers:snapshot.headers, body:snapshot.body});
      if (version !== generation) return null;
      validateCombinedPreview(result,snapshot);
      reviewed = {draft:snapshot, result:structuredClone(result)};
      return result;
    },
    submission() {
      if (!reviewed) throw new Error('Preview the current cash amount before saving.');
      if (reviewed.result.extra_choice_required) throw new Error('Choose the borrower’s extra allocation and preview again.');
      if (reviewed.result.regular_past_due_followup_required && !reviewed.draft.body.regular_past_due_followup) throw new Error('Choose a Regular Past Due reason and preview again.');
      return {headers:reviewed.draft.headers, body:{...reviewed.draft.body, reviewed_allocation_hash:reviewed.result.allocation_hash}};
    },
  };
}

export function selectedDates(values) {
  if (!Array.isArray(values) || values.some(value => !/^\d{4}-\d{2}-\d{2}$/.test(value)) || new Set(values).size !== values.length) {
    throw new TypeError('Choose valid, unique covered dates.');
  }
  return [...values].sort();
}

export function buildCorrection({entry, entryType, amount, coveredDates = [], reason = '', note = ''}) {
  if (!entry?.can_edit_today || entry.today_is_locked || !entry.today_transaction_id || !entry.route_revision) throw new Error('This collection cannot be corrected. Refresh the route.');
  if (!['payment','advance','pass'].includes(entryType)) throw new TypeError('Choose a valid collection type.');
  if (!reason.trim()) throw new TypeError('Enter a reason for the correction.');
  const dates = entryType === 'pass' ? [] : selectedDates(coveredDates);
  if (entryType !== 'pass' && !dates.length) throw new TypeError('Choose at least one covered date.');
  return {path:`/api/v1/collector/collections/${encodeURIComponent(entry.today_transaction_id)}`, body:{
    entry_type:entryType, amount:entryType === 'pass' ? null : normalizeMoney(amount), covered_dates:dates,
    reason:reason.trim(), note:note.trim(), expected_route_revision:entry.route_revision,
  }};
}

export function selectableScheduleDates(schedule) {
  return (schedule?.rows || []).filter(row => row.kind === 'installment' && /^\d{4}-\d{2}-\d{2}$/.test(row.date) && /^\d+(?:\.\d+)?$/.test(String(row.remaining_amount)) && /[1-9]/.test(String(row.remaining_amount)))
    .map(row => ({date:row.date,amount:row.remaining_amount}));
}

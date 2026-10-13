import {buildCollectionSubmission, classifyLoanType, normalizeMoney} from './collector-contract.js';
import {formatAuthoritativeMoney} from './client-schedule.js';

export async function collectorMutation({api,path,options,guard,verify}) {
  let result;
  guard.retainCommand({path,options});
  try { result=await api.request(path,{...options,financial:true}); }
  catch(error) {
    if(error.code === 'network_uncertain' || error.status >= 500) guard.lock('SPINA could not confirm the saved result. Refresh the authoritative record before another attempt.');
    if(!guard.locked) guard.clearCommand();
    throw error;
  }
  let verified=false;
  try {verified=Boolean(result && typeof result === 'object' && !Array.isArray(result) && verify(result));} catch {verified=false;}
  if(!verified) {
    const error=new Error('SPINA could not verify the saved result. Refresh the authoritative record before another attempt.');
    error.code='financial_result_unverified';guard.lock(error.message);throw error;
  }
  guard.clearCommand();
  return result;
}

const hasText = value => typeof value === 'string' && value.trim().length > 0;
const isServerMoney = value => typeof value === 'string' && /^(0|[1-9]\d*)\.\d{2}$/.test(value);

function hasAcceptedTime(value) {
  if(typeof value !== 'string') return false;
  const parts=/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(Z|[+-]\d{2}:\d{2})$/.exec(value);
  if(!parts || !Number.isFinite(Date.parse(value))) return false;
  const [year,month,day,hour,minute,second]=parts.slice(1,7).map(Number);
  const leap=year%4===0 && (year%100!==0 || year%400===0);
  const days=[31,leap?29:28,31,30,31,30,31,31,30,31,30,31];
  return month>=1 && month<=12 && day>=1 && day<=days[month-1] && hour<24 && minute<60 && second<60;
}

const finalStatusMatches = (result,commandId) => result &&
  ['accepted','duplicate'].includes(result.status) &&
  hasText(commandId) && result.client_transaction_id === commandId &&
  (!Object.hasOwn(result,'duplicate') || result.duplicate === (result.status === 'duplicate'));

export const collectionResultMatches = request => result =>
  finalStatusMatches(result,request.body.client_transaction_id) &&
  hasText(result.transaction_id) && isServerMoney(result.official_balance) &&
  hasAcceptedTime(result.accepted_at) &&
  (request.body.entry_type === 'pass' || hasText(result.receipt_number));

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
  if(!isServerMoney(value)) throw new Error('The server preview contains an invalid money value. Preview again.');
  return value;
}

export function formatServerMoney(value) {
  return formatAuthoritativeMoney(serverMoney(value));
}

function combinedResultMatches(request,preview) {
  // The server preview owns the allocation. Match its nonzero posted
  // components, including a separate 7x7 extra component for the same loan.
  const expected=new Map(),key=(loan,component)=>JSON.stringify([loan,component]);
  for(const leg of preview.legs) {
    if(leg.loan_type==='regular') {
      if(leg.total_amount!=='0.00') expected.set(key(leg.loan_id,leg.extra_amount==='0.00'?'regular_scheduled':'regular_scheduled_and_extra'),leg.total_amount);
    } else {
      if(leg.scheduled_amount!=='0.00') expected.set(key(leg.loan_id,'seven_by_seven_scheduled'),leg.scheduled_amount);
      if(leg.extra_amount!=='0.00') expected.set(key(leg.loan_id,preview.extra_allocation_choice),leg.extra_amount);
    }
  }
  return result => {
    if(!finalStatusMatches(result,request.body.client_transaction_id) ||
      result.client_id!==request.body.client_id || result.allocation_hash!==request.body.reviewed_allocation_hash ||
      result.allocation_status!==preview.status || (result.extra_allocation_choice ?? null)!==(preview.extra_allocation_choice ?? null) ||
      !isServerMoney(result.total_amount) || result.total_amount!==request.body.cash_received_amount ||
      result.applied_total_amount!==result.total_amount || result.unallocated_total_amount!=='0.00' ||
      result.cash_allocation_state!=='fully_allocated' || !Array.isArray(result.legs) || result.legs.length!==expected.size) return false;
    const seen=new Set(),transactions=new Set(),receipts=new Set();let total=0n;
    for(const leg of result.legs) {
      if(!leg || typeof leg!=='object') return false;
      const component=key(leg.loan_id,leg.allocation_component),amount=expected.get(component);
      if(!amount || seen.has(component) || !isServerMoney(leg.amount) || leg.amount!==amount ||
        leg.applied_amount!==amount || leg.unallocated_amount!=='0.00' || leg.allocation_state!=='fully_allocated' ||
        !isServerMoney(leg.official_balance) || !hasText(leg.route_revision) ||
        !hasText(leg.transaction_id) || transactions.has(leg.transaction_id) ||
        !hasText(leg.receipt_number) || receipts.has(leg.receipt_number)) return false;
      seen.add(component);transactions.add(leg.transaction_id);receipts.add(leg.receipt_number);
      total+=BigInt(leg.amount.replace('.',''));
    }
    return total===BigInt(result.total_amount.replace('.',''));
  };
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
    resultMatches() {
      const request=this.submission();
      return combinedResultMatches(structuredClone(request),structuredClone(reviewed.result));
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

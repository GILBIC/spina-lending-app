const id = value => typeof value === 'string' && /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(value);
const money = value => typeof value === 'string' && /^(0|[1-9][0-9]{0,15})\.[0-9]{2}$/.test(value);
const cents = value => BigInt(value.replace('.', ''));
const check = value => { if (!value) throw Error('The approved Collector credit does not match this count. Review its current approval.'); };
const canonical = value => JSON.stringify(Object.fromEntries(Object.entries(value ?? {}).sort(([a],[b])=>a.localeCompare(b))));

export function custodySplitText(value, expectedGross = value?.gross_obligation) {
  const keys = ['gross_obligation', 'authorized_credit_amount', 'physical_cash_required', 'physical_amount', 'excess_amount'];
  check(value && keys.every(key => money(value[key])) && cents(value.authorized_credit_amount) > 0n && cents(value.gross_obligation) === cents(value.authorized_credit_amount) + cents(value.physical_cash_required) && cents(value.physical_amount) === cents(value.physical_cash_required) + cents(value.excess_amount));
  check(value.gross_obligation === expectedGross);
  return `Actual cash received: PHP ${value.physical_amount} · Credit applied: PHP ${value.authorized_credit_amount} · Cash excess: PHP ${value.excess_amount}`;
}

export function applicationCoordinates(value) {
  const selected = value?.credit_application_id ?? value?.credit_application?.id ?? null;
  const version = value?.credit_application_version ?? value?.credit_application?.version ?? null;
  check((selected === null) === (version === null));
  if (selected !== null) check(id(selected) && Number.isSafeInteger(version) && version > 0);
  return {credit_application_id:selected, credit_application_version:version};
}

export function validateApplicationPreview(value, approval = null) {
  if (!approval) { check(value.authorized_credit_application === '0.00' && !value.credit_application); return value; }
  const actual = value.credit_application;
  check(actual && actual.id === approval.id && actual.version === approval.version && actual.kind === 'application' && actual.status === 'reserved' && actual.event_id === null && actual.remittance_id === value.remittance_id && actual.account_id === value.account_id && actual.collector_user_id === value.collector_user_id && actual.recipient_user_id === value.recipient_user_id);
  check(money(actual.amount) && cents(actual.amount) > 0n && actual.amount === value.authorized_credit_application && value.refund_due_total === '0.00' && money(value.gross_obligation) && money(value.physical_cash_required) && cents(value.gross_obligation) === cents(value.physical_cash_required) + cents(actual.amount));
  check(actual.source_digest === value.remittance_source_digest && /^[a-f0-9]{64}$/.test(value.remittance_source_digest));
  return value;
}

export function validateApplicationResult(result, held) {
  const body = held.options.body, value = result.result;
  if (result.status === 'blocked') return;
  if (body.action === 'collector_surplus_application_prepare') {
    const row = value.action_record;
    check(row?.kind === 'application' && row.status === 'reserved' && row.event_id === null && row.event_version === null && row.acknowledgment_id === null && row.remittance_id === body.remittance_id && row.source_digest === body.source_digest && row.amount === body.amount && row.collector_request_id === body.collector_request_id && row.recipient_user_id === held.actor.user_id && row.origin_account_id === held.reference.account_id);
  }
  if (!['collector_count_record','collector_count_accept'].includes(body.action)) return;
  const reference = held.reference;
  const expected = applicationCoordinates(reference), submitted = applicationCoordinates(body);
  check(canonical(expected) === canonical(submitted));
  if (body.action === 'collector_count_record') {
    const count = value.count;
    check(canonical(applicationCoordinates(count)) === canonical(expected));
    if (expected.credit_application_id) {
      check(canonical(count.credit_application) === canonical(reference.credit_application) && count.authorized_credit_application === reference.authorized_credit_application && count.remittance_source_digest === reference.remittance_source_digest);
    }
  } else if (expected.credit_application_id) {
    const action = value.action_record, entry = value.application_entry, approval = reference.credit_application;
    check(canonical(value.count?.credit_application) === canonical(approval) && canonical(applicationCoordinates(value.count)) === canonical(expected));
    check(action?.id === approval.id && action.version === approval.version + 1 && action.status === 'applied' && action.kind === 'application' && action.event_id === null && action.amount === approval.amount);
    check(entry?.kind === 'application' && id(entry.id) && entry.action_id === action.id && entry.credit_id === action.credit_id && entry.amount === action.amount && entry.settlement_id === value.settlement.id && entry.accepted_at === value.settlement.accepted_at);
    check(value.credit?.id === action.credit_id && value.settlement.authorized_credit_amount === approval.amount && value.source_account_id === approval.origin_account_id);
  } else check(!value.application_entry);
}

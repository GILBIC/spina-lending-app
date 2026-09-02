const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const MONEY_PATTERN = /^\d+(?:\.\d{1,2})?$/;
const PAST_DUE_REASONS = new Set([
  'no_cash',
  'client_absent',
  'business_slow',
  'sick_hospital',
  'emergency',
  'promised_to_pay_later',
  'other',
]);

function requiredText(value, label) {
  const normalized = String(value ?? '').trim();
  if (!normalized) {
    throw new TypeError(`${label} is required.`);
  }
  return normalized;
}

function normalizeMoney(value, label = 'Payment amount') {
  const normalized = String(value ?? '').trim().replace(/,/g, '');
  if (!MONEY_PATTERN.test(normalized)) {
    throw new TypeError(`${label} must be a valid peso amount.`);
  }
  const amount = Number(normalized);
  if (!Number.isFinite(amount) || amount <= 0) {
    throw new TypeError(`${label} must be greater than zero.`);
  }
  return amount.toFixed(2);
}

function normalizeRecordedAt(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    throw new TypeError('Recorded time must be a valid timestamp.');
  }
  return date.toISOString();
}

function normalizePastDueFollowup(value, collectionDate) {
  if (value == null || typeof value !== 'object') {
    throw new TypeError('Choose a Past Due reason before saving Unable to pay.');
  }
  const reasonCode = String(value.reason_code ?? '').trim().toLowerCase();
  if (!PAST_DUE_REASONS.has(reasonCode)) {
    throw new TypeError('Choose a valid Past Due reason.');
  }
  const note = String(value.note ?? '').trim();
  let promisedPaymentDate = value.promised_payment_date ?? null;
  let promisedAmount = value.promised_amount ?? null;

  if (reasonCode === 'other' && note.length < 3) {
    throw new TypeError('Other Past Due reason requires a short explanation.');
  }
  if (reasonCode === 'promised_to_pay_later') {
    promisedPaymentDate = requiredText(promisedPaymentDate, 'Promised payment date');
    if (!DATE_PATTERN.test(promisedPaymentDate) || promisedPaymentDate < collectionDate) {
      throw new TypeError('Promised payment date cannot be before the collection date.');
    }
    promisedAmount = normalizeMoney(promisedAmount, 'Promised amount');
  } else if (promisedPaymentDate != null || promisedAmount != null) {
    throw new TypeError('Promise date and amount are only valid for Promised to pay later.');
  }

  return {
    reason_code: reasonCode,
    note,
    promised_payment_date: promisedPaymentDate,
    promised_amount: promisedAmount,
  };
}

export function classifyLoanType(value) {
  const normalized = String(value ?? '').trim().toLowerCase().replace(/\s+/g, '');
  if (normalized.includes('7x7') || normalized.includes('7×7')) {
    return 'seven-by-seven';
  }
  if (normalized.includes('regular')) {
    return 'regular';
  }
  return 'other';
}

export function buildCollectionSubmission({
  entry,
  routeDate,
  entryType,
  amount,
  note = '',
  pastDueFollowup = null,
  deviceId,
  deviceSequence,
  clientTransactionId,
  recordedAt = new Date().toISOString(),
}) {
  if (entry == null || typeof entry !== 'object') {
    throw new TypeError('A route entry is required.');
  }
  const transactionId = requiredText(clientTransactionId, 'Client transaction UUID');
  if (!UUID_PATTERN.test(transactionId)) {
    throw new TypeError('Client transaction ID must be a valid UUID.');
  }
  const collectionDate = requiredText(routeDate, 'Collection date');
  if (!DATE_PATTERN.test(collectionDate)) {
    throw new TypeError('Collection date must use YYYY-MM-DD.');
  }
  const installationId = requiredText(deviceId, 'Device ID');
  if (!Number.isSafeInteger(deviceSequence) || deviceSequence < 1) {
    throw new TypeError('Device sequence must be a positive integer.');
  }
  const normalizedType = String(entryType ?? '').trim().toLowerCase();
  if (!['payment', 'pass'].includes(normalizedType)) {
    throw new TypeError('The MVP supports Payment and Unable to pay entries only.');
  }

  let normalizedAmount = null;
  let normalizedFollowup = null;
  if (normalizedType === 'payment') {
    normalizedAmount = normalizeMoney(amount);
    if (pastDueFollowup != null) {
      normalizedFollowup = normalizePastDueFollowup(pastDueFollowup, collectionDate);
    }
  } else {
    normalizedFollowup = normalizePastDueFollowup(pastDueFollowup, collectionDate);
  }

  const body = {
    client_transaction_id: transactionId,
    route_entry_id: requiredText(entry.route_entry_id, 'Route entry ID'),
    client_id: requiredText(entry.client_id, 'Client ID'),
    loan_id: requiredText(entry.loan_id, 'Loan ID'),
    collection_date: collectionDate,
    entry_type: normalizedType,
    amount: normalizedAmount,
    advance_from: null,
    advance_until: null,
    covered_dates: [],
    recorded_at: normalizeRecordedAt(recordedAt),
    device_id: installationId,
    device_sequence: deviceSequence,
    note: String(note ?? '').trim(),
    route_revision: String(entry.route_revision ?? '').trim() || null,
    payment_allocation_intent: 'scheduled',
    past_due_followup: normalizedFollowup,
  };

  return {
    headers: {
      'Idempotency-Key': transactionId,
      'X-Client-Transaction-Id': transactionId,
      'X-Device-Id': installationId,
      'X-Gilbic-Contract-Version': '1',
    },
    body,
  };
}

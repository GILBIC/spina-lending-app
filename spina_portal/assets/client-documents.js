import { asArray, emptyState, errorCard, escapeHtml, formatDateTime } from './ui.js';

const mounts = new WeakMap();
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const DOCUMENT_LABELS = {finalized_loan_packet:'Original released loan packet',signed_loan_contract:'Signed loan contract',cash_release_acknowledgment:'Signed cash release acknowledgment'};
const EXTENSIONS = {'application/pdf':'pdf','image/png':'png','image/jpeg':'jpg'};

export function savePrivateFile(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function requirePrivateFile(blob, expectedMediaType) {
  if (!(blob instanceof Blob) || blob.size === 0 || !EXTENSIONS[expectedMediaType]
    || blob.type.split(';', 1)[0].toLowerCase() !== expectedMediaType) {
    throw new Error('SPINA did not return a valid document file. Refresh and try again.');
  }
  return blob;
}

export function mountClientDocuments({root, api, loans = [], payments = [], signal, saveFile = savePrivateFile}) {
  mounts.get(root)?.();
  const controller = new AbortController(); let disposed = false; const removers = [];
  const listen = (element, event, fn) => {
    element.addEventListener(event, fn); removers.push(() => element.removeEventListener(event, fn));
  };
  function dispose() {
    if (disposed) return; disposed = true; controller.abort();
    for (const remove of removers) remove(); root.innerHTML = '';
    signal?.removeEventListener('abort', dispose);
    if (mounts.get(root) === dispose) mounts.delete(root);
  }
  function fail(error) {
    if (disposed) return;
    if ([401, 403].includes(error?.status)) { dispose(); root.innerHTML = errorCard(error); }
    else root.querySelector('[data-document-status]').innerHTML = errorCard(error);
  }
  async function download(button, path, filename, mediaType = 'application/pdf') {
    if (disposed || button.disabled) return;
    button.disabled = true;
    try {
      const blob = await api.request(path, {responseType: 'blob', signal: controller.signal});
      if (!disposed) { saveFile(requirePrivateFile(blob, mediaType), filename); root.querySelector('[data-document-status]').textContent = 'Download prepared.'; }
    } catch (error) { fail(error); }
    finally { if (!disposed) button.disabled = false; }
  }
  mounts.set(root, dispose); signal?.addEventListener('abort', dispose, {once: true});
  if (signal?.aborted) { dispose(); return dispose; }
  root.innerHTML = `<p>Download your original released loan packet, or current statement and payment record copies. A record copy reflects corrections and voids recorded when it is downloaded.</p>
    <button type="button" class="button button-secondary" data-statement-copy>Download statement copy (PDF)</button>
    <h3>Released loan documents</h3>
    ${loans.length ? loans.map((loan) => `<article class="list-item"><strong>${escapeHtml(loan.loan_number || 'Loan')}</strong>
      <button type="button" class="button button-secondary" data-load-documents="${escapeHtml(loan.loan_id)}">Find issued documents</button>
      <div data-loan-documents="${escapeHtml(loan.loan_id)}"></div></article>`).join('') : emptyState('No linked loan is available.')}
    <h3>Payment record copies</h3>
    ${payments.length ? payments.map((payment) => `<article class="list-item"><span>${escapeHtml(payment.receipt_number || 'Payment record')}${payment.is_voided ? ' · Voided' : ''}</span>
      <button type="button" class="button button-secondary" data-payment-copy="${escapeHtml(payment.transaction_id)}">Download record copy (PDF)</button></article>`).join('') : emptyState('No official payment is recorded yet.')}
    <div data-document-status role="status" aria-live="polite"></div>`;
  const statement = root.querySelector('[data-statement-copy]');
  listen(statement, 'click', () => download(statement, '/api/v1/client/statement/document', 'statement-of-account-record-copy.pdf'));
  for (const button of root.querySelectorAll('[data-payment-copy]')) {
    const id = button.getAttribute('data-payment-copy');
    if (!UUID.test(id)) { button.disabled = true; continue; }
    listen(button, 'click', () => download(button, `/api/v1/client/payments/${encodeURIComponent(id)}/document`, `payment-record-${id}.pdf`));
  }
  for (const button of root.querySelectorAll('[data-load-documents]')) {
    const loanId = button.getAttribute('data-load-documents');
    if (!UUID.test(loanId)) { button.disabled = true; continue; }
    listen(button, 'click', async () => {
      if (disposed || button.disabled) return; button.disabled = true;
      const base = `/api/v1/client/loans/${encodeURIComponent(loanId)}/documents`;
      try {
        const result = await api.request(base, {signal: controller.signal}); if (disposed) return;
        const documents = asArray(result.documents);
        const panel = root.querySelector(`[data-loan-documents="${loanId}"]`);
        panel.innerHTML = documents.length ? documents.map((record) => `<p>${escapeHtml(DOCUMENT_LABELS[record.kind] || 'Issued document')}${record.released_at ? ` · ${formatDateTime(record.released_at)}` : ''}
          <button type="button" class="button button-secondary" data-download-packet="${escapeHtml(record.document_id)}">Download original file</button></p>`).join('') : emptyState('No finalized issued document is available for this loan. Contact SPINA for a copy.');
        for (const packet of panel.querySelectorAll('[data-download-packet]')) {
          const documentId = packet.getAttribute('data-download-packet');
          const record = documents.find((item) => item.document_id === documentId);
          const extension = EXTENSIONS[record?.media_type || 'application/pdf'];
          if (!UUID.test(documentId) || !extension) { packet.disabled = true; continue; }
          listen(packet, 'click', () => download(packet, `${base}/${encodeURIComponent(documentId)}`, `loan-document-${documentId}.${extension}`, record.media_type || 'application/pdf'));
        }
      } catch (error) { fail(error); }
      finally { if (!disposed) button.disabled = false; }
    });
  }
  return dispose;
}

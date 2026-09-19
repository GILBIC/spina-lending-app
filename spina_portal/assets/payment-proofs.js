import { asArray, badge, emptyState, errorCard, escapeHtml, formatDateTime, loadingPanel, titleCase } from './ui.js';
import { requirePrivateFile, savePrivateFile } from './client-documents.js';

const mounts = new WeakMap();
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const TYPES = ['application/pdf', 'image/png', 'image/jpeg'];

function completeDetail(value) {
  const proof = value?.proof;
  return UUID.test(proof?.proof_id) && UUID.test(proof?.loan_id)
    && Number.isSafeInteger(proof?.current_version?.version_number) && proof.current_version.version_number > 0
    && Array.isArray(value?.history) && value.history.some((entry) => entry?.version?.version_number === proof.current_version.version_number);
}

export function mountPaymentProofs({root, api, loans = [], mode = 'client', signal, saveFile = savePrivateFile}) {
  mounts.get(root)?.();
  const management = mode === 'management';
  const base = `/api/v1/${management ? 'management' : 'client'}/payment-proofs`;
  const controller = new AbortController(); let disposed = false; let busy = false;
  let listing = {}; let detail = null; let offset = 0; let attempt = null; let uncertain = false; let removers = [];
  const listen = (element, event, fn) => { if (!element) return;
    element.addEventListener(event, fn); removers.push(() => element.removeEventListener(event, fn));
  };
  function clear() { for (const remove of removers) remove(); removers = []; root.innerHTML = ''; }
  function dispose() {
    if (disposed) return; disposed = true; controller.abort(); attempt = null; detail = null; listing = {}; clear();
    signal?.removeEventListener('abort', dispose); if (mounts.get(root) === dispose) mounts.delete(root);
  }
  function status(message) { const element = root.querySelector('[data-proof-status]'); if (element) element.textContent = message; }
  function fail(error) {
    if (disposed) return;
    if ([401,403].includes(error?.status)) {dispose();root.innerHTML = errorCard(error);return;}
    const element = root.querySelector('[data-proof-status]'); if (element) element.innerHTML = errorCard(error);
    else root.innerHTML = errorCard(error);
  }
  function lockInputs() {
    for (const input of [...root.querySelectorAll('input'),...root.querySelectorAll('textarea'),...root.querySelectorAll('select')]) input.disabled = busy || uncertain;
    for (const button of root.querySelectorAll('button')) button.disabled = busy || (uncertain && button.getAttribute('type') !== 'submit');
  }
  async function load(nextOffset = offset) {
    if (disposed || busy || uncertain) return; busy = true;
    try {
      const value = await api.request(`${base}?limit=50&offset=${nextOffset}`,{signal:controller.signal});
      if (disposed) return; offset = nextOffset; listing = value; detail = null; attempt = null; render();
    } catch(error) {fail(error);} finally {busy = false;if(!disposed) lockInputs();}
  }
  async function open(id) {
    if(disposed || busy || uncertain || !UUID.test(id)) return; busy = true;lockInputs();
    try {const value=await api.request(`${base}/${id}`,{signal:controller.signal});if(!disposed){detail=value;attempt=null;render();}}
    catch(error){fail(error);}finally{busy=false;if(!disposed)lockInputs();}
  }
  async function content(number, mediaType) {
    if(disposed || busy || !detail?.proof || !Number.isSafeInteger(number) || number < 1) return;
    const id=detail.proof.proof_id;if(!UUID.test(id))return;busy=true;lockInputs();
    try {const blob=await api.request(`${base}/${id}/versions/${number}/content`,{responseType:'blob',signal:controller.signal});
      if(!disposed)saveFile(requirePrivateFile(blob,mediaType),`payment-proof-${id}-v${number}.${mediaType==='application/pdf'?'pdf':mediaType==='image/png'?'png':'jpg'}`);
    }catch(error){fail(error);}finally{busy=false;if(!disposed)lockInputs();}
  }
  async function submit(event) {
    event.preventDefault();if(disposed||busy)return;
    if(!uncertain){
      if(management){
        const decision=root.querySelector('[name="decision"]').value;
        const reason=root.querySelector('[name="reason"]').value.trim();
        if(!['reviewed','correction_required','rejected'].includes(decision)|| (decision!=='reviewed'&&!reason)){fail(new Error('Choose a review decision and explain any correction or rejection.'));return;}
        attempt={path:`${base}/${detail.proof.proof_id}/reviews`,options:{method:'POST',body:{request_id:crypto.randomUUID(),
          expected_version:detail.proof.current_version.version_number,expected_review_id:detail.proof.latest_review?.review_id??null,decision,reason}}};
      }else{
        const file=root.querySelector('[name="proofFile"]').files?.[0];const capability=listing.capability;
        if(!capability?.upload_available||!file||!TYPES.includes(file.type)||file.size<1||file.size>Math.min(capability.max_bytes||0,10485760)){
          fail(new Error('Choose a PDF, PNG or JPEG proof of at most 10 MiB.'));return;
        }
        const note=root.querySelector('[name="note"]').value.trim();
        const query=new URLSearchParams({request_id:crypto.randomUUID()});
        let path=base;
        if(detail?.proof){path+=`/${detail.proof.proof_id}/versions`;query.set('expected_version',detail.proof.current_version.version_number);}
        else {const loanId=root.querySelector('[name="loanId"]').value;if(!UUID.test(loanId)){fail(new Error('Select your loan.'));return;}query.set('loan_id',loanId);}
        const encodedNote=btoa(String.fromCharCode(...new TextEncoder().encode(note)));
        attempt={path:`${path}?${query}`,options:{method:'POST',rawBody:file,headers:{'Content-Type':file.type,'X-Proof-Note':encodedNote}}};
      }
    }
    if(!attempt)return;busy=true;lockInputs();status('Saving evidence…');
    try {
      const value=await api.request(attempt.path,{...attempt.options,signal:controller.signal});if(disposed)return;
      const expectedLoan = detail?.proof?.loan_id || new URL(attempt.path, 'https://spina.invalid').searchParams.get('loan_id');
      if (!completeDetail(value) || (detail?.proof && value.proof.proof_id !== detail.proof.proof_id)
        || (expectedLoan && value.proof.loan_id !== expectedLoan)) {
        throw Object.assign(new Error('The evidence response could not be confirmed.'), {code:'network_uncertain'});
      }
      detail=value;attempt=null;uncertain=false;render();status(management?'Evidence review saved. No payment was posted.':'Evidence saved for review. This does not change your balance.');
    }catch(error){
      if(disposed)return;
      uncertain=error?.code==='network_uncertain'||error?.status===0||error?.status>=500;
      fail(error);
      if(uncertain)status('The result is uncertain. Retry the same submission to confirm it safely.');
      else if(error?.status===409){attempt=null;detail=null;render();status('The evidence changed. Open it again to review the latest version before resubmitting.');}
    }finally{busy=false;if(!disposed)lockInputs();}
  }
  function render() {
    clear();const records=asArray(listing.proofs);const proof=detail?.proof;const canUpload=listing.capability?.upload_available===true;
    root.innerHTML=`<p>${management?'Reviewing evidence does not confirm settlement, post a payment, or change a borrower balance.':'Uploading proof does not change your balance. Only an official SPINA payment does.'}</p>
      <button type="button" class="button button-secondary" data-proof-refresh>Refresh</button>
      ${records.length?records.map((record)=>`<article class="list-item"><strong>${escapeHtml(record.loan_number||'Loan')}</strong>
        ${management?`<span>${escapeHtml(record.client_name||'')} ${escapeHtml(record.client_code||'')}</span>`:''}${badge(record.status)}
        <button type="button" class="button button-secondary" data-proof-detail="${escapeHtml(record.proof_id)}">Open evidence and history</button></article>`).join(''):emptyState('No payment-proof submissions on this page.')}
      <div class="inline-actions">${offset>0?'<button type="button" data-proof-previous>Previous</button>':''}${listing.has_more?'<button type="button" data-proof-next>Next</button>':''}</div>
      ${proof?`<article class="notice-card"><h3>${escapeHtml(proof.loan_number||'Payment proof')}</h3>${badge(proof.status)}
        ${proof.latest_review?.reason?`<p>Review note: ${escapeHtml(proof.latest_review.reason)}</p>`:''}
        ${asArray(detail.history).map((entry)=>`<div class="list-item"><strong>Version ${escapeHtml(entry.version.version_number)}</strong>
          <span>${formatDateTime(entry.version.uploaded_at)}</span><p>${escapeHtml(entry.version.note||'')}</p>
          <button type="button" class="button button-secondary" data-proof-content="${escapeHtml(entry.version.version_number)}">Download submitted file</button>
          ${asArray(entry.reviews).map((review)=>`<p>${escapeHtml(titleCase(review.decision))} · ${formatDateTime(review.reviewed_at)}${review.reason?` · ${escapeHtml(review.reason)}`:''}</p>`).join('')}</div>`).join('')}</article>`:''}
      ${management&&proof?`<form data-proof-review class="entry-form"><h3>Review current evidence</h3>
        <label>Decision<select name="decision"><option value="reviewed">Evidence reviewed (no payment posted)</option><option value="correction_required">Request correction</option><option value="rejected">Reject evidence</option></select></label>
        <label>Reason<textarea name="reason" maxlength="1000"></textarea></label><button type="submit" class="button button-primary">Save evidence review</button></form>`:''}
      ${!management&&canUpload&&(!proof||proof.can_reupload)?`<form data-proof-upload class="entry-form"><h3>${proof?'Upload a corrected version':'Submit payment proof'}</h3>
        ${!proof?`<label>Loan<select name="loanId" required>${loans.map((loan)=>`<option value="${escapeHtml(loan.loan_id)}">${escapeHtml(loan.loan_number||'Loan')}</option>`).join('')}</select></label>`:''}
        <label>Proof file<input type="file" name="proofFile" accept="application/pdf,image/png,image/jpeg" required /></label>
        <label>Note or payment reference<textarea name="note" maxlength="1000"></textarea></label>
        <button type="submit" class="button button-primary">${proof?'Save corrected evidence':'Submit evidence for review'}</button></form>`:''}
      ${!management&&!canUpload?emptyState(listing.capability?.message||'Proof upload is currently unavailable.') : ''}
      ${!management&&proof?'<button type="button" class="button button-secondary" data-proof-new>Start a new submission</button>':''}
      <div data-proof-status role="status" aria-live="polite"></div>`;
    listen(root.querySelector('[data-proof-refresh]'),'click',()=>load());
    listen(root.querySelector('[data-proof-previous]'),'click',()=>load(Math.max(0,offset-50)));
    listen(root.querySelector('[data-proof-next]'),'click',()=>load(offset+50));
    listen(root.querySelector('[data-proof-new]'),'click',()=>{if(busy||uncertain)return;detail=null;attempt=null;render();});
    for(const button of root.querySelectorAll('[data-proof-detail]'))listen(button,'click',()=>open(button.getAttribute('data-proof-detail')));
    for(const button of root.querySelectorAll('[data-proof-content]'))listen(button,'click',()=>{const number=Number(button.getAttribute('data-proof-content'));
      content(number,asArray(detail.history).find((entry)=>entry.version.version_number===number)?.version.media_type);});
    listen(root.querySelector('[data-proof-upload]'),'submit',submit);listen(root.querySelector('[data-proof-review]'),'submit',submit);
  }
  mounts.set(root,dispose);signal?.addEventListener('abort',dispose,{once:true});
  if(signal?.aborted){dispose();return dispose;}
  root.innerHTML=loadingPanel('Loading payment-proof records…');void load();return dispose;
}

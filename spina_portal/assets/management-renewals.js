import {
  escapeHtml as h, formatExactMoney, formatDateTime, hasPermission
} from './ui.js';
const statuses = ['pending', 'approved', 'rejected'];
const parties = ['borrower', 'guarantor', 'solidary_co_maker', 'surety'];
const reviewStates = ['under_review', 'correction_required', 'flagged'];
const proofDecisions = {
  approved: 'approved', request_new_photo: 'correction_required', flag_for_review: 'flagged'
};
const validId = value => typeof value === 'string' && /^[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$/i.test(value);
const normalize = value => String(value ?? '').trim().replace(/\s+/g, ' ');
export function renewalMoney(value, { positive = false } = {}) {
  if (typeof value !== 'string') return null;
  const match = value.trim().match(/^(\d{1,16})(?:\.(\d{1,2}))?$/);
  if (!match) return null;
  const whole = match[1].replace(/^0+(?=\d)/, '');
  const result = whole + '.' + (match[2] || '').padEnd(2, '0');
  return positive && /^0\.00$/.test(result) ? null : result;
}
const money = value => renewalMoney(value) === null ? 'Unavailable' : formatExactMoney(value);
const identity = row => row && validId(row.request_id) && validId(row.client_id) && validId(row.loan_id);
const sameIdentity = (a, b) => identity(a) && identity(b) && ['request_id', 'client_id', 'loan_id'].every(key => a[key] === b[key]);
const fingerprint = row => JSON.stringify(row);
// Complete authorized payload: no mixed snapshots.
const lockedMoney = row => !!row.amount_locked_at && renewalMoney(row.renewal_offset_amount) !== null && renewalMoney(row.net_release_amount) !== null && validId(row.new_loan_id);
const sameLockedMoney = (before, after) => lockedMoney(before) && lockedMoney(after) && before.new_loan_id === after.new_loan_id && before.amount_locked_at === after.amount_locked_at && ['renewal_offset_amount', 'net_release_amount'].every(key => renewalMoney(before[key]) === renewalMoney(after[key]));
const samePrincipal = (before, after) => renewalMoney(before.approved_principal, { positive: true }) !== null && renewalMoney(before.approved_principal) === renewalMoney(after.approved_principal);
export function renewalResultMatches(command, result) {
  const row = result?.request;
  if (!sameIdentity(command.request, row)) return false;
  const body = command.body;
  if (command.action === 'terms') {
    if (row.client_decision !== command.request.client_decision || row.activation_status !== command.request.activation_status || !row.reviewed_at || row.status !== body.decision || normalize(row.review_note) !== body.review_note) return false;
    if (body.decision === 'rejected') return true;
    if (renewalMoney(row.approved_principal) !== body.approved_principal || normalize(row.management_override_reason) !== body.override_reason || row.office_processing_required !== (body.office_processing_required || body.signers.some(s => !s.user_id))) return false;
    const office = body.office_processing_required || body.signers.some(s => !s.user_id);
    if (row.signer_readiness_status !== (office ? 'office_required' : 'pending') || !Array.isArray(row.signers) || row.signers.length !== body.signers.length || row.signers.some(s => !validId(s.signer_id) || s.signed !== false || s.ready !== false)) return false;
    const remaining = [...row.signers];
    return body.signers.every(s => {
      const index = remaining.findIndex(r => r.party_role === s.party_role && normalize(r.full_name) === s.full_name && r.user_id === s.user_id && r.government_id_verified === s.government_id_verified && r.selfie_verified === s.selfie_verified);
      if (index < 0) return false;
      remaining.splice(index, 1);
      return true;
    });
  }
  if (row.status !== 'approved' || row.client_decision !== command.request.client_decision || !samePrincipal(command.request, row)) return false;
  if (command.action === 'release-to-collector') return lockedMoney(row) && !!row.cash_released_to_collector_at && row.activation_status === 'released_pending_management' && row.assigned_collector_user_id === command.request.assigned_collector_user_id;
  if (!sameLockedMoney(command.request, row)) return false;
  if (command.action === 'proof-review') return row.handover_proof_status === proofDecisions[body.decision] && (row.activation_status === command.request.activation_status || (body.decision === 'approved' && row.activation_status === 'active')) && typeof row.ready_for_activation === 'boolean';
  return command.action === 'activate' && row.activation_status === 'active' && row.handover_proof_status === 'approved' && !!row.client_cash_confirmed_at;
}
export function renewalActionBlocker(row, action) {
  if (!identity(row)) return 'Request identity is unavailable.';
  if (action === 'terms') return row.status !== 'pending' ? 'This request is no longer pending.' : !['recommend','do_not_recommend'].includes(row.collector_recommendation) ? 'Wait for the assigned Collector recommendation.' : '';
  if (row.status !== 'approved') return 'Approved terms are required.';
  if (!renewalMoney(row.approved_principal, { positive: true })) return 'Approved principal is unavailable.';
  if (action === 'proof-review') return !lockedMoney(row) || !row.cash_given_to_client_at || !reviewStates.includes(row.handover_proof_status) ? 'A submitted handover photo and authoritative locked execution evidence are required before review.' : '';
  if (row.client_decision !== 'accepted') return 'The borrower must independently Accept & Continue first.';
  if (row.office_processing_required !== false || row.signer_readiness_status !== 'ready') return 'Office processing or verified signer completion is required; this screen cannot bypass it.';
  if (action === 'release-to-collector') return row.amount_locked_at || row.cash_released_to_collector_at ? 'Cash release is already recorded; no second release.' : !validId(row.assigned_collector_user_id) ? 'Assigned Collector identity is unavailable.' : '';
  if (!lockedMoney(row)) return 'Authoritative locked cash amounts and execution-linked loan are unavailable.';
  if (action === 'activate') return row.activation_status === 'active' ? 'Renewal is already active.' : row.ready_for_activation !== true || row.handover_proof_status !== 'approved' || !row.client_cash_confirmed_at ? 'Activation is not ready. Borrower cash confirmation, settlement, signer and CIF checks remain independent.' : '';
  return 'This action is unavailable.';
}
function signerMarkup(index, role = 'guarantor') {
  return '<fieldset data-signer><legend>Required signer ' + (index + 1) + '</legend><label>Party<select name="party_role">' + parties.map(p => '<option value="' + p + '"' + (p === role ? ' selected' : '') + '>' + h(p.replaceAll('_',' ')) + '</option>').join('') + '</select></label><label>Full name<input name="full_name" maxlength="200" /></label><label>Verified account UUID<input name="user_id" maxlength="36" autocomplete="off" /></label><label><input type="checkbox" name="identity_reviewed" />I checked this named person and exact account against authorized identity evidence.</label><label><input type="checkbox" name="government_id_verified" />Government ID evidence verified</label><label><input type="checkbox" name="selfie_verified" />Selfie evidence verified</label><button type="button" class="button button-outline" data-remove-signer>Remove this signer</button></fieldset>';
}
function recordMarkup(row) {
  const detail = (label, value) => '<div class="detail-item"><span>' + h(label) + '</span><strong>' + h(value ?? 'Unavailable') + '</strong></div>';
  const timestamp = value => value ? formatDateTime(value) : 'Not recorded';
  let markup = '<h3>' + h(row.client_name || 'Borrower') + ' | ' + h(row.loan_number || 'Loan') + '</h3><p>' + h(row.client_code || '') + ' | ' + h(row.area || '') + '</p><p class="meta">Request ' + h(row.request_id) + ' | Client ' + h(row.client_id) + ' | Loan ' + h(row.loan_id) + '</p><div class="loan-meta">' + detail('Request status', row.status) + detail('Requested principal', money(row.requested_amount)) + detail('Current principal', money(row.current_principal)) + detail('Remaining balance', money(row.remaining_balance)) + detail('Contractual total', money(row.contractual_total)) + detail('Paid cash', money(row.paid_cash)) + detail('Paid percent', row.paid_percent == null ? 'Unavailable' : String(row.paid_percent) + '%') + detail('Regular 50% eligibility', typeof row.regular_50_percent_eligible === 'boolean' ? row.regular_50_percent_eligible ? 'Eligible' : 'Not eligible' : 'Unavailable') + detail('Approved principal', money(row.approved_principal)) + detail('Collector recommendation', row.collector_recommendation) + detail('Recommendation reason', row.collector_reason_code) + detail('Collector comment', row.collector_comment) + detail('Client message', row.client_message) + detail('Management review note', row.review_note) + detail('Override reason', row.management_override_reason) + detail('Borrower decision', row.client_decision) + detail('Signer readiness', row.signer_readiness_status) + detail('Office processing', typeof row.office_processing_required === 'boolean' ? row.office_processing_required ? 'Required' : 'Remote workflow' : 'Unavailable') + detail('Locked offset', money(row.renewal_offset_amount)) + detail('Locked net cash', money(row.net_release_amount)) + detail('Photo review', row.handover_proof_status) + detail('Activation', row.activation_status) + detail('New loan', row.new_loan_id) + '</div><details><summary>Saved signer and custody evidence</summary>' + (Array.isArray(row.signers) ? row.signers.map(s => '<p>' + h(s.party_role) + ': ' + h(s.full_name) + ' | account ' + h(s.user_id || 'No linked app') + ' | ID ' + h(s.government_id_verified === true ? 'verified' : 'pending') + ' | selfie ' + h(s.selfie_verified === true ? 'verified' : 'pending') + ' | signature ' + h(s.signed === true ? 'signed' : 'pending') + '</p>').join('') : '<p>Signer evidence unavailable.</p>') + ['submitted_at','recommended_at','reviewed_at','client_decided_at','amount_locked_at','cash_released_to_collector_at','collector_cash_received_at','cash_given_to_client_at','client_cash_confirmed_at'].map(k => '<p>' + h(k.replaceAll('_',' ')) + ': ' + timestamp(row[k]) + '</p>').join('') + '</details><p role="status" tabindex="-1" data-renewal-result></p><div data-renewal-confirm></div><div data-renewal-photo-region></div>';
  if (row.status === 'pending') markup += '<p>' + h(renewalActionBlocker(row,'terms')) + '</p><form class="entry-form" data-renewal-terms><label>Decision<select name="decision"><option value="approved">Approve terms</option><option value="rejected">Reject request</option></select></label><label>Approved principal<input name="approved_principal" inputmode="decimal" autocomplete="off" placeholder="Exact amount, up to 2 decimal places" /></label><label>Review or rejection reason<textarea name="review_note" maxlength="1000"></textarea></label><label>Override reason<textarea name="override_reason" maxlength="1000"></textarea></label><label><input type="checkbox" name="office_processing_required" />Process at the office (does not complete signing or release)</label><p>Enter exact account UUIDs from independently verified identity evidence; names alone are insufficient. Verification checks start unchecked.</p><div data-signers>' + signerMarkup(0,'borrower') + '</div><button type="button" class="button button-outline" data-add-signer>Add required signer</button><label><input type="checkbox" name="all_signers_reviewed" />I reviewed every legally required party and their explicit identity evidence.</label><button class="button button-primary" type="submit">Review terms decision</button></form>';
  if (row.status === 'approved') {
    for (const [action,label] of [['release-to-collector','Release using server execution'],['activate','Review activation']]) markup += '<p>' + h(renewalActionBlocker(row,action)) + '</p><button class="button button-outline" type="button" data-renewal-action="' + action + '"' + (renewalActionBlocker(row,action) ? ' disabled' : '') + '>' + label + '</button>';
    markup += '<p>Release requires the existing authoritative execution record, checked by the server. This queue does not expose that record or pre-lock offset/net cash; no amount is calculated here.</p><button class="button button-outline" type="button" data-renewal-photo>View private latest handover photo</button><form class="entry-form" data-renewal-proof><label>Proof decision<select name="decision"><option value="approved">Approve handover proof</option><option value="request_new_photo">Request new photo</option><option value="flag_for_review">Flag for review</option></select></label><label>Review note<textarea name="note" maxlength="1000"></textarea></label><p>Approving proof may also activate the renewal when all server requirements pass. A saved review can remain CIF-blocked. The latest photo is checked before submission, but it may change before the server saves your review.</p><button type="submit" class="button button-primary"' + (renewalActionBlocker(row,'proof-review') ? ' disabled' : '') + '>Review photo decision</button></form>';
  }
  return markup;
}
function safeError(error) {
  if (error?.status === 401) return 'Sign in again to review renewals.';
  if (error?.status === 403) return 'Access unavailable for this account or device.';
  const messages = {
    renewal_execution_evidence_required:'Create the authoritative renewal execution/disbursement evidence before releasing cash to the Collector.', client_cif_new_credit_not_ready:'Complete the required CIF re-verification before approving or releasing new credit.',renewal_signers_not_ready:'All required signers must complete their own verification and signing, or use office processing.',renewal_amount_already_locked:'Release is already recorded. Refresh the authoritative request.'
  };
  return messages[error?.code] || (error?.status ? 'The server did not accept this action. Refresh and review the current prerequisites.' : 'The read could not be completed. Retry this read.');
}
export function mountManagementRenewals({
  root, api, getSession, signal, onSaved
}) {
  const owner = getSession()?.user?.id;
  const device = () => getSession()?.device_id ?? getSession()?.deviceId ?? api.sessionStore?.deviceId?.() ?? null;
  const ownerDevice = device();
  let disposed = false;
  let generation = 0;
  let status = 'pending';
  let busy = false;
  // An unknown POST result survives every read/filter/open action in this mount.
  // Parent task navigation must consult isWritePending before replacing it.
  let attempt = null;
  let photo = null;
  const rows = new Map();
  const nodes = new Map();
  root.innerHTML='<label>Renewal status<select data-renewal-status>' + statuses.map(s=>'<option value="'+s+'">'+s+'</option>').join('') + '</select></label><div class="inline-actions"><button type="button" class="button button-outline" data-renewal-refresh>Refresh renewals</button><button type="button" class="button button-outline" data-renewal-reconcile hidden>Check uncertain result (read only)</button></div><p role="status" data-renewal-feedback></p><p class="meta" data-renewal-count></p><div class="list-stack" data-renewal-list></div>';
  const list=root.querySelector('[data-renewal-list]'),filter=root.querySelector('[data-renewal-status]'),feedback=root.querySelector('[data-renewal-feedback]'),count=root.querySelector('[data-renewal-count]'),refreshButton=root.querySelector('[data-renewal-refresh]'),reconcileButton=root.querySelector('[data-renewal-reconcile]');
  filter.value=status;
  function revokePhoto(){
    if(photo?.url)URL.revokeObjectURL(photo.url);
    photo=null;
    for(const node of nodes.values()){
      const region=node.querySelector('[data-renewal-photo-region]');
      if(region)region.innerHTML='';
    }
  }
  function deny(error){
    revokePhoto();
    rows.clear();
    nodes.clear();
    list.innerHTML='';
    count.textContent='';
    feedback.textContent=safeError(error);
  }
  function alive(){
    const allowed=!disposed&&!signal?.aborted&&!!owner&&getSession()?.user?.id===owner&&device()===ownerDevice&&hasPermission(getSession(),'renewal.manage');
    if(!allowed&&!disposed){
      deny({
        status:403
      });
    }
    return allowed;
  }
  const path = selected => '/api/v1/management/renewal-workflow?status='+selected;
  const controls=()=>{
    filter.disabled=busy||!!attempt;
    refreshButton.disabled=busy||!!attempt;
    reconcileButton.hidden=!attempt;
    reconcileButton.disabled=busy;
  };
  const local = (node,message) => {
    if(alive())node.querySelector('[data-renewal-result]').textContent=message;
  };
  const dirty = () => Array.from(list.querySelectorAll('input')).some(e=>e.checked===true || (e.type!=='checkbox' && e.getAttribute('type')!=='checkbox' && String(e.value||'').length)) || Array.from(list.querySelectorAll('textarea')).some(e=>String(e.value||'').length) || Array.from(list.querySelectorAll('select')).some(e=>e.value!==(e.querySelector('option[selected]')?.getAttribute('value') ?? e.querySelector('option')?.getAttribute('value')));
  async function readStatus(selected){
    const data=await api.request(path(selected),{
      signal
    });
    if(!Array.isArray(data?.requests)||data.requests.length>200||data.requests.some(r=>!identity(r)||r.status!==selected)||new Set(data.requests.map(r=>r.request_id)).size!==data.requests.length)throw new Error('invalid_queue');
    return data.requests;
  }
  async function fresh(command){
    const found=(await readStatus(command.request.status)).find(r=>r.request_id===command.request.request_id);
    if(!alive())throw new Error('scope_changed');
    if(!found||fingerprint(found)!==command.fingerprint)throw new Error('changed');
    return found;
  }
  async function photoBytes(id){
    const blob=await api.request('/api/v1/renewals/'+encodeURIComponent(id)+'/handover-photo',{
      responseType:'blob',signal
    });
    if(!(blob instanceof Blob)||!['image/jpeg','image/png','image/webp'].includes(blob.type)||!blob.size||blob.size>8*1024*1024)throw new Error('invalid_photo');
    const bytes=new Uint8Array(await blob.arrayBuffer());
    const png=bytes.length>=8&&[137,80,78,71,13,10,26,10].every((n,i)=>bytes[i]===n),jpeg=bytes.length>=3&&bytes[0]===255&&bytes[1]===216&&bytes[2]===255,webp=bytes.length>=12&&String.fromCharCode(...bytes.slice(0,4))==='RIFF'&&String.fromCharCode(...bytes.slice(8,12))==='WEBP';
    if(!({
      'image/jpeg':jpeg,'image/png':png,'image/webp':webp
    })[blob.type])throw new Error('invalid_photo');
    // Browser decoding prevents a matching MIME/header from becoming evidence
    // when the actual image is corrupt. No image or URL is persisted.
    if (typeof globalThis.createImageBitmap === 'function') {
      const bitmap = await globalThis.createImageBitmap(blob);
      try {
        if (!bitmap.width || !bitmap.height) throw new Error('invalid_photo');
      } finally {
        bitmap.close();
      }
    }
    return {
      blob,bytes
    };
  }
  async function checkPhoto(command){
    if(!photo||photo.id!==command.request.request_id)throw new Error('photo_required');
    const current=await photoBytes(photo.id);
    if(!alive())throw new Error('scope_changed');
    if(photo.bytes.length!==current.bytes.length||!photo.bytes.every((b,i)=>b===current.bytes[i])){
      revokePhoto();
      throw new Error('photo_changed');
    }
  }
  function termsBody(form,row){
    const decision=form.querySelector('[name="decision"]').value||'approved',review_note=normalize(form.querySelector('[name="review_note"]').value);
    if(!['approved','rejected'].includes(decision)||review_note.length>1000)throw new Error('Enter a valid decision and review note.');
    if(decision==='rejected'){
      if(review_note.length<3)throw new Error('A rejection reason of at least 3 characters is required.');
      return {
        decision,review_note
      };
    }
    const approved_principal=renewalMoney(form.querySelector('[name="approved_principal"]').value,{
      positive:true
    });
    if(!approved_principal)throw new Error('Enter a positive exact principal with at most 16 whole digits and 2 decimal places.');
    const override_reason=normalize(form.querySelector('[name="override_reason"]').value);
    if(override_reason.length>1000||(row.collector_recommendation==='do_not_recommend'&&override_reason.length<3))throw new Error('Explain the actual Management override before approving against the Collector recommendation.');
    const office_processing_required=form.querySelector('[name="office_processing_required"]').checked===true;
    if(form.querySelector('[name="all_signers_reviewed"]').checked!==true)throw new Error('Review every legally required signer first.');
    const signers=Array.from(form.querySelectorAll('[data-signer]')).map(node=>({
      party_role:node.querySelector('[name="party_role"]').value||'borrower',full_name:normalize(node.querySelector('[name="full_name"]').value),user_id:normalize(node.querySelector('[name="user_id"]').value)||null,government_id_verified:node.querySelector('[name="government_id_verified"]').checked===true,selfie_verified:node.querySelector('[name="selfie_verified"]').checked===true,identity_reviewed:node.querySelector('[name="identity_reviewed"]').checked===true
    }));
    if(signers.length>10||signers.some(s=>!parties.includes(s.party_role)||s.full_name.length<2||s.full_name.length>200||(s.user_id&&!validId(s.user_id))||!s.identity_reviewed||(!office_processing_required&&!s.user_id))||(!office_processing_required&&signers.filter(s=>s.party_role==='borrower').length!==1))throw new Error('Enter and explicitly verify every signer identity; remote processing requires exactly one borrower account and an account for every signer. Otherwise choose office processing.');
    const accounts=signers.filter(s=>s.user_id).map(s=>s.user_id);
    if(new Set(accounts).size!==accounts.length)throw new Error('Distinct required parties cannot use the same account.');
    return {
      decision,approved_principal,review_note,override_reason,office_processing_required,signers:signers.map(({
        identity_reviewed,...s
      })=>s)
    };
  }
  function commandFor(node,row,action,form){
    const blocker=renewalActionBlocker(row,action);
    if(blocker)throw new Error(blocker);
    let body;
    if(action==='terms')body=termsBody(form,row);
    if(action==='proof-review'){
      const decision=form.querySelector('[name="decision"]').value||'approved',note=normalize(form.querySelector('[name="note"]').value);
      if(!Object.hasOwn(proofDecisions,decision)||note.length>1000||(decision!=='approved'&&note.length<3))throw new Error('Choose a proof decision and explain requested corrections or flags.');
      body={
        decision,note
      };
    }
    return {
      action,request:structuredClone(row),body,fingerprint:fingerprint(row)
    };
  }
  function bindRow(node,row){
    const terms=node.querySelector('[data-renewal-terms]'),proof=node.querySelector('[data-renewal-proof]');
    if(terms){
      terms.querySelector('[name="decision"]').value='approved';
      const initialise=()=>{
        for(const [index,s]of Array.from(terms.querySelectorAll('[data-signer]')).entries()){
          const party=s.querySelector('[name="party_role"]');
          if(!party.value)party.value=party.querySelector('option[selected]')?.getAttribute('value')??(index===0?'borrower':'guarantor');
          if(!s.dataset?.renewalBound){
            s.querySelector('[data-remove-signer]').addEventListener('click',()=>{
              if(alive()&&!busy&&!attempt){
                s.remove?.();
                node.querySelector('[data-renewal-confirm]').innerHTML='';
              }
            });
            if(s.dataset)s.dataset.renewalBound='true';
          }
        }
      };
      initialise();
      terms.querySelector('[data-add-signer]').addEventListener('click',()=>{
        if(!alive()||busy||attempt)return;
        const region=terms.querySelector('[data-signers]'),existing=region.querySelectorAll('[data-signer]');
        if(existing.length>=10)return;
        region.insertAdjacentHTML?.('beforeend',signerMarkup(existing.length));
        initialise();
        node.querySelector('[data-renewal-confirm]').innerHTML='';
      });
      terms.addEventListener('submit',e=>{
        e.preventDefault();
        if(node.querySelector('[data-renewal-terms]')===terms)void review(node,row,'terms',terms);
      });
    }
    if(proof){
      proof.querySelector('[name="decision"]').value='approved';
      proof.addEventListener('submit',e=>{
        e.preventDefault();
        if(node.querySelector('[data-renewal-proof]')===proof)void review(node,row,'proof-review',proof);
      });
    }
    for(const form of [terms,proof].filter(Boolean))for(const event of ['input','change'])form.addEventListener(event,()=>{
      if(!attempt)node.querySelector('[data-renewal-confirm]').innerHTML='';
    });
    for(const button of node.querySelectorAll('[data-renewal-action]'))button.addEventListener('click',()=>void review(node,row,button.getAttribute('data-renewal-action')));
    node.querySelector('[data-renewal-photo]')?.addEventListener('click',async()=>{
      if(!alive()||busy||attempt||nodes.get(row.request_id)!==node)return;
      const version=++generation;
      busy=true;
      controls();
      revokePhoto();
      try{
        const command={
          request:row,fingerprint:fingerprint(row)
        };
        await fresh(command);
        const data=await photoBytes(row.request_id);
        if(!alive()||version!==generation)return;
        photo={
          id:row.request_id,bytes:data.bytes,url:URL.createObjectURL(data.blob)
        };
        node.querySelector('[data-renewal-photo-region]').innerHTML='<img class="private-proof-image" style="max-width:100%;height:auto" alt="Private current handover photo for '+h(row.client_code||row.client_name)+'" src="'+h(photo.url)+'" /><p>Private latest photo. It may change before the server saves your review; review the current evidence carefully.</p>';
      }
      catch(error){
        if(alive()){
          revokePhoto();
          if(error.status===401||error.status===403)deny(error);
          else local(node,error?.status?safeError(error):'Current handover photo is unavailable. Retry viewing it before reviewing.');
        }
      }
      finally{
        busy=false;
        controls();
      }
    });
  }
  function confirmationDetails(command) {
    const body = command.body;
    if (command.action === 'terms') {
      let text = '<p>Review reason: ' + h(body.review_note || 'None') + '</p>';
      if (body.decision === 'rejected') return text;
      text += '<p>Override reason: ' + h(body.override_reason || 'None') + ' | Office processing: ' + (body.office_processing_required ? 'Required' : 'Remote') + '</p>';
      return text + body.signers.map(s => '<p>' + h(s.party_role.replaceAll('_', ' ')) + ': ' + h(s.full_name) + ' | Account ' + h(s.user_id || 'No linked app; office required') + ' | Government ID ' + (s.government_id_verified ? 'verified' : 'pending') + ' | Selfie ' + (s.selfie_verified ? 'verified' : 'pending') + '</p>').join('');
    }
    return command.action === 'proof-review' ? '<p>Photo review note: ' + h(body.note || 'None') + '</p>' : '';
  }
  async function review(node,row,action,form){
    if(!alive()||busy||attempt||nodes.get(row.request_id)!==node)return;
    let command;
    try{
      command=commandFor(node,row,action,form);
    }
    catch(error){
      local(node,error.message);
      return;
    }
    busy=true;
    controls();
    try{
      await fresh(command);
      if(action==='proof-review')await checkPhoto(command);
      if(!alive())return;
      if(form&&JSON.stringify(commandFor(node,row,action,form).body)!==JSON.stringify(command.body))throw new Error('changed');
      const region=node.querySelector('[data-renewal-confirm]');
      const warning=action==='proof-review'?'Approving proof may activate the renewal; saved review may still be CIF-blocked. The photo may change before the server saves your review.':action==='release-to-collector'?'The server will validate the existing execution evidence and lock its authoritative offset/net cash. Pre-lock amounts are unavailable in this queue.':action==='activate'?'Activate only this eligible renewal. Client consent, own-account signatures and cash confirmation remain independent.':'Save only these terms; approval does not confirm signatures, cash receipt or activation.';
      region.innerHTML='<div class="notice-card"><h4 tabindex="-1" data-renewal-confirm-title>Confirm '+h(action.replaceAll('-',' '))+'</h4><p>'+h(row.client_name)+' | '+h(row.client_code)+' | '+h(row.loan_number)+'</p><p>Request '+h(row.request_id)+' | Loan '+h(row.loan_id)+'</p><p>'+h(command.body?.decision||action)+' | Approved principal '+money(command.body?.approved_principal||row.approved_principal)+'</p>'+confirmationDetails(command)+'<p>'+h(warning)+'</p><label><input type="checkbox" data-renewal-confirm-ack />I reviewed this exact request, selected decision and evidence.</label><button type="button" class="button button-primary" data-renewal-confirm-action>Confirm '+h(action.replaceAll('-',' '))+'</button><button type="button" class="button button-outline" data-renewal-confirm-close>Close</button></div>';
      region.scrollIntoView?.({block:'start'});
      region.querySelector('[data-renewal-confirm-title]').focus?.({preventScroll:true});
      region.querySelector('[data-renewal-confirm-close]').addEventListener('click',()=>{
        if(!busy&&!attempt){const restore=region.contains?.(globalThis.document?.activeElement);region.innerHTML='';if(restore)(form?.querySelector('button[type="submit"]')??node.querySelector('[data-renewal-action="'+action+'"]'))?.focus();}
      });
      region.querySelector('[data-renewal-confirm-action]').addEventListener('click',()=>void submit(node,command,form));
    }
    catch(error){
      if(error.status===401||error.status===403){
        if(alive())deny(error);
      }
      else local(node,error.message==='changed'?'This request or draft changed. Refresh and deliberately review it again.':error.message==='photo_changed'?'The handover photo changed. View and review the latest photo again.':error?.status?safeError(error):error.message==='photo_required'?'View the private latest handover photo before reviewing.':'Current information could not be verified. Refresh and review it again.');
    }
    finally{
      busy=false;
      controls();
    }
  }
  function saved(node,command,data,message){
    const restoreFocus = node.contains?.(globalThis.document?.activeElement);
    if(photo?.id===command.request.request_id)revokePhoto();
    rows.set(data.request.request_id,data.request);
    node.innerHTML=recordMarkup(data.request);
    bindRow(node,data.request);
    count.textContent='Saved rows remain visible until Refresh. The last queue read returns at most 200 per status, not lifetime history.';
    local(node,message);
    if (restoreFocus) node.querySelector('[data-renewal-result]')?.focus();
  }
  async function submit(node,command,form){
    if(!alive()||busy||attempt||node.querySelector('[data-renewal-confirm-ack]')?.checked!==true)return;
    if(globalThis.navigator?.onLine===false){
      local(node,'Connect to the server before this protected action.');
      return;
    }
    busy=true;
    controls();
    let posted=false;
    try{
      await fresh(command);
      if(command.action==='proof-review')await checkPhoto(command);
      if(!alive())return;
      if(form&&JSON.stringify(commandFor(node,command.request,command.action,form).body)!==JSON.stringify(command.body))throw new Error('changed');
      if(node.querySelector('[data-renewal-confirm-ack]')?.checked!==true)throw new Error('changed');
      posted=true;
      attempt={
        command,node
      };
      controls();
      const opts={
        method:'POST',financial:true,signal
      };
      if(command.body!==undefined)opts.body=command.body;
      const data=await api.request('/api/v1/management/renewals/'+encodeURIComponent(command.request.request_id)+'/'+command.action,opts);
      if(!alive())return;
      if(!renewalResultMatches(command,data))throw new Error('unconfirmed');
      attempt=null;
      const message=command.action==='terms'?'Terms saved.':command.action==='proof-review'?'Photo review saved. '+(data.request.activation_status==='active'?'Renewal is active.':'Activation remains separate or blocked. '+(data.message?'Complete required CIF re-verification and refresh before activation.':'')):command.action==='activate'?'Activation saved.':'Server execution validated; cash release recorded.';
      saved(node,command,data,message);
      try{
        if (await onSaved?.(data.request) === false) throw new Error('Overview refresh failed.');
      }
      catch{
        local(node,message+' Overview refresh failed; the saved action must not be repeated.');
      }
    }
    catch(error){
      if(alive()){
        if(posted&&(!error.status||error.status>=500)){
          local(node,'The result is uncertain. Do not submit again; use the read-only result check.');
        }
        else{
          attempt=null;
          node.querySelector('[data-renewal-confirm]').innerHTML='';
          if(error.status===401||error.status===403){
            deny(error);
          }
          else local(node,error.message==='changed'?'This request or draft changed. Review current information again.':error.message==='photo_changed'?'The photo changed. View and review it again.':error?.status?safeError(error):error.message==='photo_required'?'View the private latest handover photo before reviewing.':'Current information could not be verified. Refresh and review it again.');
        }
      }
    }
    finally{
      busy=false;
      if(alive())controls();
    }
  }
  async function refresh(options={
  }){
    if(!alive()||busy||attempt){
      filter.value=status;
      return false;
    }
    const selected=options.status||options.nextStatus||status;
    if(!statuses.includes(selected))return false;
    if(dirty()&&!globalThis.confirm?.('Discard unsent renewal drafts and load current records?')){
      filter.value=status;
      return false;
    }
    const version=++generation;
    busy=true;
    controls();
    revokePhoto();
    try{
      const items=await readStatus(selected);
      if(!alive()||version!==generation)return false;
      status=selected;
      filter.value=status;
      rows.clear();
      nodes.clear();
      list.innerHTML=items.map(row=>'<article class="data-card" data-renewal-record="'+h(row.request_id)+'">'+recordMarkup(row)+'</article>').join('')||'<p class="meta" role="status" data-management-queue-empty="renewals">No '+h(status)+' renewal requests were returned.</p>';
      for(const node of list.querySelectorAll('[data-renewal-record]')){
        const item=items.find(r=>r.request_id===node.getAttribute('data-renewal-record'));
        rows.set(item.request_id,item);
        nodes.set(item.request_id,node);
        bindRow(node,item);
      }
      count.textContent=items.length+' returned '+status+' requests. This query returns at most 200 per status, not lifetime history.';
      feedback.textContent='';
      return true;
    }
    catch(error){
      if(alive()){
        if(error.status===401||error.status===403){
          deny(error);
        }
        feedback.textContent=safeError(error)+' Use Refresh renewals for this read.';
      }
      return false;
    }
    finally{
      busy=false;
      if(alive())controls();
    }
  }
  async function reconcile(){
    if(!alive()||busy||!attempt)return;
    const pending=attempt;
    busy=true;
    controls();
    try{
      const selected=pending.command.action==='terms'?pending.command.body.decision:'approved';
      const found=(await readStatus(selected)).find(r=>r.request_id===pending.command.request.request_id);
      if(!alive())return;
      if(pending.command.action==='proof-review'||!renewalResultMatches(pending.command,{
        request:found
      })){
        feedback.textContent='The attempted action remains unconfirmed. Further writes remain blocked; latest-photo review also lacks an atomic revision/audit match.';
        return;
      }
      attempt=null;
      saved(pending.node,pending.command,{
        request:found
      },'Matching saved state verified from current records. No action was repeated.');
      feedback.textContent='';
    }
    catch(error){
      if(alive()){
        if(error.status===401||error.status===403){
          deny(error);
        }
        feedback.textContent='Could not verify the attempted action. Further writes remain blocked.';
      }
    }
    finally{
      busy=false;
      if(alive())controls();
    }
  }
  const listeners=[[filter,'change',()=>void refresh({
    status:filter.value
  })],[refreshButton,'click',()=>void refresh()],[reconcileButton,'click',()=>void reconcile()]];
  for(const [el,type,fn]of listeners)el.addEventListener(type,fn);
  function dispose(){
    if(disposed)return;
    disposed=true;
    generation++;
    revokePhoto();
    for(const [el,type,fn]of listeners)el.removeEventListener(type,fn);
    signal?.removeEventListener('abort',dispose);
    rows.clear();
    nodes.clear();
    root.innerHTML='';
  }
  signal?.addEventListener('abort',dispose,{
    once:true
  });
  if(signal?.aborted)dispose();
  return {
    refresh,dispose,isWritePending:()=>!!attempt||busy,openRecord(id){
      if(!alive()||busy||attempt)return false;
      const node=nodes.get(id);
      if(!node)return false;
      if(photo?.id!==id)revokePhoto();
      node.scrollIntoView?.({
        block:'nearest'
      });
      node.querySelector('button')?.focus();
      return true;
    }
  };
}

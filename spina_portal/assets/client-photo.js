import { escapeHtml, hasPermission } from './ui.js';
import { sessionHasRole } from './roles.js';
import { bindOfficeWriteOwner } from './office-case-context.js';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_BYTES = 5 * 1024 * 1024;
const mounts = new WeakMap();
const scope = session => JSON.stringify([session?.user?.id,session?.user?.role,session?.user?.roles,session?.user?.client_id,session?.client_id,session?.device?.id,session?.device_id,session?.permissions,session?.user?.permissions]);
const office = session => sessionHasRole(session,'employee','management') && hasPermission(session,'client_onboarding.requirement.review');
const imageType = type => ['image/jpeg','image/png'].includes(type);

// Only this mounted panel holds image bytes and object URLs. No browser storage
// or direct image URL is used for an authenticated client record.
export function mountClientPhoto({root,api,clientId,clientName='Client',getSession,allowUpload=false,signal,getClientId=()=>clientId,urlApi=globalThis.URL,onDraftChange=()=>{}}) {
  mounts.get(root)?.();
  const identity=scope(getSession?.()),controller=new AbortController();
  const base=`/api/v1/clients/${encodeURIComponent(clientId)}/photo`;
  let disposed=false,metadata=null,draft=null,held=null,busy=false,loading=false,uncertain=false,epoch=0,savedUrl=null,previewUrl=null,message='';
  let listeners=[];
  const listen=(node,event,handler)=>{node?.addEventListener(event,handler);if(node)listeners.push(()=>node.removeEventListener(event,handler));};
  function current(){if(disposed)return false;if(signal?.aborted || !getSession?.() || scope(getSession())!==identity || getClientId()!==clientId){dispose();return false;}return true;}
  const canUpload=()=>allowUpload && office(getSession?.()) && metadata?.can_upload===true;
  function revoke(which){const url=which==='saved'?savedUrl:previewUrl;if(url)urlApi.revokeObjectURL(url);if(which==='saved')savedUrl=null;else previewUrl=null;}
  function valid(value){const p=value?.photo;return value?.client_id===clientId && typeof value.can_upload==='boolean' && (p===null || (p && UUID.test(p.photo_id) && Number.isSafeInteger(p.version) && p.version>0 && imageType(p.content_type) && Number.isSafeInteger(p.byte_size) && p.byte_size>0 && p.byte_size<=MAX_BYTES && p.content_url===`${base}/content?photo_id=${p.photo_id}`));}
  function render(){
    if(!current())return;for(const remove of listeners)remove();listeners=[];
    const url=previewUrl || savedUrl;
    root.innerHTML=`<section class="client-photo-panel" aria-label="Client photo"><div class="client-photo-identity"><div class="client-photo-frame">${url?`<img src="${escapeHtml(url)}" alt="${draft?'Unsaved photo preview':'Client photo'} for ${escapeHtml(clientName)}" />`:'<span class="client-photo-placeholder">No photo</span>'}</div><div><h3>${escapeHtml(clientName)}</h3><p>${draft?'Preview · not saved':metadata?.photo?'Saved client photo':'Client photo is optional.'}</p></div></div><p role="status" aria-live="polite">${escapeHtml(message || (loading?'Loading client photo…':''))}</p>${canUpload()?`<div class="client-photo-inputs"><label>${metadata.photo?'Change photo':'Add photo'}<input type="file" data-photo-file accept="image/jpeg,image/png" /></label><label>Take photo<input type="file" data-photo-camera accept="image/jpeg,image/png" capture="user" /></label></div><p class="meta">JPEG or PNG, up to 5 MiB. Review the preview before saving. This photo does not replace CIF identity verification.</p><div class="action-row"><button class="button button-primary" type="button" data-photo-save>Save photo</button><button class="button button-quiet" type="button" data-photo-discard>Discard preview</button></div>`:''}${uncertain?'<p>The result is unconfirmed. Keep this image and retry the same upload to confirm it.</p><button class="button button-primary" type="button" data-photo-retry>Retry same photo</button>':''}<button class="button button-quiet" type="button" data-photo-reload>Reload photo</button></section>`;
    for(const selector of ['[data-photo-file]','[data-photo-camera]']){const input=root.querySelector(selector);if(input)input.disabled=busy || uncertain || loading;listen(input,'change',()=>select(input));}
    const save=root.querySelector('[data-photo-save]');if(save)save.disabled=!draft || busy || uncertain || loading;
    const discard=root.querySelector('[data-photo-discard]');if(discard)discard.disabled=!draft || busy || uncertain;
    const reload=root.querySelector('[data-photo-reload]');reload.disabled=busy || uncertain || loading;
    const retry=root.querySelector('[data-photo-retry]');if(retry)retry.disabled=busy;
    listen(save,'click',()=>upload());listen(retry,'click',()=>upload(true));listen(reload,'click',()=>load());listen(discard,'click',()=>{if(!current() || busy || uncertain)return;draft=null;held=null;revoke('preview');message='Preview discarded.';onDraftChange();render();});
  }
  function select(input){
    if(!current() || !canUpload() || busy || uncertain || loading)return;
    const file=input.files?.[0];input.value='';if(!file)return;
    if(!imageType(file.type) || !Number.isSafeInteger(file.size) || file.size<1 || file.size>MAX_BYTES){message='Choose a JPEG or PNG image up to 5 MiB.';render();return;}
    revoke('preview');draft=file;held=null;previewUrl=urlApi.createObjectURL(file);message='Review this photo beside the client name, then save.';onDraftChange();render();
  }
  async function content(value,request,saved=false){
    revoke('saved');if(!value.photo)return;
    let blob;
    try{blob=await api.request(value.photo.content_url,{responseType:'blob',signal:controller.signal});}
    catch(error){
      if(error?.status!==404)throw error;
      if(current() && request===epoch){metadata=null;message=`${saved?'Photo saved. ':''}The current photo changed or is unavailable. Reload the photo.`;}
      return false;
    }
    if(!current() || request!==epoch)return;
    if(!blob || blob.type!==value.photo.content_type || blob.size!==value.photo.byte_size)throw Error('The photo bytes could not be verified. Reload the photo.');
    savedUrl=urlApi.createObjectURL(blob);
  }
  function denied(error){if([401,403,404,426].includes(error?.status)){dispose();root.innerHTML='<p role="status">Client photo unavailable. Reopen the authorized client record to try again.</p>';return true;}return false;}
  async function load(){
    if(!current() || busy || uncertain || loading)return false;
    const request=++epoch;loading=true;message='';render();
    try{const value=await api.request(base,{signal:controller.signal});if(!current() || request!==epoch)return false;if(!valid(value))throw Error('The client photo record could not be verified.');metadata=value;const loaded=await content(value,request);return loaded!==false && current();}
    catch(error){if(current() && request===epoch && !denied(error)){message=error.message;revoke('saved');}return false;}
    finally{loading=false;if(current() && request===epoch)render();}
  }
  async function upload(retry=false){
    if(!current() || busy || loading || !canUpload() || !draft || (uncertain && !retry) || (retry && !held))return;
    if(!held)held={file:draft,requestId:globalThis.crypto.randomUUID(),version:metadata.photo?.version ?? 0};
    const original=held,request=++epoch;busy=true;message='Saving photo…';render();
    try{
      const value=await api.request(`${base}?request_id=${original.requestId}&expected_version=${original.version}`,{method:'POST',rawBody:original.file,headers:{'Content-Type':original.file.type},signal:controller.signal});
      if(!current() || request!==epoch)return;
      if(!valid(value) || !value.photo || value.photo.version<original.version+1)throw Error('The saved photo response could not be verified.');
      metadata=value;held=null;draft=null;uncertain=false;revoke('preview');onDraftChange();message=value.photo.version>original.version+1?'Your upload was saved; showing a newer client photo.':'Client photo saved.';
      try{await content(value,request,true);}catch(error){if(current() && !denied(error))message='Photo saved. The preview could not load; reload the photo.';}
    }catch(error){
      if(!current() || request!==epoch || denied(error))return;
      if(error?.beforeWrite || [400,409,413,415,422].includes(error?.status)){
        held=null;uncertain=false;message=error.status===409?'The saved photo changed. Reload the photo, review this preview, then save again.':error.message;
        if(error.status===409)metadata=null;
      }else{uncertain=true;message='The upload result is unconfirmed.';}
    }finally{busy=false;if(current() && request===epoch)render();}
  }
  function dispose(){if(disposed)return;disposed=true;epoch++;controller.abort();signal?.removeEventListener('abort',dispose);for(const remove of listeners)remove();listeners=[];revoke('saved');revoke('preview');metadata=null;draft=null;held=null;uncertain=false;root.innerHTML='';if(mounts.get(root)===dispose)mounts.delete(root);}
  Object.assign(dispose,{isDirty:()=>!disposed && Boolean(draft),isWritePending:()=>!disposed && busy,isUncertain:()=>!disposed && uncertain,refreshReadOnly:load});
  if(allowUpload)api=bindOfficeWriteOwner(api,dispose);
  mounts.set(root,dispose);signal?.addEventListener('abort',dispose,{once:true});
  if(!UUID.test(clientId) || !current()){dispose();dispose.ready=Promise.resolve(false);}else dispose.ready=load();
  return dispose;
}

export function mountClientPhotoLauncher(options){
  const {root,signal}=options;let child=null,disposed=false;
  const identity=scope(options.getSession?.());
  root.innerHTML=`<button class="button button-outline" type="button" data-open-client-photo>${options.allowUpload?'Add / change client photo':'View client photo'}</button><div data-client-photo-body></div>`;
  const button=root.querySelector('[data-open-client-photo]');
  const open=()=>{if(disposed || child)return;if(signal?.aborted || !options.getSession?.() || scope(options.getSession())!==identity || (options.getClientId && options.getClientId()!==options.clientId)){dispose();return;}child=mountClientPhoto({...options,root:root.querySelector('[data-client-photo-body]')});button.hidden=true;};
  function dispose(){if(disposed)return;disposed=true;child?.();child=null;button.removeEventListener('click',open);signal?.removeEventListener('abort',dispose);root.innerHTML='';}
  button.addEventListener('click',open);signal?.addEventListener('abort',dispose,{once:true});if(signal?.aborted)dispose();
  Object.assign(dispose,{isDirty:()=>child?.isDirty()??false,isWritePending:()=>child?.isWritePending()??false,isUncertain:()=>child?.isUncertain()??false,refreshReadOnly:()=>child?.refreshReadOnly()??false});return dispose;
}

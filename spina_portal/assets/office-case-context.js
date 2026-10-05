// One mounted Office workspace owns identities. Forms and Files stay in stages.
const identityFields = ['applicantId', 'intakeReference', 'clientId', 'applicationReference', 'applicationId', 'applicationVersionId'];
const empty = () => ({mode:'none', ...Object.fromEntries(identityFields.map(key=>[key,null])), applicationSaved:false, applicantName:null, stageFacts:{}});
const same = (field,left,right) => field === 'applicationReference' ? left === right : String(left).toLowerCase() === String(right).toLowerCase();
export const officeSessionOwner = session => session?.user ? JSON.stringify({
  id:session.user.id ?? null, role:session.user.role ?? null, roles:[...(session.user.roles ?? [])].sort(),
  permissions:[...(session.permissions ?? [])].sort(), userPermissions:[...(session.user.permissions ?? [])].sort(),
  status:session.user.status ?? null, deviceRegistered:session.user.device_registered ?? null,
}) : null;
const owner = officeSessionOwner;
const officeApis = new WeakMap();
// Each concrete writer owns its flags. Parent aggregates are only transition guards.
export function bindOfficeWriteOwner(api, handle, coordinator) {
  const inherited = officeApis.get(api);
  return (coordinator ?? inherited?.coordinator)?.bindWriteOwner(inherited?.api ?? api, handle) ?? api;
}
function project(value) {
  const result = empty();
  result.mode = value?.mode ?? 'saved-case';
  if (!['none','new-intake','saved-case'].includes(result.mode)) return null;
  for (const key of identityFields) result[key] = typeof value?.[key] === 'string' && value[key].trim() ? value[key] : null;
  result.applicantName = typeof value?.applicantName === 'string' && value.applicantName.trim() ? value.applicantName : null;
  result.applicationSaved = value?.applicationSaved === true;
  if (result.mode !== 'saved-case') return {...empty(),mode:result.mode};
  if (!result.intakeReference) return null;
  for (const [stage,fact] of Object.entries(value.stageFacts ?? {})) {
    if (!fact || typeof fact !== 'object') return null;
    for (const key of identityFields) if (fact[key] != null && (!result[key] || !same(key,fact[key],result[key]))) return null;
    result.stageFacts[stage] = {...fact};
  }
  return result;
}

export function createOfficeCaseContext({getSession, confirmDiscard = message => globalThis.confirm?.(message) === true, onChange = () => {}}) {
  const mountedOwner = owner(getSession?.());
  const stages = new Map();
  const writers = new Set();
  const stores = new Map();
  const requests = new Set();
  const privateDisposers = new Set();
  let disposed = false, generation = 0, activeStage = 'intake', context = empty();
  const snapshot = () => ({...context,stageFacts:Object.fromEntries(Object.entries(context.stageFacts).map(([key,value])=>[key,{...value}])),activeStage,generation});
  function dispose({accessDenied=false} = {}) {
    if (disposed) return;
    disposed = true; generation++; context = empty();
    for(const request of requests)request.abort();
    requests.clear();
    for (const handle of stages.values()) handle.dispose?.();
    stages.clear();
    for (const writer of writers) writer.dispose?.();
    writers.clear();
    for (const cleanup of privateDisposers) cleanup({accessDenied});
    privateDisposers.clear(); onChange(snapshot(),{disposed:true,accessDenied});
  }
  function alive() {
    if (!disposed && (owner(getSession?.()) !== mountedOwner || [...stores].some(([store,value])=>owner(store.load())!==value.owner || store.deviceId?.()!==value.device))) dispose({accessDenied:true});
    return !disposed;
  }
  const locked = () => [...stages.values()].some(handle=>handle.isWritePending?.() || handle.isUncertain?.());
  const dirty = (handles = [...stages.values()]) => handles.some(handle=>handle.isDirty?.());
  const revisions = () => [...stages.values()].map(handle=>handle.getRevision?.());
  const unchanged = previous => previous.every((value,index)=>value === revisions()[index]);
  function acceptVerifiedContext(value, selectedGeneration) {
    if (!alive() || generation !== selectedGeneration) return false;
    const next = project({...context,...value,stageFacts:{...context.stageFacts,...value?.stageFacts}});
    if (!next) return false;
    for (const key of ['intakeReference','applicantId','clientId']) {
      if (context[key] && next[key] && !same(key,context[key],next[key])) return false;
    }
    context = {...context,...next}; onChange(snapshot()); return true;
  }
  async function requestTransition({kind,targetStage=activeStage,candidate}) {
    if (!alive() || !['navigate','open','new-intake','close'].includes(kind)) return false;
    if (kind === 'navigate') { if(activeStage !== targetStage) generation++; activeStage = targetStage; onChange(snapshot()); return true; }
    if (locked()) return false;
    const request = ++generation;
    let next = kind === 'new-intake' ? {...empty(),mode:'new-intake'} : empty();
    let replacing = [...stages.values()];
    if (kind === 'open') {
      let value;
      try { value = typeof candidate === 'function' ? await candidate(request) : candidate; }
      catch(error) { if([401,403].includes(error?.status)){dispose({accessDenied:true});return false;} throw error; }
      if (!alive() || request !== generation || locked()) return false;
      next = project(value);
      if (!next || next.mode !== 'saved-case') return false;
      const sameClientCase = context.intakeReference && next.intakeReference
        && same('intakeReference',next.intakeReference,context.intakeReference)
        && context.clientId && next.clientId && same('clientId',context.clientId,next.clientId)
        && (!context.applicantId || !next.applicantId || same('applicantId',context.applicantId,next.applicantId));
      if (sameClientCase) {
        const applicationSelection = ['application','first-loan'].includes(targetStage);
        const sameApplication = applicationSelection && context.applicationId && context.applicationVersionId
          && next.applicationId && next.applicationVersionId
          && same('applicationReference',context.applicationReference,next.applicationReference)
          && same('applicationId',context.applicationId,next.applicationId) && same('applicationVersionId',context.applicationVersionId,next.applicationVersionId);
        const affected = applicationSelection && !sameApplication ? ['application','first-loan'] : [targetStage];
        replacing = affected.map(stage=>stages.get(stage)).filter(Boolean);
        if (dirty(replacing) && (!applicationSelection || sameApplication)) return false;
        const retainedFacts = Object.fromEntries(Object.entries(context.stageFacts).filter(([stage])=>!affected.includes(stage)));
        next = project({...context,...value,stageFacts:{...retainedFacts,...value.stageFacts}});
        if (!next) return false;
      } else if (dirty() && context.intakeReference && same('intakeReference',next.intakeReference,context.intakeReference)
        && same('applicationReference',next.applicationReference,context.applicationReference)) return false;
    }
    if (dirty(replacing)) {
      const before = revisions();
      const discard = await confirmDiscard('You have unsaved changes. Keep editing or discard changes?');
      if (!discard || !alive() || request !== generation || !unchanged(before) || locked()) return false;
    }
    if (!alive() || request !== generation || locked()) return false;
    for (const handle of replacing) if(handle.resetCase?.() === false)return false;
    context = next; activeStage = targetStage; onChange(snapshot()); return true;
  }
  function bindApi(api,handle,coordinator) {
      const device = api.sessionStore?.deviceId?.();
      const storeOwner = api.sessionStore ? owner(api.sessionStore.load()) : mountedOwner;
      if(api.sessionStore && !stores.has(api.sessionStore))stores.set(api.sessionStore,{owner:storeOwner,device});
      const current = () => {
        if (api.sessionStore && (owner(api.sessionStore.load()) !== storeOwner || api.sessionStore.deviceId?.() !== device)) dispose({accessDenied:true});
        return alive();
      };
      if(handle)writers.add(handle);
      const bound = Object.create(api);
      bound.isOfficeCurrent = current;
      bound.request = async (path, options = {}) => {
        if (!current()) throw Object.assign(new Error('Office access is unavailable.'), {status:403,beforeWrite:true});
        if (!['GET','HEAD'].includes((options.method ?? 'GET').toUpperCase()) && [...writers].some(writer => writer !== handle && (writer.isWritePending?.() || writer.isUncertain?.()))) {
          throw Object.assign(new Error('Keep the original Office operation and reconcile it before another write.'), {beforeWrite:true});
        }
        const request = new AbortController();
        const abort = () => request.abort();
        requests.add(request);
        options.signal?.addEventListener('abort',abort,{once:true});
        if(options.signal?.aborted)abort();
        try {
          const result = await api.request(path, {...options,signal:request.signal});
          if (!current()) throw Object.assign(new Error('Office access changed.'), {status:403});
          return result;
        } catch (error) {
          if ([401,403].includes(error?.status)) dispose({accessDenied:true});
          current();
          throw error;
        } finally {
          requests.delete(request);
          options.signal?.removeEventListener('abort',abort);
        }
      };
      officeApis.set(bound,{api,coordinator});
      return bound;
  }
  return {
    registerStage(stage,handle) { if (alive()) stages.set(stage,handle); else handle.dispose?.(); },
    getContext() { alive(); return snapshot(); },
    getGeneration() { alive(); return generation; },
    // Lookup or owner-held draft edits revoke an in-flight replacement decision.
    invalidateCandidate() { if (alive()) generation++; },
    requestTransition, acceptVerifiedContext, dispose,
    detachReleaseFact(saved) {
      if(!alive() || saved.clientId!==context.clientId || saved.applicationId!==context.applicationId || saved.applicationVersionId===context.applicationVersionId)return false;
      const {['first-loan']:removed,...facts}=context.stageFacts;
      context={...context,stageFacts:facts};onChange(snapshot());return true;
    },
    isWritePending() { return alive() && locked(); },
    refreshReadOnly(stage = activeStage) { if (!alive()) return false; return stages.get(stage)?.refreshReadOnly?.() ?? false; },
    registerPrivateDisposer(cleanup) { if(alive())privateDisposers.add(cleanup);else cleanup({accessDenied:true});return ()=>privateDisposers.delete(cleanup); },
    bindReadOnlyApi(api) { return bindApi(api,null,this); },
    bindWriteOwner(api, handle) { return bindApi(api,handle,this); },
  };
}

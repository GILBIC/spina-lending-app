// One mounted Office workspace owns identities. Forms and Files stay in stages.
const identityFields = ['applicantId', 'intakeReference', 'clientId', 'applicationReference', 'applicationId', 'applicationVersionId'];
const empty = () => ({mode:'none', ...Object.fromEntries(identityFields.map(key=>[key,null])), applicationSaved:false, applicantName:null, stageFacts:{}});
const same = (field,left,right) => field === 'applicationReference' ? left === right : String(left).toLowerCase() === String(right).toLowerCase();
const owner = session => session?.user ? `${session.user.id ?? ''}:${session.user.role ?? ''}:${(session.user.roles ?? []).join(',')}` : null;
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
  let disposed = false, generation = 0, activeStage = 'intake', context = empty();
  const snapshot = () => ({...context,stageFacts:Object.fromEntries(Object.entries(context.stageFacts).map(([key,value])=>[key,{...value}])),activeStage,generation});
  function dispose() {
    if (disposed) return;
    disposed = true; generation++; context = empty();
    for (const handle of stages.values()) handle.dispose?.();
    stages.clear(); onChange(snapshot());
  }
  function alive() { if (!disposed && owner(getSession?.()) !== mountedOwner) dispose(); return !disposed; }
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
      catch(error) { if([401,403].includes(error?.status)){dispose();return false;} throw error; }
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
        if (dirty(replacing) && (!applicationSelection || same('applicationReference',next.applicationReference,context.applicationReference))) return false;
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
  return {
    registerStage(stage,handle) { if (alive()) stages.set(stage,handle); else handle.dispose?.(); },
    getContext() { alive(); return snapshot(); },
    getGeneration() { alive(); return generation; },
    // Lookup or owner-held draft edits revoke an in-flight replacement decision.
    invalidateCandidate() { if (alive()) generation++; },
    requestTransition, acceptVerifiedContext, dispose,
  };
}

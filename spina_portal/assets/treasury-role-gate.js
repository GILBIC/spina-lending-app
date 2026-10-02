export function createTreasuryRoleGate(api,{isTreasuryPending=()=>false,isRolePending=()=>false,getRoleWriteOwner=()=>null}={}){
 let pending=0;const unknown=new Set(),owners=new Set(),wrapped=Object.create(api);
 function unresolved(){for(const attempt of unknown)if(attempt.owner&&attempt.owner.isWritePending()===false)unknown.delete(attempt);return unknown.size>0;}
 wrapped.registerTreasuryOwner=owner=>{owners.add(owner);return ()=>owners.delete(owner);};wrapped.canStartTreasuryWrite=owner=>pending===0&&!unresolved()&&![...owners].some(other=>other!==owner&&other.isWritePending());
 wrapped.request=(path,options={})=>{const write=!['GET','HEAD','OPTIONS'].includes((options.method??'GET').toUpperCase()),treasury=path.startsWith('/api/v1/treasury/');if(!write||treasury)return api.request(path,options);if(isTreasuryPending()||[...owners].some(owner=>owner.isWritePending()))return Promise.reject(Object.assign(Error('Recover the pending Cash and GCash request before another submission.'),{code:'treasury_workspace_locked'}));
  // Capture the mounted source owner before dispatch. Its existing verification
  // contract retains pending state until that exact attempt is confirmed.
  const candidate=getRoleWriteOwner(path,options),owner=candidate?.isWritePending?.()===true?candidate:null;pending++;
  return (async()=>{try{return await api.request(path,options);}catch(error){if(options.financial&&(error.code==='network_uncertain'||error.status===0||error.status>=500))unknown.add({owner});throw error;}finally{pending--;}})();};
 return {api:wrapped,canStartWrite:()=>pending===0&&!unresolved()&&!isRolePending(),isWritePending:()=>pending>0||unresolved()||[...owners].some(owner=>owner.isWritePending())};
}

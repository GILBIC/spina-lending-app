// Private, mount-owned reads. No data survives disposal or an authority change.
export function createClientReadController({signal, isCurrent = () => true, onChange = () => {}} = {}) {
  const entries = new Map();
  const controller = new AbortController();
  let disposed = false;
  const current = () => !disposed && !signal?.aborted && isCurrent();
  const state = (key) => entries.get(key)?.state ?? {status:'idle',data:null,error:null,revision:0};
  function invalidate(key) {
    const revision = state(key).revision + 1;
    entries.get(key)?.controller?.abort();
    entries.set(key,{state:{status:'idle',data:null,error:null,revision}});
  }
  function load(key, loader, {refresh = false} = {}) {
    if (!current()) return Promise.resolve(state(key));
    const old = entries.get(key);
    if (!refresh && old?.promise) return old.promise;
    if (!refresh && old?.state.status === 'ready') return Promise.resolve(old.state);
    old?.controller?.abort();
    const requestController = new AbortController();
    const abort = () => requestController.abort();
    controller.signal.addEventListener('abort',abort,{once:true});
    const entry = {controller:requestController,state:{status:'loading',data:null,error:null,revision:state(key).revision+1}};
    entries.set(key,entry);onChange(key,entry.state);
    entry.promise = (async () => {
      try {
        const data = await loader({signal:requestController.signal});
        if (current() && entries.get(key) === entry && !requestController.signal.aborted) entry.state = {...entry.state,status:'ready',data};
      } catch (error) {
        if (current() && entries.get(key) === entry && !requestController.signal.aborted) entry.state = {...entry.state,status:'error',data:null,error};
      } finally {
        controller.signal.removeEventListener('abort',abort);
        entry.promise = null;
        if (current() && entries.get(key) === entry) onChange(key,entry.state);
      }
      return state(key);
    })();
    return entry.promise;
  }
  function dispose() {if(disposed)return;disposed=true;controller.abort();for(const key of entries.keys())invalidate(key);entries.clear();signal?.removeEventListener('abort',dispose);}
  signal?.addEventListener('abort',dispose,{once:true});
  return {state,load,invalidate,dispose};
}

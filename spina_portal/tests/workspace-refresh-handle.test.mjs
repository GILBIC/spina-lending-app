import assert from 'node:assert/strict';
import test from 'node:test';
import {readFile} from 'node:fs/promises';

// Exercise the actual shell mount/refresh functions with controlled role modules.
const source=await readFile(new URL('../assets/app.js',import.meta.url),'utf8');
function shell() {
  let aborts=0,mounts=0,refreshes=0,disposals=0,context;
  const currentContext={session:{user:{id:'owner'}},role:'management'};
  const value={refreshVisible:async()=>{refreshes++;},dispose:()=>{disposals++;}};
  // Bind the real functions' module state without importing browser initialization.
  const body=source.slice(source.indexOf('async function mountCurrentWorkspace()'),source.indexOf('async function showAuthenticated'));
  const run=new Function('mountImpl','ctx','sharingController','refreshButton','roleContent','workspaceNavigation','escapeHtml','showToast',`
    let currentMount=mountImpl,currentContext=ctx,workspaceController=null,currentWorkspaceHandle=null;
    ${body}
    return {mount:mountCurrentWorkspace,refresh:()=>typeof refreshCurrentWorkspace==='function'?refreshCurrentWorkspace():mountCurrentWorkspace(),clear:()=>workspaceController?.abort()};`);
  const handle=run(async c=>{mounts++;context=c;c.registerWorkspaceHandle?.(value);},currentContext,{session:null,stop(){aborts++;},beforeNavigate(){},afterNavigate(){}},{disabled:false},{innerHTML:''},{activate(){}},x=>x,()=>{});
  return {...handle,getContext:()=>context,counts:()=>({mounts,refreshes,disposals}),currentContext};
}
test('header Refresh uses the registered role handle without remounting its form nodes',async()=>{
  const h=shell();await h.mount();await h.refresh();
  assert.deepEqual(h.counts(),{mounts:1,refreshes:1,disposals:0});
});
test('stale mounts cannot register replacement handles and abort disposes the current one',async()=>{
  const h=shell();await h.mount();const old=h.getContext();h.clear();
  assert.equal(h.counts().disposals,1);
  let staleDisposed=false;
  assert.equal(old.registerWorkspaceHandle?.({dispose(){staleDisposed=true;}}),false);
  assert.equal(staleDisposed,true);
  assert.equal(old.getSession?.(),null);
});
test('same-owner token rotation is visible to later actions through the getter',async()=>{
  const h=shell();await h.mount();h.currentContext.session={user:{id:'owner'},access_token:'new-token'};
  assert.equal(h.getContext().getSession?.().access_token,'new-token');
});

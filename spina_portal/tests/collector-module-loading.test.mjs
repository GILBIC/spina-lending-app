import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {readFile} from 'node:fs/promises';
import {Element} from './helpers/dom.mjs';

// V8 links the real module graph without evaluating the browser's DOM startup.
// This catches indirect eager imports too, not just imports in the role file.
function linkedModules(entry){
  const script=`import {SourceTextModule} from 'node:vm';import {readFileSync} from 'node:fs';
    const cache=new Map();function module(url){if(!cache.has(url))cache.set(url,new SourceTextModule(readFileSync(new URL(url),'utf8'),{identifier:url}));return cache.get(url);}
    await module(${JSON.stringify(new URL(entry,import.meta.url).href)}).link((specifier,parent)=>module(new URL(specifier,parent.identifier).href));
    process.stdout.write(JSON.stringify([...cache.keys()].map(url=>new URL(url).pathname.split('/').pop())));`;
  const result=spawnSync(process.execPath,['--experimental-vm-modules','--input-type=module','-e',script],{encoding:'utf8'});
  assert.equal(result.status,0,result.stderr);return JSON.parse(result.stdout);
}
test('Collector initial module graph excludes unopened secondary task implementations',()=>{
  const modules=linkedModules('../assets/roles/collector.js');
  for(const name of ['collector-workflows.js','collector-other-area.js','collector-renewals.js','collector-remittance.js','collector-activity.js','collector-onboarding-visit.js','employee-operations.js','collector-surplus.js','treasury-payment-claim.js'])assert.equal(modules.includes(name),false,`${name} loaded before its task opens`);
  assert.ok(modules.includes('collector-route-view.js'));assert.ok(modules.includes('collector-write-guard.js'));
});
test('shared shell does not link every role before the authenticated workspace is selected',()=>{
  const modules=linkedModules('../assets/app.js');
  for(const name of ['management.js','collector.js','employee.js','client.js'])assert.equal(modules.includes(name),false,`${name} linked before workspace selection`);
});

test('concurrent task activations share handled module failure and one local retry',async t=>{
  const sourceUrl=new URL('../assets/roles/collector.js',import.meta.url);
  const source=(await readFile(sourceUrl,'utf8'))
    .replace(/from\s+'([^']+)'/g,(_,path)=>`from '${new URL(path,sourceUrl).href}'`)
    .replace("()=>import('../collector-other-area.js')","()=>globalThis.__collectorFailureProbe()");
  let rejectLoad,attempts=0;
  globalThis.__collectorFailureProbe=()=>{attempts++;return new Promise((resolve,reject)=>rejectLoad=reject);};
  t.after(()=>delete globalThis.__collectorFailureProbe);
  const {mountCollectorWorkspace}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
  const root=new Element(),controller=new AbortController();t.after(()=>controller.abort());let handle;
  await mountCollectorWorkspace({root,signal:controller.signal,session:{user:{user_id:'collector'},permissions:['route.view','collection.create']},setNavigation(){},registerWorkspaceHandle:value=>handle=value,sessionStore:{deviceId:()=> 'd',nextDeviceSequence:()=>1},api:{request:async()=>({route_date:'2026-10-03',entries:[]})}});
  const first=handle.activate('collector-other-area'),second=handle.activate('collector-other-area');
  rejectLoad(new Error('Synthetic module unavailable'));
  const results=await Promise.allSettled([first,second]);
  assert.deepEqual(results.map(result=>result.status),['fulfilled','fulfilled']);
  assert.equal(attempts,1);assert.equal(root.querySelectorAll('[data-retry-task]').length,1);
});

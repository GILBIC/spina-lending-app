import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';

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

import assert from 'node:assert/strict';
import test from 'node:test';
import {Element, fire} from './helpers/dom.mjs';
import {mountManagementWorkspace} from '../assets/roles/management.js';

const tick = () => new Promise(resolve => setImmediate(resolve));
const summary = {active_client_count:6, active_loan_count:10, active_remaining_total:'12345.67', overdue_active_count:1};
const session = {user:{id:'manager',role:'management'},permissions:[]};

test('initial failed portfolio read never claims verified zero money', async t => {
  const root = new Element();
  const controller = new AbortController(); t.after(()=>controller.abort());
  let handle;
  await mountManagementWorkspace({root,api:{async request(path){if(path.includes('/management/loans'))throw new Error('Unavailable');return {}; }},session,signal:controller.signal,setNavigation(){},registerWorkspaceHandle(value){handle=value;}});
  await handle?.activate('management-clients-loans'); await tick();
  const panel=root.querySelector('#management-loans');
  assert.ok(panel);
  assert.match(panel.textContent,/Portfolio summary unavailable/);
  assert.doesNotMatch(panel.querySelector('.management-loan-summary')?.textContent || '',/₱0\.00/);
});

test('successful search recovery updates authoritative summary and retains search nodes',async t=>{
  const module=await import('../assets/management-portfolio.js').catch(()=>null);
  assert.ok(module?.mountManagementPortfolio,'the state-preserving portfolio controller must exist');
  const root=new Element();let fail=true;const calls=[];
  const api={async request(path){calls.push(path);if(fail)throw new Error('Unavailable');return {summary,loans:[]};}};
  const controller=new AbortController();t.after(()=>controller.abort());
  const handle=module.mountManagementPortfolio({root,api,signal:controller.signal,getSession:()=>session});
  await handle.refresh();
  assert.match(root.textContent,/Portfolio summary unavailable/);
  const query=root.querySelector('[name="query"]');query.value='paid borrower';
  root.querySelector('[name="status"]').value='paid';fail=false;
  fire(root.querySelector('#management-loan-search'),'submit');await tick();
  assert.equal(root.querySelector('[name="query"]'),query);
  assert.match(root.textContent,/12,345\.67/);
  assert.match(root.textContent,/No loan matches/);
  assert.match(calls.at(-1),/q=paid%20borrower.*status=paid/);
});

test('zero is accepted explicitly while missing or invalid summary fields remain unavailable',async()=>{
  const module=await import('../assets/management-portfolio.js').catch(()=>null);
  assert.ok(module?.managementPortfolioSummaryMarkup);
  const format=module.managementPortfolioSummaryMarkup;
  assert.doesNotMatch(format({status:'error',summary:{}}),/₱0\.00/);
  assert.match(format({status:'ready',summary:{...summary,active_remaining_total:'0.00'}}),/₱0\.00/);
  assert.doesNotMatch(format({status:'ready',summary:{...summary,active_remaining_total:null}}),/₱0\.00/);
  assert.doesNotMatch(format({status:'loading',summary}),/12,345/);
});

test('an older or aborted search cannot replace a newer query response',async t=>{
  const module=await import('../assets/management-portfolio.js').catch(()=>null);assert.ok(module?.mountManagementPortfolio);
  const root=new Element();const pending=[];const controller=new AbortController();t.after(()=>controller.abort());
  const h=module.mountManagementPortfolio({root,api:{request(){return new Promise(resolve=>pending.push(resolve));}},signal:controller.signal,getSession:()=>session});
  const a=h.refresh();root.querySelector('[name="query"]').value='current';const b=h.refresh();
  pending[1]({summary:{...summary,active_remaining_total:'900.00'},loans:[]});await b;
  pending[0]({summary,loans:[]});await a;assert.match(root.textContent,/₱900\.00/);assert.doesNotMatch(root.textContent,/12,345/);
  const c=h.refresh();controller.abort();pending[2]({summary,loans:[]});await c;assert.doesNotMatch(root.textContent,/12,345/);
});

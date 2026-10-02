import assert from 'node:assert/strict';
import test from 'node:test';
import {Element,fire} from './helpers/dom.mjs';
const tick=()=>new Promise(r=>setImmediate(r));

test('local tasks load on first activation, retain DOM drafts and refresh only the visible task',async()=>{
 const mod=await import('../assets/management-workspace-tasks.js').catch(()=>null);assert.ok(mod?.createManagementTaskController,'local task controller must exist');
 const root=new Element();root.innerHTML='<section id="group"><div data-management-task-navigation></div><section id="first"><input name="draft" /></section><section id="second"></section></section>';
 let reads=0,refreshes=0;const order=[];
 const c=mod.createManagementTaskController({root,getSession:()=>({user:{id:'a'}}),beforeTaskChange:()=>order.push('before'),afterTaskChange:()=>order.push('after'),tasks:[
 {id:'first',group:'group',label:'First',mount:async()=>{reads++;return{refresh:async()=>{refreshes++;}};}},
 {id:'second',group:'group',label:'Second',mount:()=>{reads++;}},
 ]});
 assert.equal(reads,0);await c.activate('group','first');assert.equal(reads,1);
 const input=root.querySelector('[name="draft"]');input.value='Unfinished';
 await c.activate('group','second');await c.activate('group','first');assert.equal(reads,2);assert.equal(root.querySelector('[name="draft"]'),input);assert.equal(input.value,'Unfinished');
 await c.refreshVisible();assert.equal(refreshes,1);assert.deepEqual(order,['before','after','before','after','before','after']);c.dispose();
});
test('slow, failed or disposed tasks cannot replace another task or clear pending work',async()=>{
 const mod=await import('../assets/management-workspace-tasks.js').catch(()=>null);assert.ok(mod?.createManagementTaskController);
 const root=new Element();root.innerHTML='<section id="group"><div data-management-task-navigation></div><section id="task"></section></section>';
 let finish,disposed=0,refreshes=0;
 const c=mod.createManagementTaskController({root,getSession:()=>({user:{id:'a'}}),tasks:[{id:'task',group:'group',label:'Task',mount:()=>new Promise(r=>{finish=r;})}]});
 const pending=c.activate('group');await tick();c.dispose();finish({dispose:()=>disposed++,refresh:()=>refreshes++});await pending;
 assert.equal(disposed,1);await c.refreshVisible();assert.equal(refreshes,0);
});
test('changed authority rejects the task and protected refresh cannot bypass its pending lock',async()=>{
 const mod=await import('../assets/management-workspace-tasks.js').catch(()=>null);assert.ok(mod?.createManagementTaskController);
 const root=new Element();root.innerHTML='<section id="group"><div data-management-task-navigation></div><section id="task"></section></section>';
 let allowed=true,pending=true,reads=0;
 const c=mod.createManagementTaskController({root,getSession:()=>({user:{id:'a'}}),tasks:[{id:'task',group:'group',label:'Task',allowed:()=>allowed,mount:()=>({isWritePending:()=>pending,refresh:()=>reads++})}]});
 await c.activate('group');assert.equal(await c.refreshVisible(),false);assert.equal(reads,0);pending=false;await c.refreshVisible();assert.equal(reads,1);allowed=false;assert.equal(await c.activate('group','task'),false);c.dispose();
});

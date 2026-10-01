import assert from 'node:assert/strict';
import test from 'node:test';
import {setButtonBusy, clearButtonBusyFocus} from '../assets/ui.js';

function setup() {
 const doc=new EventTarget();doc.body={};
 const button={dataset:{},textContent:'Save',ownerDocument:doc,isConnected:true,hidden:false,focusCount:0,
  closest(selector){return selector==='[hidden]'&&this.hidden?this:null;},getClientRects(){return this.visible===false?[]:[{}];},
  focus(){doc.activeElement=this;this.focusCount++;}};
 let disabled=false;Object.defineProperty(button,'disabled',{get:()=>disabled,set:value=>{disabled=value;if(value&&doc.activeElement===button)doc.activeElement=doc.body;}});
 doc.activeElement=button;
 const interact=(type,target={})=>{if(type==='focusin')doc.activeElement=target;const event=new Event(type);Object.defineProperty(event,'target',{value:target});doc.dispatchEvent(event);};
 return {doc,button,interact};
}

test('busy button restores lost browser focus when enabled after completion',()=>{
 const f=setup();setButtonBusy(f.button,true);assert.equal(f.doc.activeElement,f.doc.body);
 setButtonBusy(f.button,false);assert.equal(f.doc.activeElement,f.button);assert.equal(f.button.textContent,'Save');
});
for(const scenario of ['focusin','pointerdown','keydown','hidden','detached','invisible','not-originally-focused'])test(`busy completion preserves focus after ${scenario}`,()=>{
 const f=setup();if(scenario==='not-originally-focused')f.doc.activeElement=f.doc.body;
 setButtonBusy(f.button,true);
 if(['focusin','pointerdown','keydown'].includes(scenario))f.interact(scenario);
 if(scenario==='hidden')f.button.hidden=true;
 if(scenario==='detached')f.button.isConnected=false;
 if(scenario==='invisible')f.button.visible=false;
 const before=f.doc.activeElement;setButtonBusy(f.button,false);assert.equal(f.doc.activeElement,before);assert.equal(f.button.focusCount,0);
});
test('repeated busy calls retain original label and original focus ownership',()=>{
 const f=setup();setButtonBusy(f.button,true,'Saving');setButtonBusy(f.button,true,'Still saving');setButtonBusy(f.button,false);
 assert.equal(f.button.textContent,'Save');assert.equal(f.button.focusCount,1);
 setButtonBusy(f.button,false);assert.equal(f.button.focusCount,1);
});
test('intervening interaction remains authoritative across repeated busy calls',()=>{
 const f=setup();setButtonBusy(f.button,true);f.interact('pointerdown');setButtonBusy(f.button,true);setButtonBusy(f.button,false);assert.equal(f.button.focusCount,0);
});


test('stale busy cleanup removes listeners without enabling or focusing the button',()=>{
 const f=setup();const removed=[];const original=f.doc.removeEventListener.bind(f.doc);
 f.doc.removeEventListener=(type,...args)=>{removed.push(type);original(type,...args);};
 setButtonBusy(f.button,true,'Saving');clearButtonBusyFocus(f.button);
 assert.deepEqual(removed.sort(),['focusin','keydown','pointerdown']);
 assert.equal(f.button.disabled,true);assert.equal(f.button.textContent,'Saving');assert.equal(f.button.focusCount,0);
 setButtonBusy(f.button,false);assert.equal(f.button.focusCount,0);
});

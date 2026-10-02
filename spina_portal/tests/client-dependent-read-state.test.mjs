import test from 'node:test';import assert from 'node:assert/strict';
import {Element,fire} from './helpers/dom.mjs';
import {mountClientDocuments} from '../assets/client-documents.js';
import {mountPaymentProofs} from '../assets/payment-proofs.js';
import {renderClientGcashPanel} from '../assets/client-gcash.js';
const tick=()=>new Promise(r=>setTimeout(r,0));
test('documents errors are not empty and independently usable statement survives',()=>{
 const root=new Element();let retries=0;mountClientDocuments({root,api:{},loansState:{status:'error'},paymentsState:{status:'error'},onRetry:()=>retries++});
 assert.match(root.textContent,/Loan records unavailable/);assert.match(root.textContent,/Payment records unavailable/);assert.doesNotMatch(root.textContent,/No linked loan|No official payment/);assert.ok(root.querySelector('[data-statement-copy]'));fire(root.querySelector('[data-document-retry]'),'click');assert.equal(retries,1);
});
test('checkout loan error is not empty',()=>{const html=renderClientGcashPanel({capability:{payment_available:true},loansState:{status:'error'}});assert.match(html,/Loan records unavailable/);assert.doesNotMatch(html,/No active loan|client-gcash-form/);});
test('first proof error has read-only retry and handle never exposes attempt',async()=>{
 const root=new Element();let count=0,handle;mountPaymentProofs({root,api:{request:async(path,options)=>{assert.notEqual(options?.method,'POST');if(++count===1)throw Error('offline');return {proofs:[],capability:{upload_available:false}};}},registerHandle:h=>handle=h});await tick();assert.match(root.textContent,/offline/);assert.ok(root.querySelector('[data-proof-refresh]'));fire(root.querySelector('[data-proof-refresh]'),'click');await tick();assert.equal(count,2);assert.equal(typeof handle.refreshReadOnly,'function');assert.equal('attempt' in handle,false);
});

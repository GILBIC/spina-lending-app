import assert from 'node:assert/strict';
import test from 'node:test';
import { Element, fire } from './helpers/dom.mjs';

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
const loanId = '10000000-0000-4000-8000-000000000001';
const documentId = '20000000-0000-4000-8000-000000000001';
const module = await import('../assets/client-documents.js').catch(() => ({}));

test('Client downloads original loan packet through protected bytes, ignoring server paths', async () => {
  assert.equal(typeof module.mountClientDocuments, 'function');
  const root = new Element(); const calls = []; const saved = [];
  module.mountClientDocuments({root, loans: [{loan_id: loanId, loan_number: '<loan>'}], payments: [],
    api: {request: async (path, options) => { calls.push({path, options});
      if (path.endsWith('/documents')) return {documents: [{document_id: documentId, kind: 'finalized_loan_packet', download_path: 'https://untrusted.test'}]};
      return new Blob(['packet'], {type: 'application/pdf'});
    }}, saveFile: (...args) => saved.push(args)});
  fire(root.querySelector('[data-load-documents]'), 'click'); await tick();
  fire(root.querySelector('[data-download-packet]'), 'click'); await tick();
  assert.equal(calls[1].path, `/api/v1/client/loans/${loanId}/documents/${documentId}`);
  assert.equal(calls[1].options.responseType, 'blob');
  assert.equal(saved.length, 1); assert.equal(await saved[0][0].text(), 'packet');
  assert.doesNotMatch(root.innerHTML, /https:\/\/untrusted|<loan>/);
});

test('Statement and current payment copies use existing record endpoints and describe copies', async () => {
  assert.equal(typeof module.mountClientDocuments, 'function');
  const root = new Element(); const calls = [];
  module.mountClientDocuments({root, loans: [], payments: [{transaction_id: loanId, receipt_number: 'R-1', is_voided:true}],
    api: {request: async (path) => { calls.push(path); return new Blob(['pdf'], {type:'application/pdf'}); }}, saveFile: () => {}});
  assert.match(root.textContent, /record copies/); assert.match(root.textContent, /Voided/);
  fire(root.querySelector('[data-statement-copy]'), 'click'); await tick();
  fire(root.querySelector('[data-payment-copy]'), 'click'); await tick();
  assert.deepEqual(calls, ['/api/v1/client/statement/document', `/api/v1/client/payments/${loanId}/document`]);
});

test('Aborted Client document request cannot save private bytes or restore cleared UI', async () => {
  assert.equal(typeof module.mountClientDocuments, 'function');
  const root = new Element(); let resolve; const saved = []; const controller = new AbortController();
  module.mountClientDocuments({root, loans: [], payments: [], signal: controller.signal,
    api: {request: () => new Promise((done) => {resolve = done;})}, saveFile: (...args) => saved.push(args)});
  fire(root.querySelector('[data-statement-copy]'), 'click'); controller.abort();
  resolve(new Blob(['private'])); await tick(); assert.equal(root.innerHTML, ''); assert.equal(saved.length, 0);
});

test('Released signed evidence keeps its actual media type and distinct label', async () => {
  const root = new Element(); const saved=[];
  module.mountClientDocuments({root,loans:[{loan_id:loanId}],payments:[],saveFile:(...args)=>saved.push(args),
    api:{request:async(path)=>path.endsWith('/documents')?{documents:[{document_id:documentId,kind:'signed_loan_contract',media_type:'image/png'}]}:new Blob(['png'],{type:'image/png'})}});
  fire(root.querySelector('[data-load-documents]'),'click');await tick();
  assert.match(root.textContent,/Signed loan contract/);
  fire(root.querySelector('[data-download-packet]'),'click');await tick();
  assert.match(saved[0][1],/\.png$/);
});

test('A successful HTML response cannot be saved as a payment or statement PDF', async () => {
  const root=new Element();const saved=[];
  module.mountClientDocuments({root,saveFile:(...args)=>saved.push(args),api:{request:async()=>new Blob(['<html>Sign in</html>'],{type:'text/html'})}});
  fire(root.querySelector('[data-statement-copy]'),'click');await tick();
  assert.equal(saved.length,0);assert.doesNotMatch(root.textContent,/Download prepared/);assert.match(root.textContent,/valid.*file/);
});

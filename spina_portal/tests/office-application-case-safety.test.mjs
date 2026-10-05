import assert from 'node:assert/strict';
import test from 'node:test';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {createOfficeCaseContext} from '../assets/office-case-context.js';
import {mountOfficeApplicationReview} from '../assets/office-application-review.js';
import {mountOfficeFirstLoan} from '../assets/office-first-loan.js';
const CLIENT='11111111-1111-4111-8111-111111111111', APP='22222222-2222-4222-8222-222222222222', VERSION='33333333-3333-4333-8333-333333333333', CIF='44444444-4444-4444-8444-444444444444';
const session={user:{id:'synthetic',role:'management'},permissions:['client_onboarding.requirement.review','lending.first_loan.approve']};
const saved=(reference='APP-A')=>({client_id:CLIENT,application_id:APP,application_version_id:VERSION,application_reference:reference,cif_version_id:CIF,cif_version_number:1,version_number:1,recorded_at:'2026-10-03T00:00:00Z',review_scope:'loan_application_information_only',requested_loan_type_name:null,missing_fields:[],information:{request:{requested_loan_type_id:null,purpose:'Synthetic purpose',requested_amount:null,requested_payment_arrangement:null,requested_term:null,preferred_first_payment_date:null},repayment:{repayment_source:null,source_details:null,monthly_gross_income:null,monthly_net_income:null,has_existing_obligations:false,obligations:[]}}});
function harness(mount=mountOfficeApplicationReview){const h={root:new Element(),calls:[],value:saved(),confirm:()=>false};h.coordinator=createOfficeCaseContext({getSession:()=>session,confirmDiscard:()=>h.confirm()});h.read=path=>path.endsWith('/cif-client')?{client_id:CLIENT,application_reference:'INTAKE-A'}:path.endsWith('/entry-context')?{client_id:CLIENT,cif_version_id:CIF,cif_version_number:1,loan_types:[]}:path.endsWith('/context')?{products:[],templates:[]}:path.includes('/by-application/')?{loans:[]}:h.value;h.dispose=mount({root:h.root,api:{async request(path,options={}){h.calls.push({path,options});return h.read(path,options);}},session,officeCaseContext:h.coordinator,registerHandle:handle=>{h.handle=handle;h.coordinator.registerStage(mount===mountOfficeFirstLoan?'first-loan':'application',handle);}});return h;}
async function open(h,app='APP-A'){h.root.querySelector('[name="intakeReference"]').value='INTAKE-A';h.root.querySelector('[name="applicationReference"]').value=app;fire(h.root.querySelector('form'),'submit');await setImmediate();}
function button(h,label){return h.root.querySelectorAll('button').find(b=>b.textContent===label);}
test('verified application handle publishes exact selected saved version',async()=>{const h=harness();await open(h);assert.ok(h.handle);assert.equal(h.coordinator.getContext().applicationVersionId,VERSION);assert.equal(h.coordinator.getContext().stageFacts.application.versionNumber,1);assert.equal(h.calls.filter(c=>c.options.method==='POST').length,0);h.dispose();h.coordinator.dispose();});
test('saved application picker expected version rejects changed detail without replacing selected work',async()=>{const h=harness();await open(h);const panel=h.root.querySelector('[data-application-review-information]');assert.ok(h.handle);const result=await h.handle.openCase({intakeReference:'INTAKE-A',clientId:CLIENT,applicationReference:'APP-A',applicationId:APP,applicationVersionId:CIF,versionNumber:2});assert.equal(result,false);assert.equal(h.root.querySelector('[data-application-review-information]'),panel);assert.equal(h.coordinator.getContext().applicationVersionId,VERSION);h.dispose();h.coordinator.dispose();});
test('application lookup edits and failed target read retain actual draft',async()=>{const h=harness();await open(h);fire(button(h,'Edit application information'),'click');await setImmediate();const purpose=h.root.querySelector('[name="purpose"]');purpose.value='Unfinished application';fire(purpose,'input');h.root.querySelector('[name="applicationReference"]').value='APP-B';fire(h.root.querySelector('[name="applicationReference"]'),'input');assert.equal(h.root.querySelector('[name="purpose"]'),purpose);h.read=()=>{throw Error('Synthetic read failure');};fire(h.root.querySelector('form'),'submit');await setImmediate();assert.equal(h.root.querySelector('[name="purpose"]'),purpose);assert.ok(h.handle.isDirty());assert.equal(await h.coordinator.requestTransition({kind:'new-intake'}),false);h.confirm=()=>true;assert.equal(await h.coordinator.requestTransition({kind:'new-intake'}),true);assert.equal(h.root.querySelector('[name="purpose"]'),null);h.dispose();h.coordinator.dispose();});
test('application candidate invalidated by newer draft edit retains old owner',async()=>{const h=harness();await open(h);fire(button(h,'Edit application information'),'click');await setImmediate();const purpose=h.root.querySelector('[name="purpose"]');purpose.value='Draft';fire(purpose,'input');let done;h.read=path=>path.endsWith('/cif-client')?{client_id:CLIENT,application_reference:'INTAKE-A'}:new Promise(r=>done=r);h.root.querySelector('[name="applicationReference"]').value='APP-B';fire(h.root.querySelector('form'),'submit');await setImmediate();purpose.value='Newer';fire(purpose,'input');done(saved('APP-B'));await setImmediate();assert.equal(h.root.querySelector('[name="purpose"]'),purpose);assert.equal(h.coordinator.getContext().applicationReference,'APP-A');h.dispose();h.coordinator.dispose();});
test('first-loan handle protects actual approval draft and blocks New during original write',async()=>{const h=harness(mountOfficeFirstLoan);await open(h);assert.ok(h.handle);const principal=h.root.querySelector('[name="principal"]');principal.value='1200';fire(principal,'input');assert.ok(h.handle.isDirty());assert.equal(await h.coordinator.requestTransition({kind:'new-intake'}),false);h.confirm=()=>true;assert.equal(await h.coordinator.requestTransition({kind:'new-intake'}),true);assert.equal(h.root.querySelector('[name="principal"]'),null);assert.equal(h.handle.getContext(),null);h.dispose();h.coordinator.dispose();});
import {File} from 'node:buffer';
import {mountOfficeCifSelection} from '../assets/office-cif-selection.js';
import {officeCaseBanner} from '../assets/employee-office-case.js';
const LOAN='55555555-5555-4555-8555-555555555555';
function recordedLoan(){return {loan_id:LOAN,client_id:CLIENT,packet_id:VERSION,packet_hash:'a'.repeat(64),loan_number:'Synthetic loan',status:'approved_pending_release',packet:{loan_id:LOAN,client_id:CLIENT,packet_id:VERSION,application:{application_id:APP,application_version_id:VERSION},borrower:{full_name:'Synthetic applicant'},terms:{principal:'1000.00',schedule_basis_date:'2026-10-03'},net_cash:'1000.00',schedule:[{installment_number:1,due_date:'2026-10-04',contractual_amount:'1100.00',principal_component:'1000.00',interest_component:'100.00'}]},authorization:null,document:{id:CIF,content_sha256:'b'.repeat(64)}};}
async function addCif(h){h.cifRoot=new Element();const read=h.read;h.read=(path,options)=>path.includes('/cif/review-summary')?{client_id:CLIENT,cif_version_id:CIF,version_number:1,status:'draft',review_scope:'cif_information_only',full_name:'Synthetic applicant',phone_number:'00000000000',email:null,present_address:'Synthetic address',can_correct_information:true}:path.includes('/privacy/context')?{client_id:CLIENT,cif_version_id:CIF,subject_id:CIF,application_id:null,application_version_id:null,purpose:'privacy_acknowledgment',issuable:true,detail:'Synthetic privacy',snapshot_sha256:'a'.repeat(64),review_snapshot:{schema_version:1,scope:'privacy_acknowledgment',client_id:CLIENT,cif_version_id:CIF,optional_service_communications:false,notice:{version:'v1',sha256:'b'.repeat(64)},consent:{version:'v1',sha256:'c'.repeat(64)}}}:path.includes('/review-evidence/context')?{client_id:CLIENT,cif_version_id:CIF,purpose:'cif_review',snapshot_sha256:'a'.repeat(64),review_snapshot:{schema_version:1,scope:'cif_information_review',client_id:CLIENT,cif_version_id:CIF,information:{full_name:'Synthetic applicant',phone_number:'00000000000',email:null,present_address:'Synthetic address'}}}:read(path,options);
h.cifDispose=mountOfficeCifSelection({root:h.cifRoot,api:{request:(path,options={})=>{h.calls.push({path,options});return h.read(path,options);}},session,officeCaseContext:h.coordinator,registerHandle:handle=>h.coordinator.registerStage('cif',handle)});h.cifRoot.querySelector('[name="applicationReference"]').value='INTAKE-A';fire(h.cifRoot.querySelector('form'),'submit');await setImmediate();fire(h.cifRoot.querySelector('[data-open-cif-workflow]'),'click');await setImmediate();const field=h.cifRoot.querySelector('[name="signedScan"]'),file=new File(['Synthetic'],'synthetic.pdf',{type:'application/pdf'});field.files=[file];fire(field,'change');return {field,file};}
test('selected application and release reads retain compatible actual CIF File and earlier facts',async()=>{const h=harness(),f=await addCif(h);await open(h);assert.equal(h.cifRoot.querySelector('[name="signedScan"]'),f.field);assert.equal(f.field.files[0],f.file);assert.equal(h.coordinator.getContext().stageFacts.cif.status,'draft');const appPanel=h.root.querySelector('[data-application-review-information]');const releaseRoot=new Element();const release=mountOfficeFirstLoan({root:releaseRoot,api:{request:(path,options={})=>{h.calls.push({path,options});return h.read(path,options);}},session,officeCaseContext:h.coordinator,registerHandle:handle=>h.coordinator.registerStage('first-loan',handle)});await release.openCase(h.handle.getContext());assert.equal(h.root.querySelector('[data-application-review-information]'),appPanel);assert.match(appPanel.textContent,/Synthetic purpose/);assert.equal(f.field.files[0],f.file);assert.equal(h.coordinator.getContext().stageFacts['first-loan'].status,'No recorded first loan');assert.equal(h.calls.filter(c=>c.options.method).length,0);h.coordinator.dispose();});
test('new_intake_detaches_all_old_stage_handoffs from actual CIF application and release owners',async()=>{const h=harness(),f=await addCif(h);await open(h);const releaseRoot=new Element(),read=h.read;h.read=(path,options)=>path.includes('/by-application/')?{loans:[recordedLoan()]}:read(path,options);const release=mountOfficeFirstLoan({root:releaseRoot,api:{request:(path,options={})=>{h.calls.push({path,options});return h.read(path,options);}},session:{...session,permissions:[...session.permissions,'lending.first_loan.release']},officeCaseContext:h.coordinator,registerHandle:handle=>h.coordinator.registerStage('first-loan',handle)});await release.openCase(h.handle.getContext());const contract=releaseRoot.querySelector('[name="contractFile"]'),contractFile=new File(['Synthetic contract'],'contract.pdf',{type:'application/pdf'});contract.files=[contractFile];fire(contract,'change');fire(button(h,'Edit application information'),'click');await setImmediate();const purpose=h.root.querySelector('[name="purpose"]');purpose.value='Unfinished';fire(purpose,'input');assert.equal(await h.coordinator.requestTransition({kind:'new-intake'}),false);assert.equal(h.root.querySelector('[name="purpose"]'),purpose);assert.equal(contract.files[0],contractFile);h.confirm=()=>true;assert.equal(await h.coordinator.requestTransition({kind:'new-intake'}),true);assert.equal(h.coordinator.getContext().mode,'new-intake');assert.equal(h.root.querySelector('[name="purpose"]'),null);assert.equal(releaseRoot.querySelector('[name="contractFile"]'),null);assert.equal(h.cifRoot.querySelector('[name="signedScan"]'),null);assert.equal(h.handle.getContext(),null);assert.equal(release.getContext(),null);assert.equal(h.calls.filter(c=>c.options.method).length,0);h.coordinator.dispose();});
test('two applications for one client preserve CIF File and require current application discard consent',async()=>{const h=harness(),f=await addCif(h);await open(h);fire(button(h,'Edit application information'),'click');await setImmediate();const purpose=h.root.querySelector('[name="purpose"]');purpose.value='Unfinished';fire(purpose,'input');h.value={...saved('APP-B'),application_id:LOAN};const selection={intakeReference:'INTAKE-A',clientId:CLIENT,applicationReference:'APP-B',applicationId:LOAN,applicationVersionId:VERSION,versionNumber:1};assert.equal(await h.handle.openCase(selection),false);assert.equal(h.root.querySelector('[name="purpose"]'),purpose);assert.equal(f.field.files[0],f.file);h.confirm=()=>true;assert.equal(await h.handle.openCase(selection),true);assert.equal(h.root.querySelector('[name="purpose"]'),null);assert.equal(f.field.files[0],f.file);assert.equal(h.coordinator.getContext().applicationId,LOAN);h.coordinator.dispose();});
test('application pending and uncertain save handle guards New while read-only entry failure is not uncertain',async()=>{const h=harness();await open(h);fire(button(h,'Edit application information'),'click');await setImmediate();let reject;const read=h.read;h.read=(path,options)=>options.method==='POST'?new Promise((resolve,no)=>reject=no):read(path,options);fire(h.root.querySelector('[data-application-entry]').querySelector('form'),'submit');await setImmediate();assert.equal(h.handle.isWritePending(),true);assert.equal(await h.coordinator.requestTransition({kind:'new-intake'}),false);reject(Error('Synthetic lost write'));await setImmediate();assert.equal(h.handle.isWritePending(),false);assert.equal(h.handle.isUncertain(),true);assert.equal(await h.coordinator.requestTransition({kind:'close'}),false);assert.equal(h.calls.filter(c=>c.options.method==='POST').length,1);h.coordinator.dispose();const other=harness();other.read=path=>path.endsWith('/cif-client')?{client_id:CLIENT,application_reference:'INTAKE-A'}:path.endsWith('/entry-context')?Promise.reject(Error('Synthetic context failure')):other.value;await open(other);fire(button(other,'Edit application information'),'click');await setImmediate();assert.equal(other.handle.isUncertain(),false);assert.equal(await other.coordinator.requestTransition({kind:'new-intake'}),true);other.coordinator.dispose();});
test('first-loan pending and blocked original write cannot be discarded by New or another lookup',async()=>{const h=harness(mountOfficeFirstLoan),read=h.read;h.read=path=>path.includes('/by-application/')?{loans:[recordedLoan()]}:read(path);await open(h);let reject;h.read=(path,options)=>options.method==='POST'?new Promise((resolve,no)=>reject=no):read(path,options);fire(button(h,'Authorize exact office release'),'click');await setImmediate();assert.equal(h.handle.isWritePending(),true);assert.equal(await h.coordinator.requestTransition({kind:'new-intake'}),false);reject(Error('Synthetic lost write'));await setImmediate();assert.equal(h.handle.isUncertain(),true);assert.equal(await h.coordinator.requestTransition({kind:'new-intake'}),false);const count=h.calls.length;assert.equal(await h.handle.openCase({intakeReference:'INTAKE-A',applicationReference:'APP-B'}),false);assert.equal(h.calls.length,count);assert.equal(h.calls.filter(c=>c.options.method==='POST').length,1);h.coordinator.dispose();});
test('banner facts belong to verified source version and viewing a stage never completes it',async()=>{const h=harness();assert.match(officeCaseBanner(h.coordinator.getContext(),'intake'),/No intake selected/);await open(h);const context=h.coordinator.getContext();assert.match(officeCaseBanner(context,'application'),/Saved version 1/);assert.match(officeCaseBanner(context,'application'),/CIF status: Not loaded/);assert.match(officeCaseBanner(context,'application'),/Approval & release status: Not loaded/);assert.equal(h.coordinator.acceptVerifiedContext({stageFacts:{application:{applicationReference:'APP-A',applicationVersionId:CIF,status:'Approved'}}},h.coordinator.getGeneration()),false);await h.coordinator.requestTransition({kind:'navigate',targetStage:'first-loan'});assert.equal(h.coordinator.getContext().stageFacts['first-loan'],undefined);assert.doesNotMatch(officeCaseBanner(h.coordinator.getContext(),'first-loan'),/status: Approved|Complete/);h.coordinator.dispose();});
test('acknowledged application save retains recoverable saved identity when stale release facts reject publication',async()=>{const h=harness();await open(h);h.coordinator.acceptVerifiedContext({stageFacts:{'first-loan':{applicationReference:'APP-A',applicationVersionId:VERSION,status:'approved_pending_release'}}},h.coordinator.getGeneration());fire(button(h,'Edit application information'),'click');await setImmediate();const read=h.read;h.read=(path,options)=>options.method==='POST'?{...saved(),version_number:2,application_version_id:LOAN}:read(path,options);fire(h.root.querySelector('[data-application-entry]').querySelector('form'),'submit');await setImmediate();assert.match(h.root.textContent,/Application version 2 saved/);assert.match(h.root.textContent,/previously selected version/);assert.equal(h.handle.getContext().applicationVersionId,LOAN);assert.equal(h.coordinator.getContext().applicationVersionId,VERSION);assert.equal(h.coordinator.getContext().stageFacts['first-loan'],undefined);assert.ok(h.root.querySelector('[data-reload-saved-application]'));assert.equal(h.calls.filter(c=>c.options.method==='POST').length,1);assert.equal(h.calls.filter(c=>c.path.endsWith('/review-summary')).length,1);h.coordinator.dispose();});
test('New application from a saved selection produces a distinct unsaved reference and retains compatible CIF File',async()=>{const h=harness(),f=await addCif(h);await open(h);h.root.querySelector('[name="applicationReference"]').value='';fire(button(h,'New application'),'click');await setImmediate();assert.ok(h.root.querySelector('[name="purpose"]'));assert.match(h.coordinator.getContext().applicationReference,/^LOAN-/);assert.equal(h.coordinator.getContext().applicationSaved,false);assert.equal(h.coordinator.getContext().applicationId,null);assert.equal(h.coordinator.getContext().stageFacts.application,undefined);assert.equal(f.field.files[0],f.file);h.coordinator.dispose();});
test('first-loan banner uses actual locked packet version ID and does not infer missing version agreement',async()=>{for(const source of [VERSION,null,CIF]){const h=harness(mountOfficeFirstLoan),read=h.read,loan=recordedLoan();delete loan.packet.application.application_version_id;if(source)loan.packet.application.id=source;h.read=path=>path.includes('/by-application/')?{loans:[loan]}:read(path);await open(h);if(source===CIF){assert.equal(h.coordinator.getContext().applicationId,APP);assert.equal(h.coordinator.getContext().stageFacts['first-loan'].status,'Unavailable');assert.match(h.root.textContent,/different saved version/);}else assert.equal(h.coordinator.getContext().stageFacts['first-loan'].status,source?'approved_pending_release':'Unavailable');h.coordinator.dispose();}});
test('explicit picker version unavailable must not silently adopt a newly appeared saved version',async()=>{const h=harness();await open(h);assert.equal(await h.handle.openCase({intakeReference:'INTAKE-A',clientId:CLIENT,applicationReference:'APP-A',applicationId:APP,applicationVersionId:null,versionNumber:null}),false);assert.match(h.root.textContent,/version changed/);h.coordinator.dispose();});
test('retained Edit action uses verified application identity after application lookup candidate edits',async()=>{const h=harness();await open(h);h.root.querySelector('[name="applicationReference"]').value='APP-B';fire(h.root.querySelector('[name="applicationReference"]'),'input');fire(button(h,'Edit application information'),'click');await setImmediate();assert.equal(h.root.querySelector('[name="purpose"]')?.value,'Synthetic purpose');assert.equal(h.handle.getContext().applicationReference,'APP-A');h.coordinator.dispose();});
for (const outcome of ['accepted', 'cancelled', 'stale']) {
  test(`version-only application selection ${outcome} guards the actual dirty release File`, async () => {
    const h = harness();
    const cifFile = await addCif(h);
    await open(h);
    const releaseRoot = new Element();
    const read = h.read;
    h.read = (path, options) => path.includes('/by-application/')
      ? { loans: [recordedLoan()] } : read(path, options);
    const release = mountOfficeFirstLoan({
      root: releaseRoot,
      api: { request: (path, options = {}) => { h.calls.push({ path, options }); return h.read(path, options); } },
      session: { ...session, permissions: [...session.permissions, 'lending.first_loan.release'] },
      officeCaseContext: h.coordinator,
      registerHandle: handle => h.coordinator.registerStage('first-loan', handle),
    });
    await release.openCase(h.handle.getContext());
    const contract = releaseRoot.querySelector('[name="contractFile"]');
    const originalFile = new File(['Synthetic old contract'], 'old-contract.pdf', { type: 'application/pdf' });
    contract.files = [originalFile];
    fire(contract, 'change');
    let consent, confirmations = 0;
    h.confirm = () => {
      confirmations++;
      return outcome === 'stale' ? new Promise(resolve => { consent = resolve; }) : outcome === 'accepted';
    };
    h.value = { ...saved(), application_version_id: CIF, version_number: 2 };
    const pending = h.handle.openCase({
      intakeReference: 'INTAKE-A', clientId: CLIENT, applicationReference: 'APP-A',
      applicationId: APP, applicationVersionId: CIF, versionNumber: 2,
    });
    await setImmediate();
    assert.equal(confirmations, 1, 'A different saved version must reach current discard consent');
    let retainedFile = originalFile;
    if (outcome === 'stale') {
      retainedFile = new File(['Synthetic newer edit'], 'newer-contract.pdf', { type: 'application/pdf' });
      contract.files = [retainedFile];
      fire(contract, 'change');
      consent(true);
    }
    assert.equal(await pending, outcome === 'accepted');
    assert.equal(cifFile.field.files[0], cifFile.file);
    if (outcome === 'accepted') {
      assert.equal(releaseRoot.querySelector('[name="contractFile"]'), null);
      assert.equal(release.getContext(), null);
      assert.equal(h.coordinator.getContext().applicationVersionId, CIF);
    } else {
      assert.equal(releaseRoot.querySelector('[name="contractFile"]'), contract);
      assert.equal(contract.files[0], retainedFile);
      assert.equal(h.coordinator.getContext().applicationVersionId, VERSION);
    }
    assert.equal(h.calls.filter(call => call.options.method).length, 0);
    h.coordinator.dispose();
  });
}

for (const matchingApproval of [false, true]) {
  test(`selected v2 resumes with historical cancelled v1${matchingApproval ? ' and matching approval' : ''}`, async () => {
    const h = harness(mountOfficeFirstLoan);
    h.value = { ...saved(), application_version_id: CIF, version_number: 2 };
    const old = recordedLoan();
    old.status = 'cancelled';
    old.packet.application = { application_id: APP, id: VERSION, version_number: 1 };
    old.loan_number = 'Synthetic historical v1';
    const current = recordedLoan();
    current.packet.application = { application_id: APP, id: CIF, version_number: 2 };
    current.loan_number = 'Synthetic current v2';
    const read = h.read;
    h.read = path => path.includes('/by-application/')
      ? { loans: matchingApproval ? [old, current] : [old] } : read(path);
    assert.equal(await h.handle.openCase({
      intakeReference: 'INTAKE-A', clientId: CLIENT, applicationReference: 'APP-A',
      applicationId: APP, applicationVersionId: CIF, versionNumber: 2,
    }), true, 'History for another saved version is a legitimate protected response');
    assert.equal(h.coordinator.getContext().applicationVersionId, CIF);
    assert.equal(h.coordinator.getContext().stageFacts['first-loan'].status,
      matchingApproval ? 'approved_pending_release' : 'Unavailable');
    assert.match(h.root.textContent, matchingApproval ? /Synthetic current v2/ : /Synthetic historical v1/);
    if (!matchingApproval) {
      assert.match(h.root.textContent, /Recorded packet application version: 1/);
      assert.match(h.root.textContent, /different saved version/);
      assert.ok(button(h, 'Approve exact terms'), 'Historical cancellation does not disable the existing current-version approval path');
    }
    assert.equal(h.calls.filter(call => call.options.method).length, 0);
    h.coordinator.dispose();
  });
}

test('uncertain first-loan operation blocks a different mounted CIF writer across stage navigation',async()=>{
 const h=harness(mountOfficeFirstLoan),read=h.read,loan=recordedLoan();loan.document=null;
 h.read=path=>path.includes('/by-application/')?{loans:[loan]}:read(path);await open(h);const f=await addCif(h),readAll=h.read;
 h.read=(path,options)=>options.method?Promise.reject(Object.assign(Error('Lost financial result'),{status:0})):readAll(path,options);
 fire(h.root.querySelector('[data-action="documents"]'),'click');await setImmediate();assert.equal(h.handle.isUncertain(),true);
 await h.coordinator.requestTransition({kind:'navigate',targetStage:'cif'});
 const privacy=h.cifRoot.querySelector('[name="signedPrivacyScan"]');const file=new File(['privacy'],'privacy.pdf',{type:'application/pdf'});privacy.files=[file];h.cifRoot.querySelector('[name="witnessedPrivacySignature"]').checked=true;
 fire(h.cifRoot.querySelector('[data-privacy-confirm]'),'submit');await setImmediate();
 assert.equal(h.calls.filter(c=>c.options.method).length,1);assert.equal(f.field.files[0],f.file);assert.equal(privacy.files[0],file);assert.equal(h.handle.isUncertain(),true);h.coordinator.dispose();
});

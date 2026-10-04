import assert from 'node:assert/strict';
import test from 'node:test';
import {createOfficeCaseContext} from '../assets/office-case-context.js';
const saved={mode:'saved-case',intakeReference:'INTAKE-A',applicantId:'applicant-a',clientId:'client-a'};
function setup(confirmDiscard=()=>true){let session={user:{id:'owner',role:'employee'},access_token:'first'};const changes=[];const c=createOfficeCaseContext({getSession:()=>session,confirmDiscard,onChange:value=>changes.push(value)});return {c,changes,setSession:value=>session=value};}
test('navigation retains dirty owners and does not reset or read',async()=>{const {c}=setup();let resets=0,reads=0;c.registerStage('intake',{isDirty:()=>true,resetCase:()=>resets++,openCase:()=>reads++});assert.equal(await c.requestTransition({kind:'navigate',targetStage:'cif'}),true);assert.equal(c.getContext().activeStage,'cif');assert.equal(resets,0);assert.equal(reads,0);});
test('replacement checks write locks before invoking a read or discard',async()=>{const {c}=setup(()=>assert.fail('locked work cannot be discarded'));let reads=0;c.registerStage('intake',{isWritePending:()=>true});assert.equal(await c.requestTransition({kind:'open',candidate:()=>{reads++;return saved;}}),false);assert.equal(reads,0);});
test('cancelled discard preserves verified context and stage owners',async()=>{const {c}=setup(()=>false);c.acceptVerifiedContext(saved,c.getGeneration());let resets=0;c.registerStage('intake',{isDirty:()=>true,resetCase:()=>resets++});assert.equal(await c.requestTransition({kind:'new-intake'}),false);assert.equal(c.getContext().intakeReference,'INTAKE-A');assert.equal(resets,0);});
test('new edits during discard make prior consent stale',async()=>{let resolve;const {c}=setup(()=>new Promise(done=>resolve=done));c.acceptVerifiedContext(saved,c.getGeneration());let resets=0;c.registerStage('intake',{isDirty:()=>true,resetCase:()=>resets++});const transition=c.requestTransition({kind:'close'});await Promise.resolve();c.invalidateCandidate();resolve(true);assert.equal(await transition,false);assert.equal(resets,0);assert.equal(c.getContext().intakeReference,'INTAKE-A');});
test('owner changes dispose owners while token refresh retains context',()=>{const {c,setSession}=setup();let disposed=0;c.registerStage('intake',{dispose:()=>disposed++});c.acceptVerifiedContext(saved,c.getGeneration());setSession({user:{id:'owner',role:'employee'},access_token:'refreshed'});assert.equal(c.getContext().intakeReference,'INTAKE-A');setSession({user:{id:'other',role:'employee'}});assert.equal(c.getContext().mode,'none');assert.equal(disposed,1);});
test('stale verified facts and cross-client application facts cannot change the case',()=>{const {c}=setup();c.acceptVerifiedContext(saved,c.getGeneration());const old=c.getGeneration();c.invalidateCandidate();assert.equal(c.acceptVerifiedContext({...saved,intakeReference:'INTAKE-B'},old),false);assert.equal(c.acceptVerifiedContext({...saved,clientId:'client-b',applicationReference:'APP-B',applicationSaved:true},c.getGeneration()),false);assert.equal(c.getContext().clientId,'client-a');});
test('explicit replacement detaches downstream saved and draft identities',async()=>{const {c}=setup();c.acceptVerifiedContext({...saved,applicationReference:'DRAFT-A',applicationSaved:false},c.getGeneration());assert.equal(await c.requestTransition({kind:'new-intake',targetStage:'intake'}),true);assert.equal(c.getContext().mode,'new-intake');assert.equal(c.getContext().intakeReference,null);assert.equal(c.getContext().applicationReference,null);});
test('denied candidate disposes private owners and returns false',async()=>{const {c}=setup();c.acceptVerifiedContext(saved,c.getGeneration());let disposals=0;c.registerStage('intake',{dispose:()=>disposals++});assert.equal(await c.requestTransition({kind:'open',candidate:async()=>{throw Object.assign(Error('Denied'),{status:403});}}),false);assert.equal(disposals,1);assert.equal(c.getContext().mode,'none');});
test('application fact sources require exact references while intake and UUID identities retain normalization',()=>{
 const {c}=setup();assert.equal(c.acceptVerifiedContext({...saved,clientId:'CLIENT-A',applicationReference:'APP-A',stageFacts:{application:{intakeReference:'intake-a',clientId:'client-a',applicationReference:'APP-A'}}},c.getGeneration()),true);
 assert.equal(c.acceptVerifiedContext({stageFacts:{application:{intakeReference:'INTAKE-A',clientId:'CLIENT-A',applicationReference:'app-a'}}},c.getGeneration()),false);
 assert.equal(c.acceptVerifiedContext({applicationReference:'app-a'},c.getGeneration()),false);
 assert.equal(c.getContext().applicationReference,'APP-A');assert.equal(c.getContext().stageFacts.application.applicationReference,'APP-A');
});
test('case-distinct application references require dirty replacement consent rather than same-case refresh',async()=>{
 let confirmations=0,resets=0;const {c}=setup(()=>{confirmations++;return true;});c.acceptVerifiedContext({...saved,applicationReference:'APP-A'},c.getGeneration());c.registerStage('application',{isDirty:()=>true,resetCase:()=>resets++});
 assert.equal(await c.requestTransition({kind:'open',targetStage:'application',candidate:{...saved,applicationReference:'app-a'}}),true);assert.equal(confirmations,1);assert.equal(resets,1);assert.equal(c.getContext().applicationReference,'app-a');
});
test('first selected application retains dirty CIF owner and compatible verified intake facts',async()=>{const {c}=setup(()=>assert.fail('retained CIF is not discardable'));c.acceptVerifiedContext({...saved,stageFacts:{intake:{intakeReference:'INTAKE-A',clientId:'client-a',status:'eligible_for_cif'},cif:{clientId:'client-a',status:'draft'}}},c.getGeneration());let cifReset=0,applicationReset=0;c.registerStage('cif',{isDirty:()=>true,resetCase:()=>cifReset++});c.registerStage('application',{resetCase:()=>applicationReset++});assert.equal(await c.requestTransition({kind:'open',targetStage:'application',candidate:{...saved,applicationReference:'APP-A',applicationId:'application-a',applicationVersionId:'version-a',applicationSaved:true}}),true);assert.equal(cifReset,0);assert.equal(applicationReset,1);assert.equal(c.getContext().stageFacts.intake.status,'eligible_for_cif');assert.equal(c.getContext().stageFacts.cif.status,'draft');});
test('changing saved application resets only application and release after current consent',async()=>{let consent=0;const {c}=setup(()=>{consent++;return true;});c.acceptVerifiedContext({...saved,applicationReference:'APP-A',applicationId:'application-a',applicationVersionId:'version-a',stageFacts:{cif:{clientId:'client-a',status:'active'},application:{applicationReference:'APP-A',applicationVersionId:'version-a',status:'Saved'},'first-loan':{applicationReference:'APP-A',applicationVersionId:'version-a',status:'released'}}},c.getGeneration());const resets=[];for(const stage of ['intake','cif','application','first-loan'])c.registerStage(stage,{isDirty:()=>true,resetCase:()=>resets.push(stage)});assert.equal(await c.requestTransition({kind:'open',targetStage:'application',candidate:{...saved,applicationReference:'APP-B',applicationId:'application-b',applicationVersionId:'version-b',stageFacts:{application:{applicationReference:'APP-B',applicationVersionId:'version-b',status:'Saved'}}}}),true);assert.deepEqual(resets,['application','first-loan']);assert.equal(consent,1);assert.equal(c.getContext().stageFacts.cif.status,'active');assert.equal(c.getContext().stageFacts['first-loan'],undefined);});
test('different intake or conflicting client fully guards and resets all stage owners',async()=>{for(const candidate of [{...saved,intakeReference:'INTAKE-B'},{...saved,clientId:'client-b'}]){let consent=0;const {c}=setup(()=>{consent++;return true;});c.acceptVerifiedContext(saved,c.getGeneration());const resets=[];for(const stage of ['intake','cif','application','first-loan'])c.registerStage(stage,{isDirty:()=>stage==='cif',resetCase:()=>resets.push(stage)});assert.equal(await c.requestTransition({kind:'open',targetStage:'application',candidate:{...candidate,applicationReference:'APP-A'}}),true);assert.equal(consent,1);assert.deepEqual(resets,['intake','cif','application','first-loan']);}});
for (const accept of [true, false]) test(`same reference new version reaches discard consent (${accept})`, async () => {
  let confirmations = 0;
  const { c } = setup(() => { confirmations++; return accept; });
  c.acceptVerifiedContext({ ...saved, applicationReference: 'APP-A', applicationId: 'application-a', applicationVersionId: 'version-1' }, c.getGeneration());
  const resets = [];
  c.registerStage('cif', { isDirty: () => true, resetCase: () => resets.push('cif') });
  c.registerStage('application', { resetCase: () => resets.push('application') });
  c.registerStage('first-loan', { isDirty: () => true, resetCase: () => resets.push('first-loan') });
  assert.equal(await c.requestTransition({ kind: 'open', targetStage: 'application', candidate: {
    ...saved, applicationReference: 'APP-A', applicationId: 'application-a', applicationVersionId: 'version-2',
  } }), accept);
  assert.equal(confirmations, 1);
  assert.deepEqual(resets, accept ? ['application', 'first-loan'] : []);
  assert.equal(c.getContext().applicationVersionId, accept ? 'version-2' : 'version-1');
});
test('version-only replacement retains global pending and uncertain locks', async () => {
  for (const lock of ['isWritePending', 'isUncertain']) {
    const { c } = setup(() => assert.fail('A locked operation is not discardable'));
    c.acceptVerifiedContext({ ...saved, applicationReference: 'APP-A', applicationId: 'application-a', applicationVersionId: 'version-1' }, c.getGeneration());
    c.registerStage('cif', { [lock]: () => true });
    let reads = 0;
    assert.equal(await c.requestTransition({ kind: 'open', targetStage: 'application', candidate: () => {
      reads++; return { ...saved, applicationReference: 'APP-A', applicationId: 'application-a', applicationVersionId: 'version-2' };
    } }), false);
    assert.equal(reads, 0);
    assert.equal(c.getContext().applicationVersionId, 'version-1');
  }
});

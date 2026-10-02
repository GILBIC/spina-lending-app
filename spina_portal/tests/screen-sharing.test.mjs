import assert from 'node:assert/strict';
import test from 'node:test';
import { Element } from './helpers/dom.mjs';
import { mountManagementWorkspace } from '../assets/roles/management.js';
import {createManagementTaskController} from '../assets/management-workspace-tasks.js';
import {
  isEligibleScreen,
  verifySelfCapture,
  captureRestrictedFrame,
  createScreenShareLifecycle,
  viewerFrameIsNew,
  ScreenSharingController,
} from '../assets/screen-sharing.js';

function groupedManagementContent(groupId, childId) {
  const content = new Element();
  content.innerHTML = `<section id="${groupId}" data-workspace-section>
    <section id="private-sibling"><input type="password"><input type="file"></section>
    <section id="${childId}" data-screen-share-section><p>Audited work records</p></section>
  </section>`;
  function decorate(node, parent = null) {
    Object.defineProperty(node, 'hidden', { get: () => node.getAttribute('hidden') !== null, set: value => value ? node.setAttribute('hidden', '') : node.removeAttribute('hidden') });
    node.closest = selector => selector === '[hidden]' ? (node.hidden ? node : parent?.closest(selector)) : null;
    const query = node.querySelectorAll.bind(node);
    node.querySelectorAll = selector => selector.split(',').flatMap(part => query(part.trim()));
    for (const child of node.children) if (typeof child !== 'string') decorate(child, node);
  }
  decorate(content);
  return content;
}

test('grouped Management sharing restricts each former audited panel and excludes private siblings', async () => {
  const previous = globalThis.RestrictionTarget;
  try {
    for (const [group, child] of [['management-clients-loans', 'management-loans'], ['management-collections', 'management-loan-operations']]) {
      const contentRoot = groupedManagementContent(group, child);
      const panel = contentRoot.querySelector(`#${child}`);
      const restricted = [];
      globalThis.RestrictionTarget = { fromElement: async element => { restricted.push(element); return {}; } };
      const capture = selfTrack();
      const subject = controller({ sectionId: group, contentRoot, handle: 'self', supported: () => true,
        browser: { mediaDevices: { getDisplayMedia: async () => capture.stream } } });
      assert.equal(subject.activeSection(), panel);
      assert.equal(subject.safeToCapture(), true, 'excluded siblings are outside the restricted child');
      assert.equal(isEligibleScreen('management', group), false, 'whole groups must never become eligible');
      await subject.prepare();
      assert.deepEqual(restricted, [panel]);
      assert.equal(subject.preparedTrack, capture.track);
      await subject.stop({ notify: false });
      panel.innerHTML = '<input type="password">';
      assert.equal(subject.safeToCapture(), false, 'a sensitive control inside the audited panel blocks capture');
      subject.dispose();
    }
  } finally { globalThis.RestrictionTarget = previous; }
});

test('grouped Management capture stops when navigating or replacing its exact restricted child', async () => {
  const contentRoot = groupedManagementContent('management-clients-loans', 'management-loans');
  const panel = contentRoot.querySelector('#management-loans');
  let stopped = 0;
  const subject = controller({ sectionId: 'management-clients-loans', contentRoot, restrictedElement: panel,
    track: { stop: () => { stopped += 1; } } });
  subject.beforeNavigate('management-overview');
  assert.equal(stopped, 1);
  assert.equal(subject.track, null);
  subject.sectionId = 'management-clients-loans';
  subject.restrictedElement = panel;
  const group = contentRoot.querySelector('#management-clients-loans');
  group.innerHTML = '<section id="management-loans" data-screen-share-section>Replacement</section>';
  assert.equal(subject.safeToCapture(), false, 'remount cannot reuse an old element restriction');
  subject.restrictedElement = null;
  group.setAttribute('hidden', '');
  assert.equal(subject.safeToCapture(), false, 'hidden groups fail closed');
  subject.dispose();
});

test('Management rendering marks only the two existing audited child panels for grouped capture', async () => {
  const root = new Element(); root.dataset = {};
  const abort = new AbortController();
  try {
    await mountManagementWorkspace({ root, signal: abort.signal, setNavigation() {},
      session: { user: { role: 'management', roles: ['management'] }, permissions: [] },
      api: { request: async () => ({}) } });
    assert.deepEqual(root.querySelectorAll('[data-screen-share-section]').map(panel => panel.getAttribute('id')),
      ['management-loans', 'management-loan-operations']);
  } finally { abort.abort(); }
});

test('Management local task change stops active and prepared capture before hiding the exact public panel',async()=>{
  for(const kind of ['track','preparedTrack']) {
    const contentRoot=groupedManagementContent('management-clients-loans','management-loans');
    const panel=contentRoot.querySelector('#management-loans');let stopped=0,wasVisibleAtStop=false;
    const subject=controller({sectionId:'management-clients-loans',contentRoot});
    const taskController=createManagementTaskController({root:contentRoot,getSession:()=>({user:{id:'manager'}}),beforeTaskChange:()=>void subject.stop({notify:false}),tasks:[{id:'management-loans',group:'management-clients-loans',mount:()=>({})},{id:'private-sibling',group:'management-clients-loans',mount:()=>({})}]});
    await taskController.activate('management-clients-loans','management-loans');
    subject[kind]={stop(){stopped++;wasVisibleAtStop=!panel.hidden;}};
    await taskController.activate('management-clients-loans','private-sibling');
    assert.equal(stopped,1);assert.equal(wasVisibleAtStop,true);assert.equal(panel.hidden,true);assert.equal(subject.safeToCapture(),false);assert.equal(subject[kind],null);
    taskController.dispose();subject.dispose();
  }
});

function controller(overrides = {}) {
  const root = { querySelector: () => null, querySelectorAll: () => [], replaceChildren: () => {} };
  const doc = { hidden: false, addEventListener: () => {}, removeEventListener: () => {}, createElement: () => ({ muted: false, playsInline: false, play: async () => {}, pause: () => {}, remove: () => {}, srcObject: null }) };
  const instance = new ScreenSharingController({ root, contentRoot: { querySelectorAll: () => [] }, api: { request: async () => ({}) }, sessionStore: { deviceId: () => 'raw-client-device-id' }, doc, browser: {}, location: { origin: 'https://spina.test', protocol: 'https:', hostname: 'spina.test' } });
  instance.disposed = false;
  instance.role = 'management';
  instance.sectionId = 'management-overview';
  instance.account = { user: { id: 'viewer-id' } };
  instance.render = () => {};
  instance.refreshLists = async () => {};
  Object.assign(instance, overrides);
  return instance;
}

test('only audited daily screens are eligible; account, credentials, media, and unknown screens fail closed', () => {
  assert.equal(isEligibleScreen('client', 'client-overview'), true);
  assert.equal(isEligibleScreen('collector', 'collector-route'), true);
  assert.equal(isEligibleScreen('management', 'management-overview'), true);
  for (const id of ['client-account', 'management-client-accounts', 'management-staff', 'client-documents', 'management-payment-proofs', 'unknown']) {
    assert.equal(isEligibleScreen('management', id), false);
  }
  assert.equal(isEligibleScreen('client', 'management-overview'), false);
});

test('a different tab, window, or absent Capture Handle is rejected before restriction or upload', async () => {
  for (const [surface, handle] of [['window', {handle:'own',origin:'https://spina.test'}], ['browser', {handle:'other',origin:'https://spina.test'}], ['browser', null]]) {
    let restricted = false;
    const track = {getSettings:()=>({displaySurface:surface}),getCaptureHandle:()=>handle,restrictTo:async()=>{restricted=true;}};
    await assert.rejects(verifySelfCapture(track,{handle:'own',origin:'https://spina.test',restrictionTarget:{}}));
    assert.equal(restricted,false);
  }
});

test('restriction resolves before any image encode or frame upload', async () => {
  const order=[];
  let resolveRestriction;
  const track={getSettings:()=>({displaySurface:'browser'}),getCaptureHandle:()=>({handle:'own',origin:'https://spina.test'}),restrictTo:()=>new Promise(resolve=>{resolveRestriction=()=>{order.push('restricted');resolve();};})};
  const pending=captureRestrictedFrame({track,handle:'own',origin:'https://spina.test',restrictionTarget:{},encode:async()=>{order.push('encoded');return new Blob(['png'],{type:'image/png'});},upload:async()=>{order.push('uploaded');}});
  await Promise.resolve();
  assert.deepEqual(order,[]);
  resolveRestriction();
  await pending;
  assert.deepEqual(order,['restricted','encoded','uploaded']);
});

test('Stop and navigation invalidate late captures and clear viewer pixels', async () => {
  const lifecycle=createScreenShareLifecycle();
  const token=lifecycle.generation();
  lifecycle.setViewerImage('blob:synthetic',0);
  lifecycle.navigate('collector','collector-route');
  assert.equal(lifecycle.current(token),false);
  const next=lifecycle.generation();
  lifecycle.stop();
  assert.equal(lifecycle.current(next),false);
  assert.equal(lifecycle.viewerImage(),null);
});

test('viewer clears stale pixels after three seconds', () => {
  const lifecycle=createScreenShareLifecycle();
  lifecycle.setViewerImage('blob:synthetic',1000);
  assert.equal(lifecycle.clearStaleViewer(3999),false);
  assert.equal(lifecycle.clearStaleViewer(4000),true);
  assert.equal(lifecycle.viewerImage(),null);
});

test('repeated cached frames do not refresh viewer freshness', () => {
  assert.equal(viewerFrameIsNew({generation:2,sequence:7},2,6),true);
  assert.equal(viewerFrameIsNew({generation:2,sequence:7},2,7),false);
  assert.equal(viewerFrameIsNew({generation:1,sequence:8},2,7),false);
});

test('a stopped lifecycle rejects late request and capture generations until a new explicit request', () => {
  const lifecycle=createScreenShareLifecycle();
  const pending=lifecycle.generation();
  lifecycle.stop();
  assert.equal(lifecycle.current(pending),false);
  lifecycle.restart();
  assert.equal(lifecycle.current(pending),false);
  assert.equal(lifecycle.current(lifecycle.generation()),true);
});

test('late Management request cannot resurrect a stopped share and revokes its grant', async () => {
  let resolveRequest;
  const stopped = [];
  const subject = controller({
    targets: [{ user_id: 'holder-account', device_id: 'registered-device-uuid' }],
    api: { request: async (path, options) => {
      if (path === '/api/v1/screen-shares') {
        assert.equal(options.body.holder_device_id, 'registered-device-uuid');
        return new Promise(resolve => { resolveRequest = resolve; });
      }
      stopped.push(path);
      return {};
    } },
  });
  subject.root.querySelector = (selector) => selector === '[data-screen-target]' ? { value: '0' } : null;
  const pending = subject.request();
  await subject.stop({ notify: false });
  resolveRequest({ id: 'late-session', generation: 1, state: 'pending' });
  await pending;
  assert.equal(subject.session, null);
  assert.deepEqual(stopped, ['/api/v1/screen-shares/late-session/stop']);
});

test('late request from old account cannot revive after workspace remount', async () => {
  let resolveRequest;
  const stopped = [];
  const subject = controller({
    targets: [{ user_id: 'old-holder', device_id: 'old-device' }],
    api: { request: async (path) => {
      if (path === '/api/v1/screen-shares') return new Promise(resolve => { resolveRequest = resolve; });
      stopped.push(path);
      return {};
    } },
  });
  subject.root.querySelector = (selector) => selector === '[data-screen-target]' ? { value: '0' } : null;
  subject.observeContent = () => {};
  subject.refreshLists = async () => {};
  subject.supported = () => false;
  const pending = subject.request();
  subject.mount({ session: { user: { role: 'client' } }, role: 'client' });
  resolveRequest({ id: 'old-grant', generation: 1, state: 'pending' });
  await pending;
  assert.equal(subject.session, null);
  assert.deepEqual(stopped, ['/api/v1/screen-shares/old-grant/stop']);
  subject.dispose();
});

test('a hung old pending check is aborted and cannot block polling after remount', async () => {
  let resolveOld;
  let firstSignal;
  let checks = 0;
  const subject = controller({
    account: { user: { role: 'client' } },
    api: { request: async (path, options) => {
      assert.equal(path, '/api/v1/screen-shares/pending');
      checks += 1;
      if (checks === 1) { firstSignal = options.signal; return new Promise(resolve => { resolveOld = resolve; }); }
      return { sessions: [] };
    } },
  });
  subject.observeContent = () => {};
  subject.supported = () => false;
  subject.refreshLists = ScreenSharingController.prototype.refreshLists.bind(subject);
  const old = subject.refreshLists();
  assert.equal(subject.listInFlight, true);
  subject.mount({ session: { user: { role: 'client' } }, role: 'client' });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(firstSignal.aborted, true);
  assert.equal(checks, 2);
  assert.equal(subject.listInFlight, false);
  resolveOld({ sessions: [] });
  await old;
  assert.equal(subject.listInFlight, false);
  subject.dispose();
});

const pendingView = (overrides = {}) => ({
  id: 'f9f5d846-7c60-44d8-a756-01a5c5ce2d93', generation: 1, state: 'pending',
  holder_user_id: 'holder-id', viewer_name: 'Ana', expires_at: new Date(Date.now() + 60000).toISOString(),
  ...overrides,
});

function selfTrack(order = []) {
  const listeners = {};
  const track = {
    getSettings: () => ({ displaySurface: 'browser' }),
    getCaptureHandle: () => ({ handle: 'self', origin: 'https://spina.test' }),
    restrictTo: async () => { order.push('restricted'); },
    addEventListener: (name, fn) => { listeners[name] = fn; },
    stop: () => { order.push('stopped'); },
  };
  return { track, listeners, stream: { getVideoTracks: () => [track], getTracks: () => [track] } };
}

test('Enable browser gesture verifies and restricts self tab without encoding or uploading', async () => {
  const order = [];
  const capture = selfTrack(order);
  const previous = globalThis.RestrictionTarget;
  globalThis.RestrictionTarget = { fromElement: async () => ({}) };
  try {
    const subject = controller({
      role: 'client', sectionId: 'client-overview', handle: 'self',
      safeToCapture: () => true, supported: () => true,
      browser: { mediaDevices: { getDisplayMedia: () => { order.push('browser chooser'); return Promise.resolve(capture.stream); } } },
      api: { request: async () => { throw new Error('Preparation must not use the API'); } },
    });
    await subject.prepare();
    assert.deepEqual(order, ['browser chooser', 'restricted']);
    assert.equal(subject.preparedTrack, capture.track);
    assert.equal(subject.session, null);
    assert.ok(subject.preparedUntil > Date.now());
    await subject.stop({ notify: false });
    assert.equal(order.at(-1), 'stopped');
  } finally { globalThis.RestrictionTarget = previous; }
});

test('a second Enable click cannot open another browser chooser', async () => {
  let resolveChooser;
  let count = 0;
  const subject = controller({
    role: 'client', sectionId: 'client-overview', handle: 'self', safeToCapture: () => true, supported: () => true,
    browser: { mediaDevices: { getDisplayMedia: () => { count += 1; return new Promise(resolve => { resolveChooser = resolve; }); } } },
  });
  const first = subject.prepare();
  const second = subject.prepare();
  assert.equal(count, 1);
  await subject.stop({ notify: false });
  const capture = selfTrack();
  resolveChooser(capture.stream);
  await Promise.all([first, second]);
  assert.equal(subject.preparedTrack, null);
  assert.equal(subject.session, null);
});

test('a rejected old status request cannot stop a newly mounted share', async () => {
  let rejectOld;
  const subject = controller({
    session: { id: 'old-share', generation: 1, state: 'pending' },
    api: { request: async () => new Promise((_, reject) => { rejectOld = reject; }) },
    later: () => {},
  });
  const pending = subject.pollSession('old-share');
  subject.lifecycle.restart();
  subject.session = { id: 'new-share', generation: 1, state: 'active' };
  rejectOld(new Error('old request failed'));
  await pending;
  assert.equal(subject.session.id, 'new-share');
});

test('prepared tab automatically readies only its pending request and paints the named indicator before frames', async () => {
  const order = [];
  const capture = selfTrack(order);
  const previous = globalThis.RestrictionTarget;
  globalThis.RestrictionTarget = { fromElement: async () => ({}) };
  try {
    const item = pendingView();
    const subject = controller({
      role: 'client', sectionId: 'client-overview', handle: 'self', account: { user: { id: 'holder-id' } },
      safeToCapture: () => true, supported: () => true,
      doc: { hidden: false, defaultView: { requestAnimationFrame: callback => { order.push('paint'); callback(); } }, createElement: () => ({ play: async () => {}, pause: () => {}, remove: () => {} }) },
      browser: { mediaDevices: { getDisplayMedia: () => { order.push('chooser'); return Promise.resolve(capture.stream); } } },
      api: { request: async (path, options) => {
        assert.equal(path, `/api/v1/screen-shares/${item.id}/ready`);
        assert.deepEqual(options.body, { generation: 1 });
        order.push('ready');
        return { ...item, state: 'active', holder_device_id: 'registered-device-uuid' };
      } },
      queueCapture: () => { order.push('frame'); },
    });
    subject.render = () => { if (subject.session?.state === 'active') order.push(`visible Management ${subject.session.viewer_name} is viewing`); };
    await subject.prepare();
    assert.deepEqual(order, ['chooser', 'restricted']);
    assert.equal(subject.validPending(pendingView({ holder_user_id: 'someone-else' })), false);
    assert.equal(subject.validPending(pendingView({ expires_at: new Date(Date.now() - 1000).toISOString() })), false);
    assert.equal(subject.validPending(item), true); // Raw X-Device-Id is not the registered device UUID.
    await subject.ready(item);
    assert.deepEqual(order, ['chooser', 'restricted', 'ready', 'visible Management Ana is viewing', 'paint', 'paint', 'frame']);
    assert.equal(subject.participantMode, 'holder');
    await subject.stop({ notify: false });
  } finally { globalThis.RestrictionTarget = previous; }
});

test('local Stop during ready revokes late grant and suppresses exact pending replay', async () => {
  let resolveReady;
  const stopped = [];
  const order = [];
  const capture = selfTrack(order);
  const previous = globalThis.RestrictionTarget;
  globalThis.RestrictionTarget = { fromElement: async () => ({}) };
  try {
    const item = pendingView();
    const subject = controller({
      role: 'client', sectionId: 'client-overview', handle: 'self', account: { user: { id: 'holder-id' } },
      safeToCapture: () => true, supported: () => true,
      browser: { mediaDevices: { getDisplayMedia: async () => capture.stream } },
      queueCapture: () => { throw new Error('late frame scheduled'); },
      api: { request: async path => {
        if (path.endsWith('/ready')) return new Promise(resolve => { resolveReady = resolve; });
        stopped.push(path);
        return {};
      } },
    });
    await subject.prepare();
    const pending = subject.ready(item);
    assert.ok(resolveReady);
    await subject.stop({ notify: false });
    assert.equal(order.at(-1), 'stopped');
    resolveReady({ ...item, state: 'active' });
    await pending;
    assert.equal(subject.session, null);
    assert.equal(subject.validPending(item), false);
    assert.deepEqual(stopped, [`/api/v1/screen-shares/${item.id}/stop`]);
    subject.mount({ session: { user: { id: 'holder-id', role: 'client' } }, role: 'client' });
    assert.equal(subject.validPending(item), false);
    subject.dispose();
  } finally { globalThis.RestrictionTarget = previous; }
});

test('stopped pending request stays suppressed across logout and workspace remount until expiry', async () => {
  let time = Date.now();
  const item = pendingView({ expires_at: new Date(time + 60000).toISOString() });
  const subject = controller({
    account: { user: { id: 'holder-id', role: 'client' } }, role: 'client', sectionId: 'client-overview',
    now: () => time, supported: () => false, observeContent: () => {},
  });
  subject.pendingRequests = [item];
  await subject.stop({ notify: false });
  assert.equal(subject.validPending(item), false);
  subject.mount({ session: { user: { id: 'holder-id', role: 'client' } }, role: 'client' });
  assert.equal(subject.validPending(item), false);
  subject.dispose();
  subject.mount({ session: { user: { id: 'holder-id', role: 'client' } }, role: 'client' });
  assert.equal(subject.validPending(item), false);
  time += 60001;
  assert.equal(subject.validPending(item), false); // The original request has expired.
  assert.equal(subject.suppressedPending.size, 0); // Suppression is bounded, not permanent.
  subject.dispose();
});

test('only Management viewer gets an app Stop or Cancel control; holder status stays visible', () => {
  const root = { innerHTML: '', querySelector: selector => selector === '[data-screen-panel]' ? { open: false } : null, querySelectorAll: () => [] };
  const subject = controller({ root, account: { user: { id: 'holder-id' } }, role: 'management', sectionId: 'management-overview' });
  subject.render = ScreenSharingController.prototype.render.bind(subject);
  subject.preparedTrack = { stop: () => {} };
  subject.render();
  assert.match(root.innerHTML, /Live view ready/);
  assert.doesNotMatch(root.innerHTML, /data-screen-stop|Allow view|Decline view/);
  subject.preparedTrack = null;
  subject.session = { ...pendingView(), state: 'active' };
  subject.participantMode = 'holder';
  subject.render();
  assert.match(root.innerHTML, /Management Ana is viewing/);
  assert.doesNotMatch(root.innerHTML, /data-screen-stop/);
  subject.participantMode = 'viewer';
  subject.render();
  assert.match(root.innerHTML, /data-screen-stop>Stop viewing/);
  subject.session = null;
  subject.requestInFlight = true;
  subject.render();
  assert.match(root.innerHTML, /data-screen-stop>Cancel request/);
});

test('leaving the eligible screen destroys prepared capture and prevents replayed request from readying', async () => {
  const order = [];
  const capture = selfTrack(order);
  const previous = globalThis.RestrictionTarget;
  globalThis.RestrictionTarget = { fromElement: async () => ({}) };
  try {
    const item = pendingView();
    let readyCalls = 0;
    const subject = controller({
      role: 'client', sectionId: 'client-overview', handle: 'self', account: { user: { id: 'holder-id' } },
      safeToCapture: () => true, supported: () => true,
      browser: { mediaDevices: { getDisplayMedia: async () => capture.stream } },
      api: { request: async () => { readyCalls += 1; return {}; } },
    });
    await subject.prepare();
    subject.pendingRequests = [item];
    subject.beforeNavigate('client-account');
    assert.equal(subject.preparedTrack, null);
    assert.equal(subject.validPending(item), false);
    assert.equal(order.at(-1), 'stopped');
    await subject.ready(item);
    assert.equal(readyCalls, 0);
  } finally { globalThis.RestrictionTarget = previous; }
});

test('a hung next frame request cannot keep the previous viewer image visible', async () => {
  let currentTime = 1000;
  let call = 0;
  const scheduled = [];
  const image = { hidden: true, removeAttribute(name) { if (name === 'src') this.src = ''; } };
  const subject = controller({
    now: () => currentTime,
    role: 'management',
    session: { id: 'share', generation: 1, state: 'active' },
    lastViewerSequence: 0,
    participantMode: 'viewer',
    apiFrameGet: async () => {
      call += 1;
      if (call === 1) return { generation: 1, sequence: 1, blob: new Blob(['synthetic'], { type: 'image/png' }) };
      return new Promise(() => {});
    },
    later: (action, delay) => scheduled.push({ action, delay }),
  });
  subject.root.querySelector = (selector) => selector === '[data-screen-view-image]' ? image : null;
  await subject.pollFrame('share');
  assert.equal(image.hidden, false);
  const stale = scheduled.find(item => item.delay === 3000);
  const nextPoll = scheduled.find(item => item.delay === 1000);
  nextPoll.action();
  currentTime = 4000;
  stale.action();
  assert.equal(image.hidden, true);
  assert.equal(subject.lifecycle.viewerImage(), null);
});

test('viewer rejects cacheable and overlarge frame responses before display', async () => {
  const headers = new Map([['X-Screen-Share-Generation', '1'], ['X-Screen-Share-Sequence', '1'], ['Content-Type', 'image/png']]);
  const subject = controller({
    sessionStore: { load: () => ({ access_token: 'synthetic' }), deviceId: () => 'raw-device' },
    api: { apiBaseUrl: '', appVersion: 'test', fetchImpl: async () => ({
      status: 200, headers: { get: name => headers.get(name) || null },
      blob: async () => new Blob(['x'], { type: 'image/png' }),
    }) },
  });
  subject.requestAbort = new AbortController();
  await assert.rejects(subject.apiFrameGet('share'), /caching protection/i);
  headers.set('Cache-Control', 'no-store');
  headers.set('Content-Length', '524289');
  await assert.rejects(subject.apiFrameGet('share'), /too large/i);
});

test('viewer navigation clears pixels without stopping another account’s shared screen', () => {
  const image = { hidden: false, removeAttribute(name) { if (name === 'src') this.src = ''; } };
  const subject = controller({
    role: 'management', session: { id: 'share', state: 'active', generation: 1 }, participantMode: 'viewer',
    requestAbort: { abort: () => {} }, later: () => {},
  });
  subject.root.querySelector = (selector) => selector === '[data-screen-view-image]' ? image : null;
  subject.lifecycle.setViewerImage('blob:synthetic', 0);
  subject.beforeNavigate('management-staff');
  assert.equal(image.hidden, true);
  assert.equal(subject.session.state, 'active');
  assert.equal(subject.lifecycle.viewerImage(), null);
});

test('a navigation during frame encoding invalidates the pending upload', async () => {
  let finishEncoding;
  let uploads = 0;
  const subject = controller({
    role: 'client', sectionId: 'client-overview',
    session: { id: 'share', generation: 2, state: 'active' },
    track: { stop: () => {} }, video: { videoWidth: 640, videoHeight: 360 },
    safeToCapture: () => true, selfCaptureStillValid: () => true,
    queueCapture: () => {},
    api: { request: async () => { uploads += 1; return {}; } },
    doc: { hidden: false, createElement: () => ({
      getContext: () => ({ drawImage: () => {} }),
      toBlob: callback => { finishEncoding = () => callback(new Blob(['synthetic'], { type: 'image/png' })); },
    }) },
  });
  const pending = subject.sendFrame('share');
  assert.equal(typeof finishEncoding, 'function');
  subject.lifecycle.navigate();
  finishEncoding();
  await pending;
  assert.equal(uploads, 0);
});

test('holder frame upload carries generation and sequence only after capture checks', async () => {
  const uploads = [];
  const subject = controller({
    role: 'client', sectionId: 'client-overview',
    session: { id: 'share', generation: 4, state: 'active' },
    track: { stop: () => {} }, video: { videoWidth: 640, videoHeight: 360 },
    safeToCapture: () => true, selfCaptureStillValid: () => true,
    queueCapture: () => {},
    api: { request: async (path, options) => { uploads.push({ path, options }); return {}; } },
    doc: { hidden: false, createElement: () => ({
      getContext: () => ({ drawImage: () => {} }),
      toBlob: callback => callback(new Blob(['synthetic'], { type: 'image/png' })),
    }) },
  });
  await subject.sendFrame('share');
  assert.equal(uploads.length, 1);
  assert.equal(uploads[0].path, '/api/v1/screen-shares/share/frame');
  assert.equal(uploads[0].options.headers['X-Screen-Share-Generation'], '4');
  assert.equal(uploads[0].options.headers['X-Screen-Share-Sequence'], '1');
  assert.equal(uploads[0].options.rawBody.type, 'image/png');
});

test('aborted upload on eligible navigation conservatively paces the next frame', async () => {
  let rejectUpload;
  let currentTime = 1000;
  const queued = [];
  const subject = controller({
    role: 'client', sectionId: 'client-overview', now: () => currentTime,
    session: { id: 'share', generation: 2, state: 'active' },
    track: { stop: () => {} }, video: { videoWidth: 640, videoHeight: 360, pause: () => {}, remove: () => {} },
    safeToCapture: () => true, selfCaptureStillValid: () => true,
    queueCapture: delay => queued.push(delay),
    api: { request: async () => new Promise((_, reject) => { rejectUpload = reject; }) },
    doc: { hidden: false, createElement: () => ({ getContext: () => ({ drawImage: () => {} }), toBlob: cb => cb(new Blob(['synthetic'], { type: 'image/png' })) }) },
  });
  const pending = subject.sendFrame('share');
  while (!rejectUpload) await Promise.resolve();
  subject.lifecycle.navigate();
  currentTime = 1300;
  rejectUpload(new Error('aborted after possible server acceptance'));
  await pending;
  assert.ok(subject.nextFrameAt >= 2400);
  assert.deepEqual(queued, [0]);
});

test('a hung old upload cannot keep a new share capture marked busy', async () => {
  let firstUpload;
  let uploads = 0;
  const subject = controller({
    role: 'client', sectionId: 'client-overview',
    session: { id: 'old-share', generation: 1, state: 'active' },
    track: { stop: () => {} }, video: { videoWidth: 640, videoHeight: 360, pause: () => {}, remove: () => {} },
    safeToCapture: () => true, selfCaptureStillValid: () => true, queueCapture: () => {},
    api: { request: async () => {
      uploads += 1;
      if (uploads === 1) return new Promise(resolve => { firstUpload = resolve; });
      return {};
    } },
    doc: { hidden: false, createElement: () => ({ getContext: () => ({ drawImage: () => {} }), toBlob: cb => cb(new Blob(['synthetic'], { type: 'image/png' })) }) },
  });
  const old = subject.sendFrame('old-share');
  while (!firstUpload) await Promise.resolve();
  subject.stopLocal();
  subject.lifecycle.restart();
  subject.session = { id: 'new-share', generation: 1, state: 'active' };
  subject.track = { stop: () => {} };
  await subject.sendFrame('new-share');
  assert.equal(uploads, 2);
  firstUpload({});
  await old;
  assert.equal(subject.captureInFlight, false);
});

test('unsupported browser and excluded work screen explain why Enable is unavailable while viewing stays possible', () => {
  const subject = controller({ role: 'client', sectionId: 'client-overview', supported: () => false });
  assert.match(subject.captureUnavailableReason(), /supported browser/i);
  assert.match(subject.captureUnavailableReason(), /Viewing remains available/i);
  subject.supported = () => true;
  subject.handle = 'self';
  subject.sectionId = 'client-account';
  assert.match(subject.captureUnavailableReason(), /excluded/i);
});

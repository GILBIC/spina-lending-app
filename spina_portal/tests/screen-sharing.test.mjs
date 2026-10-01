import assert from 'node:assert/strict';
import test from 'node:test';
import {
  isEligibleScreen,
  verifySelfCapture,
  captureRestrictedFrame,
  createScreenShareLifecycle,
  viewerFrameIsNew,
  ScreenSharingController,
} from '../assets/screen-sharing.js';

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

test('double-clicking Accept opens one chooser and Stop cancels the pending attempt', async () => {
  let resolveChooser;
  let chooserCount = 0;
  const subject = controller({
    role: 'client', sectionId: 'client-overview', handle: 'self',
    safeToCapture: () => true, supported: () => true,
    browser: { mediaDevices: { getDisplayMedia: () => { chooserCount += 1; return new Promise(resolve => { resolveChooser = resolve; }); } } },
  });
  const item = { id: 'grant', generation: 1 };
  const first = subject.acceptAndShare(item);
  const second = subject.acceptAndShare(item);
  assert.equal(chooserCount, 1);
  await subject.stop({ notify: false });
  let stopped = false;
  const track = { stop: () => { stopped = true; } };
  resolveChooser({ getVideoTracks: () => [track], getTracks: () => [track] });
  await Promise.all([first, second]);
  assert.equal(stopped, true);
  assert.equal(subject.session, null);
});

test('a device already viewing another holder cannot accept an overlapping request', async () => {
  let chooserCount = 0;
  let postCount = 0;
  const subject = controller({
    role: 'management', sectionId: 'management-overview', handle: 'self',
    session: { id: 'viewing-a', generation: 1, state: 'active' }, participantMode: 'viewer',
    safeToCapture: () => true, supported: () => true,
    browser: { mediaDevices: { getDisplayMedia: () => { chooserCount += 1; } } },
    api: { request: async () => { postCount += 1; return {}; } },
  });
  assert.match(subject.captureUnavailableReason(), /already has a screen request or active share/i);
  await subject.acceptAndShare({ id: 'holder-b-request', generation: 1 });
  assert.equal(chooserCount, 0);
  assert.equal(postCount, 0);
  assert.equal(subject.session.id, 'viewing-a');
});

test('a queued ended event from an old capture cannot stop a newer share', async () => {
  const listeners = {};
  const oldTrack = { getSettings: () => ({ displaySurface: 'browser' }), getCaptureHandle: () => ({ handle: 'self', origin: 'https://spina.test' }), restrictTo: async () => {}, addEventListener: (name, fn) => { listeners[name] = fn; }, stop: () => {} };
  const previous = globalThis.RestrictionTarget;
  globalThis.RestrictionTarget = { fromElement: async () => ({}) };
  try {
    const subject = controller({
      role: 'client', sectionId: 'client-overview', handle: 'self', safeToCapture: () => true, supported: () => true,
      browser: { mediaDevices: { getDisplayMedia: async () => ({ getVideoTracks: () => [oldTrack], getTracks: () => [oldTrack] }) } },
      api: { request: async () => ({ id: 'old-grant', generation: 1, state: 'active' }) },
      queueCapture: () => {},
    });
    await subject.acceptAndShare({ id: 'old-grant', generation: 1 });
    await subject.stop({ notify: false });
    subject.session = { id: 'new-grant', generation: 1, state: 'active' };
    subject.track = { stop: () => {} };
    listeners.ended();
    assert.equal(subject.session.id, 'new-grant');
  } finally { globalThis.RestrictionTarget = previous; }
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

test('holder browser gesture restricts own tab before POST accept and works with a different raw device header', async () => {
  const order = [];
  let ended = false;
  const track = {
    getSettings: () => ({ displaySurface: 'browser' }),
    getCaptureHandle: () => ({ handle: 'self-handle', origin: 'https://spina.test' }),
    restrictTo: async () => { order.push('restrict'); },
    addEventListener: () => {},
    stop: () => { ended = true; },
  };
  const previous = globalThis.RestrictionTarget;
  globalThis.RestrictionTarget = { fromElement: async () => ({}) };
  try {
    const subject = controller({
      role: 'client', sectionId: 'client-overview', handle: 'self-handle',
      safeToCapture: () => true,
      supported: () => true,
      queueCapture: () => { order.push('capture scheduled'); },
      browser: { mediaDevices: { getDisplayMedia: () => { order.push('browser chooser'); return Promise.resolve({ getVideoTracks: () => [track], getTracks: () => [track] }); } } },
      api: { request: async (path, options) => {
        assert.equal(path, '/api/v1/screen-shares/grant/accept');
        assert.deepEqual(options.body, { generation: 1 });
        order.push('accept');
        return { id: 'grant', generation: 1, state: 'active', holder_device_id: 'registered-device-uuid' };
      } },
    });
    await subject.acceptAndShare({ id: 'grant', generation: 1 });
    assert.deepEqual(order, ['browser chooser', 'restrict', 'accept', 'capture scheduled']);
    assert.equal(subject.participantMode, 'holder');
    assert.equal(subject.session.holder_device_id, 'registered-device-uuid');
    assert.equal(ended, false);
    await subject.stop({ notify: false });
    assert.equal(ended, true);
  } finally { globalThis.RestrictionTarget = previous; }
});

test('Stop while accept is pending revokes the late accepted grant and never schedules frames', async () => {
  let resolveAccept;
  const stopped = [];
  let captureStopped = false;
  const track = {
    getSettings: () => ({ displaySurface: 'browser' }),
    getCaptureHandle: () => ({ handle: 'self', origin: 'https://spina.test' }),
    restrictTo: async () => {}, addEventListener: () => {}, stop: () => { captureStopped = true; },
  };
  const previous = globalThis.RestrictionTarget;
  globalThis.RestrictionTarget = { fromElement: async () => ({}) };
  try {
    const subject = controller({
      role: 'client', sectionId: 'client-overview', handle: 'self',
      safeToCapture: () => true, supported: () => true,
      queueCapture: () => { throw new Error('late frame scheduled'); },
      browser: { mediaDevices: { getDisplayMedia: async () => ({ getVideoTracks: () => [track], getTracks: () => [track] }) } },
      api: { request: async (path) => {
        if (path.endsWith('/accept')) return new Promise(resolve => { resolveAccept = resolve; });
        stopped.push(path);
        return {};
      } },
    });
    const pending = subject.acceptAndShare({ id: 'grant', generation: 1 });
    while (!resolveAccept) await Promise.resolve();
    await subject.stop({ notify: false });
    assert.equal(captureStopped, true);
    resolveAccept({ id: 'grant', generation: 1, state: 'active' });
    await pending;
    assert.equal(subject.session, null);
    assert.deepEqual(stopped, ['/api/v1/screen-shares/grant/stop']);
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

test('unsupported browser and excluded work screen explain why Accept is unavailable while viewing stays possible', () => {
  const subject = controller({ role: 'client', sectionId: 'client-overview', supported: () => false });
  assert.match(subject.captureUnavailableReason(), /supported browser/i);
  assert.match(subject.captureUnavailableReason(), /Viewing remains available/i);
  subject.supported = () => true;
  subject.handle = 'self';
  subject.sectionId = 'client-account';
  assert.match(subject.captureUnavailableReason(), /excluded/i);
});

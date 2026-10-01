import { hasPermission, escapeHtml } from './ui.js';
import { sessionWorkspaceRoles } from './roles.js';

const BASE = '/api/v1/screen-shares';
const MAX_FRAME_BYTES = 524288;
const MAX_EDGE = 720;
const ELIGIBLE = Object.freeze({
  client: new Set(['client-overview', 'client-loans']),
  employee: new Set(['employee-overview', 'employee-operations']),
  collector: new Set(['collector-overview', 'collector-master-review', 'collector-route', 'collector-remittance']),
  management: new Set(['management-overview', 'management-loans', 'management-loan-operations']),
});
// Group navigation must not widen the previously audited capture surfaces.
const MANAGEMENT_CHILD = new Map([
  ['management-clients-loans', 'management-loans'],
  ['management-collections', 'management-loan-operations'],
]);
const SENSITIVE = 'input[type="password"], .one-time-client-credentials, [data-credential-result], [data-credential-own-form], [data-credential-reset-form], input[type="file"], dialog[open], [role="dialog"]';

export function isEligibleScreen(role, id) {
  return ELIGIBLE[role]?.has(id) === true;
}

export function viewerFrameIsNew(frame, generation, lastSequence) {
  return frame?.generation === generation && Number.isSafeInteger(frame.sequence) && frame.sequence > lastSequence;
}

export async function verifySelfCapture(track, { handle, origin, restrictionTarget }) {
  const chosen = track?.getCaptureHandle?.();
  if (track?.getSettings?.().displaySurface !== 'browser' || !chosen || chosen.handle !== handle || chosen.origin !== origin || typeof track.restrictTo !== 'function') {
    throw new Error('Choose this Spina browser tab. Other tabs, windows and screens are not allowed. If you are using the Windows app, open Spina in a supported browser.');
  }
  await track.restrictTo(restrictionTarget);
  return track;
}

export async function captureRestrictedFrame({ track, handle, origin, restrictionTarget, encode, upload }) {
  await verifySelfCapture(track, { handle, origin, restrictionTarget });
  const frame = await encode();
  await upload(frame);
}

export function createScreenShareLifecycle({ revoke = () => {} } = {}) {
  let epoch = 0;
  let stopped = false;
  let image = null;
  let imageAt = 0;
  function clearImage() { if (image) revoke(image); image = null; imageAt = 0; }
  return {
    generation: () => epoch,
    current: (value) => !stopped && value === epoch,
    navigate: () => { epoch += 1; },
    stop: () => { stopped = true; epoch += 1; clearImage(); },
    restart: () => { stopped = false; epoch += 1; clearImage(); },
    setViewerImage: (value, at) => { clearImage(); image = value; imageAt = at; },
    viewerImage: () => image,
    clearViewer: clearImage,
    clearStaleViewer: (now) => { if (!image || now - imageAt < 3000) return false; clearImage(); return true; },
  };
}

function visibleSensitive(section) {
  if (!section || section.hidden || section.closest?.('[hidden]')) return true;
  for (const item of section.querySelectorAll?.(SENSITIVE) || []) {
    if (!item.hidden && !item.closest?.('[hidden]') && (!item.getClientRects || item.getClientRects().length)) return true;
  }
  return false;
}

function frameBlob(video, doc) {
  if (!video.videoWidth || !video.videoHeight) throw new Error('The shared Spina screen has no visible frame.');
  const ratio = Math.min(1, MAX_EDGE / Math.max(video.videoWidth, video.videoHeight));
  const canvas = doc.createElement('canvas');
  canvas.width = Math.max(1, Math.round(video.videoWidth * ratio));
  canvas.height = Math.max(1, Math.round(video.videoHeight * ratio));
  canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve, reject) => canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error('Spina could not encode the shared frame.')), 'image/png'));
}

export class ScreenSharingController {
  constructor({ root, contentRoot, api, sessionStore, doc = globalThis.document, browser = globalThis.navigator, location = globalThis.location, now = Date.now }) {
    Object.assign(this, { root, contentRoot, api, sessionStore, doc, browser, location, now });
    this.disposed = true;
    this.session = null;
    this.role = null;
    this.sectionId = null;
    this.track = null;
    this.pendingTrack = null;
    this.restrictedElement = null;
    this.preparedTrack = null;
    this.preparedStream = null;
    this.preparedUntil = 0;
    this.pendingRequests = [];
    this.suppressedPending = new Map();
    this.captureToken = 0;
    this.captureInFlight = false;
    this.video = null;
    this.timers = new Set();
    this.listTimer = null;
    this.listInFlight = false;
    this.listAbort = null;
    this.mountEpoch = 0;
    this.requestInFlight = false;
    this.prepareInFlight = false;
    this.readyInFlight = false;
    this.readyItem = null;
    this.requestAbort = null;
    this.uploadAbort = null;
    this.controlAbort = new Set();
    this.lifecycle = createScreenShareLifecycle({ revoke: (url) => globalThis.URL?.revokeObjectURL?.(url) });
  }

  supported() {
    const secure = this.location?.protocol === 'https:' || (this.location?.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]', '::1'].includes(this.location.hostname));
    return Boolean(this.browser?.mediaDevices?.getDisplayMedia && this.browser.mediaDevices.setCaptureHandleConfig
      && globalThis.RestrictionTarget?.fromElement && secure && globalThis.isSecureContext !== false);
  }

  captureUnavailableReason() {
    if (this.prepareInFlight || this.readyInFlight) return 'This Spina tab is being prepared for live viewing.';
    if (this.preparedTrack) return 'Live view is ready for one Management request. Browser sharing controls remain available.';
    if (this.requestInFlight) return 'A screen request is being sent. Cancel it before enabling this tab.';
    if (this.session) return 'This device already has a screen request or active share. Stop it before enabling this tab again.';
    if (this.browser?.onLine === false) return 'Reconnect to Spina before sharing this screen.';
    if (!this.supported() || !this.handle) return 'This browser cannot safely share only this Spina tab. Open Spina in a supported browser to start sharing. Viewing remains available.';
    if (!isEligibleScreen(this.role, this.captureSectionId())) return 'This screen is excluded from sharing. Open an eligible daily-work screen before enabling.';
    if (!this.safeToCapture()) return 'This screen contains private controls or is not visible. Close them before sharing.';
    return '';
  }

  updateCaptureAvailability() {
    const reason = this.captureUnavailableReason();
    const message = this.root.querySelector('[data-screen-unavailable]');
    if (message) { message.textContent = reason; message.hidden = !reason; }
    const button = this.root.querySelector('[data-screen-prepare]');
    if (button) button.disabled = Boolean(reason);
  }

  later(action, delay) {
    const timer = setTimeout(() => { this.timers.delete(timer); action(); }, delay);
    this.timers.add(timer);
    return timer;
  }

  async controlRequest(path, options = {}) {
    const abort = new AbortController();
    this.controlAbort.add(abort);
    let deadline;
    try {
      return await Promise.race([
        this.api.request(path, { ...options, signal: abort.signal }),
        new Promise((_, reject) => { deadline = setTimeout(() => { abort.abort(); reject(new Error('Screen sharing did not respond. Check again before retrying.')); }, 10000); }),
      ]);
    } finally {
      clearTimeout(deadline);
      this.controlAbort.delete(abort);
    }
  }

  captureSectionId(id = this.sectionId) {
    return this.role === 'management' ? MANAGEMENT_CHILD.get(id) || id : id;
  }

  activeSection() {
    const group = [...this.contentRoot.querySelectorAll('[data-workspace-section]')].find((item) => item.getAttribute('id') === this.sectionId && !item.hidden);
    const childId = this.captureSectionId();
    if (!group || childId === this.sectionId) return group;
    const children = [...group.querySelectorAll('[data-screen-share-section]')].filter((item) => item.getAttribute('id') === childId);
    return children.length === 1 ? children[0] : null;
  }

  captureElement() {
    return this.captureSectionId() === this.sectionId ? this.contentRoot : this.activeSection();
  }

  safeToCapture() {
    return isEligibleScreen(this.role, this.captureSectionId())
      && (!this.restrictedElement || this.restrictedElement === this.captureElement())
      && !visibleSensitive(this.activeSection())
      && !this.doc.hidden && this.browser?.onLine !== false;
  }

  pendingKey(item) {
    return `${item?.id || ''}:${item?.generation || ''}`;
  }

  suppressPending(item) {
    if (!item?.id || !Number.isSafeInteger(item.generation)) return;
    this.pruneSuppressed();
    const expires = Date.parse(item.expires_at);
    this.suppressedPending.set(this.pendingKey(item), Number.isFinite(expires) ? Math.min(expires, this.now() + 600000) : this.now() + 60000);
  }

  pruneSuppressed() {
    for (const [key, expires] of this.suppressedPending) if (expires <= this.now()) this.suppressedPending.delete(key);
  }

  validPending(item) {
    this.pruneSuppressed();
    return item?.state === 'pending'
      && /^[a-f0-9-]{36}$/i.test(item.id || '')
      && Number.isSafeInteger(item.generation) && item.generation > 0
      && item.holder_user_id === this.account?.user?.id
      && Date.parse(item.expires_at) > this.now()
      && !this.suppressedPending.has(this.pendingKey(item));
  }

  async apiFrameGet(id) {
    const session = this.sessionStore.load();
    if (!session) throw new Error('Your session ended.');
    const response = await this.api.fetchImpl(`${this.api.apiBaseUrl}${BASE}/${encodeURIComponent(id)}/frame`, {
      method: 'GET', cache: 'no-store', signal: this.requestAbort?.signal,
      headers: { Authorization: `Bearer ${session.access_token}`, 'X-Device-Id': this.sessionStore.deviceId(), 'X-App-Platform': 'web', 'X-App-Version': this.api.appVersion },
    });
    if (!/\bno-store\b/i.test(response.headers.get('Cache-Control') || '')) throw new Error('Screen image caching protection is missing.');
    if (response.status === 204) return null;
    if (response.status !== 200) throw new Error('Screen viewing ended or is no longer allowed.');
    const generation = Number(response.headers.get('X-Screen-Share-Generation'));
    const sequence = Number(response.headers.get('X-Screen-Share-Sequence'));
    if (!Number.isSafeInteger(generation) || !Number.isSafeInteger(sequence) || sequence < 1) throw new Error('Screen frame metadata is incomplete.');
    if (Number(response.headers.get('Content-Length')) > MAX_FRAME_BYTES) throw new Error('Screen image is too large.');
    let blob;
    if (response.body?.getReader) {
      const reader = response.body.getReader();
      const chunks = [];
      let bytes = 0;
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          bytes += value.byteLength;
          if (bytes > MAX_FRAME_BYTES) throw new Error('Screen image is too large.');
          chunks.push(value);
        }
      } catch (error) { await reader.cancel().catch(() => {}); throw error; }
      blob = new Blob(chunks, { type: response.headers.get('Content-Type') || '' });
    } else blob = await response.blob();
    if (blob.type !== 'image/png' || blob.size > MAX_FRAME_BYTES) throw new Error('Screen frame format is invalid.');
    return { generation, sequence, blob };
  }

  stopLocal() {
    this.lifecycle.stop();
    this.requestAbort?.abort();
    this.requestAbort = null;
    this.listAbort?.abort();
    this.listAbort = null;
    for (const abort of this.controlAbort) abort.abort();
    this.controlAbort.clear();
    this.listInFlight = false;
    this.listRefreshNeeded = false;
    this.requestInFlight = false;
    this.prepareInFlight = false;
    this.readyInFlight = false;
    this.readyItem = null;
    this.uploadAbort?.abort();
    this.uploadAbort = null;
    this.captureToken += 1;
    this.captureInFlight = false;
    this.nextFrameAt = 0;
    this.sequence = 0;
    for (const timer of this.timers) clearTimeout(timer);
    this.timers.clear();
    this.listTimer = null;
    this.viewerPolling = false;
    this.lastViewerSequence = 0;
    const track = this.track;
    this.track = null;
    track?.stop();
    const pendingTrack = this.pendingTrack;
    this.pendingTrack = null;
    this.restrictedElement = null;
    if (pendingTrack !== track) pendingTrack?.stop();
    const preparedTrack = this.preparedTrack;
    this.preparedTrack = null;
    if (preparedTrack !== track && preparedTrack !== pendingTrack) preparedTrack?.stop();
    this.preparedStream = null;
    this.preparedUntil = 0;
    this.pendingRequests = [];
    if (this.video) { this.video.pause(); this.video.srcObject = null; this.video.remove(); }
    this.video = null;
    const img = this.root.querySelector('[data-screen-view-image]');
    if (img) { img.removeAttribute('src'); img.hidden = true; }
    this.root.querySelector('[data-screen-stop]')?.setAttribute('hidden', '');
  }

  async stop({ notify = true, reason = '' } = {}) {
    const active = this.session;
    const requestWasPending = this.requestInFlight;
    for (const pending of this.pendingRequests) this.suppressPending(pending);
    this.suppressPending(this.readyItem);
    if (active) this.suppressPending(active);
    this.stopLocal();
    if (!this.disposed) this.lifecycle.restart();
    this.session = null;
    this.participantMode = null;
    this.render(reason || (requestWasPending ? 'Request canceled here. If it reached the server, it expires within a minute.' : ''));
    if (notify && active && ['pending', 'active'].includes(active.state)) {
      try { await this.controlRequest(`${BASE}/${encodeURIComponent(active.id)}/stop`, { method: 'POST', body: { generation: active.generation } }); }
      catch { /* Local capture and stale pixels are already stopped. */ }
    }
    if (!this.disposed && !this.doc.hidden) void this.refreshLists();
  }

  beforeNavigate(id) {
    this.lifecycle.navigate();
    this.lifecycle.clearViewer();
    const image = this.root.querySelector('[data-screen-view-image]');
    if (image) { image.removeAttribute('src'); image.hidden = true; }
    this.sectionId = id;
    if (!this.session) this.listRefreshNeeded = true;
    if (this.preparedTrack || this.prepareInFlight || this.readyInFlight) { void this.stop({ reason: 'Live view setup stopped because the Spina screen changed. Enable this tab again when ready.' }); return; }
    if (this.track && (!isEligibleScreen(this.role, this.captureSectionId(id))
      || this.restrictedElement && this.restrictedElement !== this.captureElement())) {
      void this.stop({ reason: 'Sharing stopped because the captured work panel changed. Enable this tab again when ready.' }); return;
    }
    if (this.track) {
      this.uploadAbort?.abort();
      this.queueCapture(0);
    } else if (this.session?.state === 'active' && this.participantMode === 'viewer') {
      this.requestAbort?.abort();
      this.viewerPolling = true;
      this.later(() => void this.pollFrame(this.session?.id), 0);
    } else if (this.session?.state === 'pending') {
      this.later(() => void this.pollSession(this.session?.id), 0);
    }
  }

  afterNavigate() {
    if ((this.track || this.preparedTrack || this.prepareInFlight || this.readyInFlight) && !this.safeToCapture()) void this.stop({ reason: 'Sharing stopped because this screen contains private controls or is hidden.' });
    this.updateCaptureAvailability();
    if (!this.session && !this.listInFlight) void this.refreshLists();
  }

  observeContent() {
    this.observer?.disconnect();
    if (!globalThis.MutationObserver) return;
    this.observer = new MutationObserver(() => {
      if ((this.track || this.preparedTrack || this.prepareInFlight || this.readyInFlight) && !this.safeToCapture()) void this.stop({ reason: 'Sharing stopped because a private control appeared.' });
    });
    this.observer.observe(this.contentRoot, { childList: true, subtree: true, attributes: true, attributeFilter: ['hidden', 'type', 'open', 'id', 'data-screen-share-section'] });
  }

  mount({ session, role }) {
    this.dispose();
    this.mountEpoch += 1;
    this.disposed = false;
    this.session = null;
    this.participantMode = null;
    this.role = role;
    this.account = session;
    // Preserve the epoch across account and role remounts so an old response can never look current.
    this.lifecycle.restart();
    this.sequence = 0;
    this.lastViewerSequence = 0;
    this.viewerPolling = false;
    this.pendingRequests = [];
    this.handle = globalThis.crypto?.randomUUID?.();
    if (this.supported() && this.handle) {
      try { this.browser.mediaDevices.setCaptureHandleConfig({ handle: this.handle, exposeOrigin: true, permittedOrigins: [this.location.origin] }); }
      catch { this.handle = null; }
    }
    this.render();
    this.observeContent();
    this.doc.addEventListener('visibilitychange', this.onVisibility = () => {
      if (this.doc.hidden) void this.stop();
      else void this.refreshLists();
    });
    this.refreshLists();
  }

  dispose() {
    if (this.disposed) return;
    this.mountEpoch += 1;
    this.disposed = true;
    this.observer?.disconnect();
    this.doc?.removeEventListener('visibilitychange', this.onVisibility);
    void this.stop();
    this.root.replaceChildren();
  }

  render(message = '') {
    if (this.disposed) return;
    const panelWasOpen = this.root.querySelector('[data-screen-panel]')?.open === true;
    const canView = sessionWorkspaceRoles(this.account).includes('management') && hasPermission(this.account, 'screen_share.view');
    const active = this.session;
    const status = message ? `<p role="status">${escapeHtml(message)}</p>` : '';
    const unavailable = this.captureUnavailableReason();
    const holderName = active?.viewer_name || 'Management';
    const banner = active?.state === 'active'
      ? this.participantMode === 'holder' ? `Management ${escapeHtml(holderName)} is viewing` : `Viewing ${escapeHtml(active.holder_name || 'the selected account')}`
      : this.readyInFlight ? 'Connecting live view' : this.preparedTrack ? 'Live view ready' : this.prepareInFlight ? 'Preparing this Spina tab' : this.requestInFlight ? 'Sending screen request' : active?.state === 'pending' ? 'Screen request pending' : '';
    const viewerCanStop = (active && this.participantMode === 'viewer') || this.requestInFlight;
    this.root.innerHTML = `${banner ? `<div class="screen-share-active" role="status"><strong>${banner}</strong>${viewerCanStop ? `<button type="button" data-screen-stop>${this.requestInFlight ? 'Cancel request' : 'Stop viewing'}</button>` : ''}</div>` : ''}<details data-screen-panel><summary>Live screen view${active?.state === 'pending' ? ' · request pending' : ''}</summary><div class="screen-share-panel">
      <p>Enable only this Spina browser tab. Management can then view an eligible work screen. A visible status shows when viewing is active. The browser keeps its own sharing controls. No remote control or recording.</p>${status}<p data-screen-unavailable ${unavailable ? '' : 'hidden'}>${escapeHtml(unavailable)}</p>
      <button type="button" data-screen-prepare ${unavailable ? 'disabled' : ''}>Enable this Spina tab</button>
      ${canView ? `<div data-screen-request><label>Request a screen<select data-screen-target><option value="">Choose an account and device</option></select></label><button type="button" data-screen-request-button ${this.requestInFlight || this.prepareInFlight || this.readyInFlight || this.preparedTrack || active ? 'disabled' : ''}>Request view</button></div>` : ''}
      <button type="button" data-screen-check>Check requests now</button>
      <div data-screen-pending></div>
      ${active ? `<p data-screen-session-status>${escapeHtml(active.state === 'active' ? `Live view with ${this.participantMode === 'viewer' ? active.holder_name : active.viewer_name}` : `Request ${active.state}`)}</p>` : ''}
      ${active?.state === 'active' && this.participantMode === 'viewer' ? '<img data-screen-view-image alt="Live Spina screen" hidden />' : ''}
    </div></details>`;
    this.root.querySelector('[data-screen-panel]').open = panelWasOpen || Boolean(banner);
    this.root.querySelector('[data-screen-prepare]')?.addEventListener('click', () => void this.prepare());
    this.root.querySelector('[data-screen-request-button]')?.addEventListener('click', () => void this.request());
    for (const button of this.root.querySelectorAll('[data-screen-stop]')) button.addEventListener('click', () => void this.stop());
    this.root.querySelector('[data-screen-check]')?.addEventListener('click', () => void this.refreshLists());
  }

  async refreshLists() {
    if (this.disposed || this.doc.hidden || this.listInFlight) return;
    if (this.listTimer) { clearTimeout(this.listTimer); this.timers.delete(this.listTimer); this.listTimer = null; }
    this.listInFlight = true;
    this.listRefreshNeeded = false;
    const epoch = this.lifecycle.generation();
    const mountEpoch = this.mountEpoch;
    const abort = new AbortController();
    this.listAbort = abort;
    const timeout = setTimeout(() => abort.abort(), 10000);
    const canView = sessionWorkspaceRoles(this.account).includes('management') && hasPermission(this.account, 'screen_share.view');
    try {
      const [pending, targets] = await Promise.all([
        this.api.request(`${BASE}/pending`, { signal: abort.signal }),
        canView ? this.api.request(`${BASE}/targets`, { signal: abort.signal }) : Promise.resolve({ targets: [] }),
      ]);
      if (this.disposed || this.mountEpoch !== mountEpoch || !this.lifecycle.current(epoch)) return;
      const select = this.root.querySelector('[data-screen-target]');
      if (select) {
        this.targets = Array.isArray(targets?.targets) ? targets.targets : [];
        select.innerHTML = '<option value="">Choose an account and device</option>' + this.targets.map((target, index) => `<option value="${index}">${escapeHtml(target.display_name)} · ${escapeHtml(target.device_name)}</option>`).join('');
      }
      const pendingRoot = this.root.querySelector('[data-screen-pending]');
      const items = Array.isArray(pending?.sessions) ? pending.sessions.filter(item => this.validPending(item)) : [];
      this.pendingRequests = items;
      if (pendingRoot) {
        pendingRoot.innerHTML = items.map(item => `<div class="notice-card"><strong>Management ${escapeHtml(item.viewer_name || '')}</strong> requested live view. ${this.preparedTrack ? 'Connecting this enabled tab.' : 'Enable this Spina tab when it is safe to share.'}</div>`).join('');
      }
      if (this.preparedTrack && !this.readyInFlight && !this.session && items[0]) void this.ready(items[0]);
    } catch { /* A private status failure is shown on the next explicit action. */ }
    finally {
      clearTimeout(timeout);
      if (this.mountEpoch !== mountEpoch || this.listAbort !== abort) return;
      this.listAbort = null;
      this.listInFlight = false;
      if (this.listRefreshNeeded) {
        this.listRefreshNeeded = false;
        if (!this.disposed && !this.doc.hidden) { void this.refreshLists(); return; }
      }
      if (!this.disposed && !this.doc.hidden) {
        this.listTimer = setTimeout(() => { this.timers.delete(this.listTimer); this.listTimer = null; void this.refreshLists(); }, 15000);
        this.timers.add(this.listTimer);
      }
    }
  }

  async request() {
    if (this.requestInFlight || this.prepareInFlight || this.readyInFlight || this.preparedTrack || this.disposed || this.session) return;
    const select = this.root.querySelector('[data-screen-target]');
    const target = this.targets?.[Number(select?.value)];
    if (!select?.value || !target) return;
    const epoch = this.lifecycle.generation();
    this.requestInFlight = true;
    this.render();
    try {
      const session = await this.controlRequest(BASE, { method: 'POST', body: { holder_user_id: target.user_id, holder_device_id: target.device_id } });
      if (this.disposed || !this.lifecycle.current(epoch)) { await this.bestEffortStop(session); return; }
      this.requestInFlight = false;
      this.lifecycle.restart();
      this.session = session;
      this.participantMode = 'viewer';
      this.render();
      this.pollSession(session.id);
    } catch (error) {
      if (!this.disposed && this.lifecycle.current(epoch)) {
        this.requestInFlight = false;
        this.render(error.message);
      }
    }
    finally {
      if (!this.disposed && this.lifecycle.current(epoch)) {
        this.requestInFlight = false;
        const current = this.root.querySelector('[data-screen-request-button]');
        if (current) current.disabled = false;
      }
    }
  }

  async bestEffortStop(session) {
    if (!session?.id || !Number.isSafeInteger(session.generation)) return;
    try { await this.controlRequest(`${BASE}/${encodeURIComponent(session.id)}/stop`, { method: 'POST', body: { generation: session.generation } }); }
    catch { /* Expiry or revocation will also terminate this bounded grant. */ }
  }

  async pollSession(id) {
    if (this.disposed || this.session?.id !== id) return;
    const epoch = this.lifecycle.generation();
    try {
      const session = await this.controlRequest(`${BASE}/${encodeURIComponent(id)}`);
      if (this.disposed || this.session?.id !== id || !this.lifecycle.current(epoch)) return;
      if (!['pending', 'active'].includes(session.state) || session.generation !== this.session.generation && this.session.state === 'active') { await this.stop({ notify: false }); return; }
      if (session.state !== this.session.state) { this.session = session; this.render(); }
      if (session.state === 'active' && this.participantMode === 'viewer' && !this.viewerPolling) {
        this.viewerPolling = true;
        this.pollFrame(id);
      }
    } catch {
      if (!this.disposed && this.session?.id === id && this.lifecycle.current(epoch)) await this.stop({ notify: false });
      return;
    }
    if (!this.disposed && this.session?.id === id && this.session.state === 'pending') this.later(() => void this.pollSession(id), 2000);
  }

  async pollFrame(id) {
    if (this.disposed || this.session?.id !== id || this.session.state !== 'active') return;
    const epoch = this.lifecycle.generation();
    const abort = new AbortController();
    this.requestAbort = abort;
    const deadline = this.later(() => abort.abort(), 5000);
    try {
      const frame = await this.apiFrameGet(id);
      if (this.disposed || this.session?.id !== id || !this.lifecycle.current(epoch)) return;
      if (frame && frame.generation !== this.session.generation) throw new Error('Screen frame generation changed.');
      if (viewerFrameIsNew(frame, this.session.generation, this.lastViewerSequence)) {
        this.lastViewerSequence = frame.sequence;
        const url = URL.createObjectURL(frame.blob);
        this.lifecycle.setViewerImage(url, this.now());
        const image = this.root.querySelector('[data-screen-view-image]');
        if (image) { image.src = url; image.hidden = false; }
        this.later(() => {
          if (!this.disposed && this.lifecycle.clearStaleViewer(this.now())) {
            const current = this.root.querySelector('[data-screen-view-image]');
            if (current) { current.removeAttribute('src'); current.hidden = true; }
          }
        }, 3000);
      }
      if (this.lifecycle.clearStaleViewer(this.now())) {
        const image = this.root.querySelector('[data-screen-view-image]');
        if (image) { image.removeAttribute('src'); image.hidden = true; }
      }
    } catch { if (!this.disposed && this.session?.id === id && this.lifecycle.current(epoch)) await this.stop({ notify: false }); return; }
    finally {
      clearTimeout(deadline);
      this.timers.delete(deadline);
      if (this.requestAbort === abort) this.requestAbort = null;
    }
    if (!this.disposed && this.session?.id === id) this.later(() => void this.pollFrame(id), 1000);
  }

  async prepare() {
    if (this.disposed || this.track || this.preparedTrack || this.prepareInFlight || this.readyInFlight || this.session || this.requestInFlight || !this.safeToCapture() || !this.supported() || !this.handle) return;
    const epoch = this.lifecycle.generation();
    this.prepareInFlight = true;
    this.render();
    let stream;
    try {
      // The browser chooser must be invoked by this explicit button gesture.
      stream = await this.browser.mediaDevices.getDisplayMedia({ video: { displaySurface: 'browser', frameRate: 1 }, audio: false, preferCurrentTab: true, selfBrowserSurface: 'include', monitorTypeSurfaces: 'exclude', surfaceSwitching: 'exclude', systemAudio: 'exclude' });
      const track = stream.getVideoTracks()[0];
      if (!track || !this.lifecycle.current(epoch) || !this.safeToCapture()) throw new Error('Live view setup was cancelled.');
      this.pendingTrack = track;
      const captureElement = this.captureElement();
      const target = await RestrictionTarget.fromElement(captureElement);
      await verifySelfCapture(track, { handle: this.handle, origin: this.location.origin, restrictionTarget: target });
      if (!this.lifecycle.current(epoch) || !this.safeToCapture() || captureElement !== this.captureElement()) throw new Error('Live view setup was cancelled.');
      this.restrictedElement = captureElement;
      this.preparedTrack = track;
      this.preparedStream = stream;
      this.pendingTrack = null;
      this.preparedUntil = this.now() + 600000;
      this.prepareInFlight = false;
      track.addEventListener('ended', () => { if (this.preparedTrack === track || this.track === track) void this.stop({ reason: 'Browser screen sharing ended. Enable this tab again if needed.' }); }, { once: true });
      track.addEventListener?.('capturehandlechange', () => { if ((this.preparedTrack === track || this.track === track) && !this.selfCaptureStillValid(track)) void this.stop({ reason: 'The selected browser tab changed. Enable this tab again if needed.' }); });
      this.later(() => { if (this.preparedTrack === track || this.track === track) void this.stop({ reason: 'Live view setup expired. Enable this tab again if needed.' }); }, 600000);
      this.render();
      if (this.listInFlight) this.listRefreshNeeded = true;
      else void this.refreshLists();
    } catch (error) {
      stream?.getTracks().forEach(track => track.stop());
      if (!this.disposed && this.lifecycle.current(epoch)) {
        await this.stop({ notify: false });
        this.render(['NotSupportedError', 'SecurityError', 'TypeError'].includes(error?.name)
          ? 'This window cannot safely share only the Spina tab. Open Spina in a supported browser to enable it.'
          : error.message);
      }
    } finally {
      if (this.pendingTrack && stream?.getVideoTracks?.().includes(this.pendingTrack)) this.pendingTrack = null;
      if (this.disposed || !this.lifecycle.current(epoch)) stream?.getTracks().forEach(track => track.stop());
    }
  }

  async ready(item) {
    if (this.disposed || this.readyInFlight || this.session || !this.preparedTrack || !this.validPending(item)) return;
    if (this.now() >= this.preparedUntil || !this.safeToCapture() || !this.selfCaptureStillValid(this.preparedTrack)) {
      await this.stop({ reason: 'Live view setup ended. Enable this tab again if needed.' });
      return;
    }
    const epoch = this.lifecycle.generation();
    const track = this.preparedTrack;
    const stream = this.preparedStream;
    this.readyInFlight = true;
    this.readyItem = item;
    this.render();
    let active;
    try {
      // Restriction completed during explicit setup. No image is encoded or sent yet.
      active = await this.controlRequest(`${BASE}/${encodeURIComponent(item.id)}/ready`, { method: 'POST', body: { generation: item.generation } });
      if (this.disposed || !this.lifecycle.current(epoch) || this.preparedTrack !== track || !this.safeToCapture() || !this.selfCaptureStillValid(track)) {
        await this.bestEffortStop(active);
        return;
      }
      if (active?.id !== item.id || active?.generation !== item.generation || active?.state !== 'active') throw new Error('Live view request is no longer active.');
      this.session = active;
      this.participantMode = 'holder';
      this.track = track;
      this.preparedTrack = null;
      this.preparedStream = null;
      this.video = this.doc.createElement('video');
      this.video.muted = true;
      this.video.playsInline = true;
      this.video.srcObject = stream;
      await this.video.play();
      if (!this.lifecycle.current(epoch) || !this.safeToCapture() || !this.selfCaptureStillValid()) throw new Error('Live view setup ended.');
      this.readyInFlight = false;
      this.readyItem = null;
      this.render(); // Paint the named status before the first encoded frame.
      await new Promise((resolve, reject) => {
        const raf = this.doc.defaultView?.requestAnimationFrame?.bind(this.doc.defaultView);
        if (!raf) { reject(new Error('The live view status cannot be displayed safely.')); return; }
        const deadline = setTimeout(() => reject(new Error('The live view status could not be displayed.')), 1000);
        raf(() => raf(() => { clearTimeout(deadline); resolve(); }));
      });
      if (!this.lifecycle.current(epoch) || this.session?.id !== item.id || !this.safeToCapture() || !this.selfCaptureStillValid()) throw new Error('Live view setup ended.');
      this.queueCapture(0);
    } catch (error) {
      this.suppressPending(item);
      await this.bestEffortStop(active || item);
      if (!this.disposed && this.lifecycle.current(epoch)) await this.stop({ notify: false, reason: 'Live view could not start. Enable this tab again for a new request.' });
    }
  }

  async sendFrame(id) {
    if (this.disposed || !this.track || this.session?.id !== id || this.captureInFlight) return;
    this.captureInFlight = true;
    const captureToken = ++this.captureToken;
    const epoch = this.lifecycle.generation();
    const generation = this.session.generation;
    let attemptedUpload = false;
    try {
      if (!this.safeToCapture() || !this.selfCaptureStillValid()) { await this.stop({ reason: 'Sharing stopped because the selected tab or visible screen changed.' }); return; }
      const blob = await frameBlob(this.video, this.doc);
      if (!this.lifecycle.current(epoch) || this.session?.id !== id || !this.safeToCapture() || !this.selfCaptureStillValid()) return;
      if (blob.size <= MAX_FRAME_BYTES) {
        this.sequence = (this.sequence || 0) + 1;
        const abort = new AbortController();
        this.uploadAbort = abort;
        attemptedUpload = true;
        let deadline;
        try {
          await Promise.race([
            this.api.request(`${BASE}/${encodeURIComponent(id)}/frame`, { method: 'PUT', rawBody: blob, signal: abort.signal, headers: { 'Content-Type': 'image/png', 'X-Screen-Share-Generation': String(this.session.generation), 'X-Screen-Share-Sequence': String(this.sequence) } }),
            new Promise((_, reject) => { deadline = setTimeout(() => { abort.abort(); reject(new Error('Screen upload timed out.')); }, 5000); }),
          ]);
        } finally {
          clearTimeout(deadline);
          if (this.uploadAbort === abort) this.uploadAbort = null;
        }
      }
      if (!this.lifecycle.current(epoch) || this.session?.id !== id) return;
      this.queueCapture(1000);
    } catch { if (!this.disposed && this.lifecycle.current(epoch)) await this.stop(); }
    finally {
      if (attemptedUpload && this.session?.id === id && this.session.generation === generation) this.nextFrameAt = Math.max(this.nextFrameAt || 0, this.now() + 1100);
      if (this.captureToken !== captureToken) return;
      this.captureInFlight = false;
      if (!this.disposed && this.track && this.session?.id === id && !this.lifecycle.current(epoch)) this.queueCapture(0);
    }
  }

  queueCapture(delay) {
    if (!this.track || this.disposed) return;
    if (this.captureTimer) { clearTimeout(this.captureTimer); this.timers.delete(this.captureTimer); }
    const remaining = Math.max(0, (this.nextFrameAt || 0) - this.now());
    this.captureTimer = setTimeout(() => {
      this.timers.delete(this.captureTimer);
      this.captureTimer = null;
      if (this.captureInFlight) { this.queueCapture(100); return; }
      void this.sendFrame(this.session?.id);
    }, Math.max(delay, remaining));
    this.timers.add(this.captureTimer);
  }

  selfCaptureStillValid(track = this.track) {
    const chosen = track?.getCaptureHandle?.();
    return track?.getSettings?.().displaySurface === 'browser' && chosen?.handle === this.handle && chosen?.origin === this.location.origin;
  }
}

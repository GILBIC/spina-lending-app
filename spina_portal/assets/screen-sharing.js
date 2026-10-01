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
    this.captureToken = 0;
    this.captureInFlight = false;
    this.video = null;
    this.timers = new Set();
    this.listTimer = null;
    this.listInFlight = false;
    this.listAbort = null;
    this.mountEpoch = 0;
    this.requestInFlight = false;
    this.acceptInFlight = false;
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
    if (this.acceptInFlight) return 'Screen sharing is being prepared. Stop it before accepting another request.';
    if (this.requestInFlight) return 'A screen request is being sent. Cancel it before accepting another.';
    if (this.session) return 'This device already has a screen request or active share. Stop it before accepting another.';
    if (this.browser?.onLine === false) return 'Reconnect to Spina before sharing this screen.';
    if (!this.supported() || !this.handle) return 'This browser cannot safely share only this Spina tab. Open Spina in a supported browser to start sharing. Viewing remains available.';
    if (!isEligibleScreen(this.role, this.sectionId)) return 'This screen is excluded from sharing. Open an eligible daily-work screen before accepting.';
    if (!this.safeToCapture()) return 'This screen contains private controls or is not visible. Close them before sharing.';
    return '';
  }

  updateCaptureAvailability() {
    const reason = this.captureUnavailableReason();
    const message = this.root.querySelector('[data-screen-unavailable]');
    if (message) { message.textContent = reason; message.hidden = !reason; }
    for (const button of this.root.querySelectorAll('[data-screen-accept]')) button.disabled = Boolean(reason || this.acceptInFlight);
    for (const message of this.root.querySelectorAll('[data-screen-accept-reason]')) {
      message.textContent = reason;
      message.hidden = !reason;
    }
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

  activeSection() {
    return [...this.contentRoot.querySelectorAll('[data-workspace-section]')].find((item) => item.getAttribute('id') === this.sectionId && !item.hidden);
  }

  safeToCapture() {
    return isEligibleScreen(this.role, this.sectionId) && !visibleSensitive(this.activeSection()) && !this.doc.hidden && this.browser?.onLine !== false;
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
    this.acceptInFlight = false;
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
    if (pendingTrack !== track) pendingTrack?.stop();
    if (this.video) { this.video.pause(); this.video.srcObject = null; this.video.remove(); }
    this.video = null;
    const img = this.root.querySelector('[data-screen-view-image]');
    if (img) { img.removeAttribute('src'); img.hidden = true; }
    this.root.querySelector('[data-screen-stop]')?.setAttribute('hidden', '');
  }

  async stop({ notify = true, reason = '' } = {}) {
    const active = this.session;
    const requestWasPending = this.requestInFlight;
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
    if (this.track && !isEligibleScreen(this.role, id)) { void this.stop({ reason: 'Sharing stopped because this screen is excluded.' }); return; }
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
    if (this.track && !this.safeToCapture()) void this.stop({ reason: 'Sharing stopped because this screen contains private controls or is hidden.' });
    this.updateCaptureAvailability();
    if (!this.session && !this.listInFlight) void this.refreshLists();
  }

  observeContent() {
    this.observer?.disconnect();
    if (!globalThis.MutationObserver) return;
    this.observer = new MutationObserver(() => {
      if (this.track && !this.safeToCapture()) void this.stop({ reason: 'Sharing stopped because a private control appeared.' });
    });
    this.observer.observe(this.contentRoot, { childList: true, subtree: true, attributes: true, attributeFilter: ['hidden', 'type', 'open'] });
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
    this.root.innerHTML = `${active?.state === 'active' || this.acceptInFlight || this.requestInFlight ? `<div class="screen-share-active" role="status"><strong>${active?.state === 'active' ? 'Screen sharing is active' : this.acceptInFlight ? 'Preparing screen sharing' : 'Sending screen request'}</strong><button type="button" data-screen-stop>${this.requestInFlight ? 'Cancel request' : 'Stop sharing'}</button></div>` : ''}<details data-screen-panel><summary>Screen sharing${active?.state === 'pending' ? ' · request pending' : ''}</summary><div class="screen-share-panel">
      <p>Viewing requires the other person's approval. Sharing shows only selected Spina work, with no control or recording.</p>${status}<p data-screen-unavailable ${unavailable ? '' : 'hidden'}>${escapeHtml(unavailable)}</p>
      ${canView ? `<div data-screen-request><label>Request a screen<select data-screen-target><option value="">Choose an account and device</option></select></label><button type="button" data-screen-request-button ${this.requestInFlight ? 'disabled' : ''}>Request view</button></div>` : ''}
      <button type="button" data-screen-check>Check requests now</button>
      <div data-screen-pending></div>
      ${active ? `<p data-screen-session-status>${escapeHtml(active.state === 'active' ? `Sharing with ${this.participantMode === 'viewer' ? active.holder_name : active.viewer_name}` : `Request ${active.state}`)}</p>` : ''}
      ${active?.state === 'active' && this.participantMode === 'viewer' ? '<img data-screen-view-image alt="Consented live Spina screen" hidden />' : ''}
      ${active?.state === 'pending' ? '<button type="button" data-screen-stop>Cancel request</button>' : ''}
    </div></details>`;
    this.root.querySelector('[data-screen-panel]').open = panelWasOpen || active?.state === 'active' || this.requestInFlight || this.acceptInFlight;
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
      if (pendingRoot) {
        const items = Array.isArray(pending?.sessions) ? pending.sessions : [];
        const unavailable = this.captureUnavailableReason();
        pendingRoot.innerHTML = items.map((item, index) => `<div class="notice-card"><strong>${escapeHtml(item.viewer_name || 'Management')}</strong> wants to view this Spina screen. <button type="button" data-screen-accept="${index}" ${unavailable || this.acceptInFlight ? 'disabled' : ''}>Accept and share this tab</button> <button type="button" data-screen-decline="${index}">Decline</button><p data-screen-accept-reason ${unavailable ? '' : 'hidden'}>${escapeHtml(unavailable)}</p></div>`).join('');
        for (const button of pendingRoot.querySelectorAll('[data-screen-accept]')) button.addEventListener('click', () => void this.acceptAndShare(items[Number(button.dataset.screenAccept)]));
        for (const button of pendingRoot.querySelectorAll('[data-screen-decline]')) button.addEventListener('click', () => void this.consent(items[Number(button.dataset.screenDecline)], 'decline'));
      }
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
    if (this.requestInFlight || this.acceptInFlight || this.disposed || this.session) return;
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

  async consent(item, action = 'decline') {
    if (!item || this.disposed || action !== 'decline') return;
    const epoch = this.lifecycle.generation();
    try {
      const session = await this.controlRequest(`${BASE}/${encodeURIComponent(item.id)}/${action}`, { method: 'POST', body: { generation: item.generation } });
      if (this.disposed || !this.lifecycle.current(epoch)) return;
      this.render(session.state === 'declined' ? 'Request declined.' : 'Request is no longer available.');
      void this.refreshLists();
    } catch (error) { if (!this.disposed && this.lifecycle.current(epoch)) this.render(error.message); }
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

  async acceptAndShare(item) {
    if (this.disposed || this.track || this.session || this.requestInFlight || this.acceptInFlight || !item || !this.safeToCapture() || !this.supported() || !this.handle) return;
    const epoch = this.lifecycle.generation();
    this.acceptInFlight = true;
    this.render();
    let stream;
    let accepted;
    try {
      // Must run directly in this click handler. No request or timer may consume the user gesture first.
      stream = await this.browser.mediaDevices.getDisplayMedia({ video: { displaySurface: 'browser', frameRate: 1 }, audio: false, preferCurrentTab: true, selfBrowserSurface: 'include', monitorTypeSurfaces: 'exclude', surfaceSwitching: 'exclude', systemAudio: 'exclude' });
      const track = stream.getVideoTracks()[0];
      if (!track || !this.lifecycle.current(epoch) || !this.safeToCapture()) throw new Error('Screen sharing was cancelled.');
      this.pendingTrack = track;
      const target = await RestrictionTarget.fromElement(this.contentRoot);
      await verifySelfCapture(track, { handle: this.handle, origin: this.location.origin, restrictionTarget: target });
      if (!this.lifecycle.current(epoch) || !this.safeToCapture()) throw new Error('Screen sharing was cancelled.');
      // The holder accepts only after restricting the chosen self-tab. No pixels leave before this response.
      accepted = await this.controlRequest(`${BASE}/${encodeURIComponent(item.id)}/accept`, { method: 'POST', body: { generation: item.generation } });
      if (this.disposed || !this.lifecycle.current(epoch) || !this.safeToCapture()) { await this.bestEffortStop(accepted); return; }
      if (accepted?.state !== 'active') throw new Error('This request is no longer active.');
      this.session = accepted;
      this.participantMode = 'holder';
      this.track = track;
      this.pendingTrack = null;
      const ownsCapture = () => this.track === track && this.session?.id === accepted.id && this.session.generation === accepted.generation;
      track.addEventListener('ended', () => { if (ownsCapture()) void this.stop(); }, { once: true });
      track.addEventListener?.('capturehandlechange', () => { if (ownsCapture() && !this.selfCaptureStillValid()) void this.stop(); });
      this.video = this.doc.createElement('video');
      this.video.muted = true;
      this.video.playsInline = true;
      this.video.srcObject = stream;
      await this.video.play();
      if (!this.lifecycle.current(epoch) || !this.safeToCapture()) throw new Error('Screen sharing was cancelled.');
      this.acceptInFlight = false;
      this.render();
      this.queueCapture(0);
    } catch (error) {
      stream?.getTracks().forEach((track) => track.stop());
      if (accepted) await this.bestEffortStop(accepted);
      else if (stream) await this.bestEffortStop(item);
      if (!this.disposed && this.lifecycle.current(epoch)) {
        await this.stop({ notify: false });
        const message = ['NotSupportedError', 'SecurityError', 'TypeError'].includes(error?.name)
          ? 'This window cannot safely share only the Spina tab. Open Spina in a supported browser to start sharing.'
          : error.message;
        this.render(message);
      }
    } finally {
      if (this.pendingTrack && stream?.getVideoTracks?.().includes(this.pendingTrack)) this.pendingTrack = null;
      if (this.disposed || !this.lifecycle.current(epoch)) stream?.getTracks().forEach((track) => track.stop());
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

  selfCaptureStillValid() {
    const chosen = this.track?.getCaptureHandle?.();
    return this.track?.getSettings?.().displaySurface === 'browser' && chosen?.handle === this.handle && chosen?.origin === this.location.origin;
  }
}

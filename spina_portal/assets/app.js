import { SpinaApi } from './api.js';
import { PORTAL_CONFIG } from './config.js';
import { normalizeRole, sessionWorkspaceRoles } from './roles.js';
import { SessionStore } from './session.js';
import { SessionRefreshController } from './session-refresh.js';
import { ScreenSharingController } from './screen-sharing.js';
import { clearCashDisbursementRecovery, syncCashDisbursementRecovery } from './cash-disbursement.js';
import {
  bindNavigation,
  escapeHtml,
  navigationMarkup,
  setButtonBusy,
  showToast,
} from './ui.js';
import { mountClientWorkspace } from './roles/client.js';
import { mountEmployeeWorkspace } from './roles/employee.js';
import { mountCollectorWorkspace } from './roles/collector.js';
import { mountManagementWorkspace } from './roles/management.js';

const sessionStore = new SessionStore();
const api = new SpinaApi({
  apiBaseUrl: PORTAL_CONFIG.apiBaseUrl,
  appVersion: PORTAL_CONFIG.appVersion,
  sessionStore,
});

const authView = document.getElementById('auth-view');
const authenticatedApp = document.getElementById('authenticated-app');
const roleContent = document.getElementById('role-content');
const roleNavigation = document.getElementById('role-navigation');
const workspaceTitle = document.getElementById('workspace-title');
const signedInRole = document.getElementById('signed-in-role');
const signedInName = document.getElementById('signed-in-name');
const connectionStatus = document.getElementById('connection-status');
const environmentLabel = document.getElementById('environment-label');
const refreshButton = document.getElementById('refresh-workspace');
const logoutButton = document.getElementById('logout-button');
const loginForm = document.getElementById('login-form');
const workspaceChoice = document.getElementById('workspace-choice');
const workspaceChoiceLabel = document.getElementById('workspace-choice-label');
const navigationToggle = document.getElementById('navigation-toggle');
const workspaceSidebar = document.getElementById('workspace-sidebar');
const currentScreen = document.getElementById('current-screen');
const loginFeedback = document.getElementById('login-feedback');
const accountMenu = document.getElementById('account-menu');
const sharingController = new ScreenSharingController({
  root: document.getElementById('screen-sharing-controls'),
  contentRoot: roleContent,
  api,
  sessionStore,
});
function closeNavigation() {
  workspaceSidebar?.classList.toggle('is-open', false);
  navigationToggle?.setAttribute('aria-expanded', 'false');
}
const workspaceNavigation = bindNavigation(roleNavigation, roleContent, {
  onBeforeNavigate: ({ to }) => sharingController.beforeNavigate(to),
  onNavigate: ({ id, label, userInitiated }) => {
    const handle = currentWorkspaceHandle;
    Promise.resolve(handle?.activate?.(id)).catch(() => {
      if (handle === currentWorkspaceHandle) showToast('This task could not load. Use its Retry control.', 'error');
    });
    sharingController.afterNavigate();
    if (currentScreen) currentScreen.textContent = label || 'Today';
    if (userInitiated) closeNavigation();
  },
});

let currentMount = null;
let currentContext = null;
let workspaceController = null;
let currentWorkspaceHandle = null;
const refreshController = new SessionRefreshController({
  api, sessionStore,
  onRefreshed: async (session) => {
    syncCashDisbursementRecovery(api, session);
    if (!currentContext) return;
    if (currentContext.session.user.id !== session.user?.id) {
      sessionStore.clear();showAuthentication();return;
    }
    const scope = (value) => JSON.stringify([sessionWorkspaceRoles(value), value.permissions, value.user?.permissions, value.user?.status, value.user?.device_registered]);
    if (scope(currentContext.session) !== scope(session)) {
      await showAuthenticated(session, currentContext.role);
    } else {
      currentContext.session = session;
    }
  },
  onExpired: () => { showAuthentication(); showToast('Your session ended. Sign in again.', 'error'); },
});

function updateConnectionStatus() {
  const online = navigator.onLine !== false;
  connectionStatus.textContent = online ? 'Online' : 'Offline — read only';
  connectionStatus.classList.toggle('online', online);
  connectionStatus.classList.toggle('offline', !online);
}

function roleDisplayName(role) {
  return role === 'management' ? 'Management' : `${role.charAt(0).toUpperCase()}${role.slice(1)}`;
}

function setNavigation(items) {
  roleNavigation.innerHTML = navigationMarkup(items);
}

function clearWorkspace() {
  sharingController.dispose();
  workspaceController?.abort();
  workspaceController = null;
  currentWorkspaceHandle = null;
  currentMount = null;
  currentContext = null;
  workspaceNavigation.reset();
  closeNavigation();
  if (accountMenu) accountMenu.open = false;
  roleNavigation.innerHTML = '';
  roleContent.innerHTML = '';
  signedInName.textContent = '';
  if (workspaceChoice) workspaceChoice.innerHTML = '';
  if (workspaceChoiceLabel) workspaceChoiceLabel.hidden = true;
}

function showAuthentication() {
  clearCashDisbursementRecovery(api);
  refreshController.stop();
  clearWorkspace();
  authenticatedApp.hidden = true;
  authView.hidden = false;
  loginForm.querySelector('input[name="username"]')?.focus();
}

async function mountCurrentWorkspace() {
  if (!currentMount || !currentContext) return;
  if (sharingController.session) void sharingController.stop();
  workspaceController?.abort();
  const controller = new AbortController();
  workspaceController = controller;
  currentWorkspaceHandle = null;
  const mount = currentMount;
  const ownerContext = currentContext;
  const isCurrent = () => !controller.signal.aborted && workspaceController === controller && currentContext === ownerContext;
  let registeredHandle = null;
  const context = {
    ...ownerContext, signal: controller.signal,
    getSession: () => isCurrent() ? ownerContext.session : null,
    registerWorkspaceHandle: (handle) => {
      if (!isCurrent()) { handle?.dispose?.(); return false; }
      if (registeredHandle !== handle) registeredHandle?.dispose?.();
      registeredHandle = handle;
      currentWorkspaceHandle = handle;
      return true;
    },
    beforeTaskChange: () => {
      if (isCurrent()) void sharingController.stop({ reason: 'Live view stopped because the work panel changed.' });
    },
    afterTaskChange: () => { if (isCurrent()) sharingController.afterNavigate(); },
    navigateTo: (id) => isCurrent() && workspaceNavigation.activate(id, { focus: true }),
  };
  Object.defineProperty(context, 'session', {get: () => isCurrent() ? ownerContext.session : null});
  controller.signal.addEventListener('abort', () => {
    registeredHandle?.dispose?.();
    if (currentWorkspaceHandle === registeredHandle) currentWorkspaceHandle = null;
    registeredHandle = null;
  }, {once: true});
  refreshButton.disabled = true;
  try {
    await mount(context);
    if (!controller.signal.aborted) workspaceNavigation.activate();
  } catch (error) {
    if (controller.signal.aborted) return;
    roleContent.innerHTML = `<div class="error-card"><strong>The ${escapeHtml(context.role)} workspace could not start.</strong><br>${escapeHtml(error.message || 'Unexpected error')}</div>`;
    showToast(error.message || 'Workspace failed to load.', 'error');
  } finally {
    if (workspaceController === controller) refreshButton.disabled = false;
  }
}

async function refreshCurrentWorkspace() {
  const handle = currentWorkspaceHandle;
  const controller = workspaceController;
  if (!handle?.refreshVisible) return mountCurrentWorkspace();
  if (handle.isWritePending?.()) {
    showToast('Finish or reconcile the current action before refreshing.', 'error');
    return;
  }
  refreshButton.disabled = true;
  try { await handle.refreshVisible(); }
  catch (error) {
    if (handle === currentWorkspaceHandle && !controller?.signal.aborted) showToast(error.message || 'Refresh failed. Your work is retained.', 'error');
  } finally {
    if (controller === workspaceController) refreshButton.disabled = false;
  }
}

async function showAuthenticated(session, requestedRole) {
  syncCashDisbursementRecovery(api, session);
  const roles = sessionWorkspaceRoles(session);
  const hasManagementWorkspace = roles.includes('management');
  const role = hasManagementWorkspace
    ? 'management'
    : roles.includes(normalizeRole(requestedRole))
      ? normalizeRole(requestedRole)
      : roles[0] || 'unknown';
  if (role === 'unknown') {
    sessionStore.clear();
    showAuthentication();
    showToast('This account does not have a supported SPINA role.', 'error');
    return;
  }

  authView.hidden = true;
  authenticatedApp.hidden = false;
  environmentLabel.textContent = PORTAL_CONFIG.environment;
  signedInRole.textContent = roleDisplayName(role);
  signedInName.textContent = session.user.full_name || session.user.username || 'Signed in';
  workspaceTitle.textContent = `${roleDisplayName(role)} workspace`;
  if (workspaceChoice) {
    workspaceChoice.innerHTML = hasManagementWorkspace
      ? ''
      : roles.map((value) => `<option value="${value}">${roleDisplayName(value)}</option>`).join('');
    workspaceChoice.value = hasManagementWorkspace ? '' : role;
  }
  if (workspaceChoiceLabel) workspaceChoiceLabel.hidden = hasManagementWorkspace || roles.length < 2;
  updateConnectionStatus();

  const mounts = {
    client: mountClientWorkspace,
    employee: mountEmployeeWorkspace,
    collector: mountCollectorWorkspace,
    management: mountManagementWorkspace,
  };
  currentMount = mounts[role];
  currentContext = {
    root: roleContent,
    api,
    session,
    sessionStore,
    role,
    setNavigation,
    activateNavigation: () => { if (!workspaceController?.signal.aborted) workspaceNavigation.activate(); },
    uncertainCollection: null,
  };
  sharingController.mount({ session, role });
  refreshController.start();
  await mountCurrentWorkspace();
  if (currentContext?.session === session) roleContent.focus({ preventScroll: true });
}

loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (loginForm.reportValidity && !loginForm.reportValidity()) return;
  if (loginFeedback) { loginFeedback.hidden = true; loginFeedback.textContent = ''; }
  const button = loginForm.querySelector('button[type="submit"]');
  const data = new FormData(loginForm);
  setButtonBusy(button, true, 'Signing in…');
  try {
    const session = await api.login(data.get('username'), data.get('password'));
    loginForm.reset();
    await showAuthenticated(session);
  } catch (error) {
    const message = error.code === 'device_approval_required'
      ? 'This device is registered as pending. Management must approve it before Collector access is activated.'
      : error.message;
    if (loginFeedback) {
      loginFeedback.textContent = message || 'Sign-in failed. Check your details and try again.';
      loginFeedback.hidden = false;
      loginFeedback.focus();
    } else showToast(message, 'error', 7600);
  } finally {
    setButtonBusy(button, false);
  }
});

refreshButton.addEventListener('click', () => refreshCurrentWorkspace());
workspaceChoice?.addEventListener('change', () => {
  const session = currentContext?.session;
  if (!session || sessionWorkspaceRoles(session).includes('management')) return;
  if (sessionWorkspaceRoles(session).includes(workspaceChoice.value)) {
    if (accountMenu) accountMenu.open = false;
    workspaceNavigation.reset();
    void showAuthenticated(session, workspaceChoice.value);
  }
});
logoutButton.addEventListener('click', async () => {
  setButtonBusy(logoutButton, true, 'Signing out…');
  const revocation = api.logout();
  showAuthentication();
  try {
    await revocation;
  } catch (error) {
    showToast(error.message, 'error');
  } finally {
    setButtonBusy(logoutButton, false);
  }
});

globalThis.addEventListener('spina:unauthorized', () => {
  showAuthentication();
  showToast('Your session ended. Sign in again.', 'error');
});
globalThis.addEventListener('online', () => {
  updateConnectionStatus();
  sharingController.updateCaptureAvailability();
  showToast('Connection restored. Refresh to load authoritative records.', 'success');
});
globalThis.addEventListener('offline', () => {
  if (sharingController.session || sharingController.preparedTrack || sharingController.prepareInFlight || sharingController.readyInFlight) void sharingController.stop();
  updateConnectionStatus();
  sharingController.updateCaptureAvailability();
  showToast('Connection lost. Financial entry is unavailable while offline.', 'error');
});

navigationToggle?.addEventListener('click', () => {
  const open = navigationToggle.getAttribute('aria-expanded') !== 'true';
  navigationToggle.setAttribute('aria-expanded', String(open));
  workspaceSidebar?.classList.toggle('is-open', open);
});
workspaceSidebar?.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    const wasOpen = navigationToggle?.getAttribute('aria-expanded') === 'true';
    closeNavigation();
    if (wasOpen) navigationToggle?.focus();
  }
});

if ('serviceWorker' in navigator) {
  globalThis.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      // The portal remains usable online when service worker registration is blocked.
    });
  });
}

async function boot() {
  updateConnectionStatus();
  let session = sessionStore.load();
  let revision = sessionStore.revision;
  if (!session) {
    showAuthentication();
    return;
  }
  try {
    if (session.refresh_token && Date.parse(session.expires_at) <= Date.now() + 120000) {
      session = await api.refresh();
      revision = sessionStore.revision;
    }
    const current = await api.request('/api/v1/auth/me');
    api.assertSessionRevision(revision);
    const refreshed = {
      ...session,
      user: {
        ...session.user,
        ...(current.user || {}),
      },
    };
    sessionStore.save(refreshed);
    await showAuthenticated(refreshed);
  } catch (error) {
    if (error.code === 'session_changed' || sessionStore.revision !== revision) return;
    if (error.status === 401 || error.status === 403) {
      sessionStore.clear();
      showAuthentication();
      showToast('Your saved session is no longer authorized. Sign in again.', 'error');
      return;
    }
    await showAuthenticated(session);
    showToast('The server could not verify the session yet. Workspace sections may be unavailable until connection returns.', 'error');
  }
}

boot();

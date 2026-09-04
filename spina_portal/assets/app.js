import { SpinaApi } from './api.js';
import { PORTAL_CONFIG } from './config.js';
import { normalizeRole } from './roles.js';
import { SessionStore } from './session.js';
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

let currentMount = null;
let currentContext = null;

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

function showAuthentication() {
  currentMount = null;
  currentContext = null;
  authenticatedApp.hidden = true;
  authView.hidden = false;
  roleNavigation.innerHTML = '';
  roleContent.innerHTML = '';
  loginForm.querySelector('input[name="username"]')?.focus();
}

async function mountCurrentWorkspace() {
  if (!currentMount || !currentContext) return;
  refreshButton.disabled = true;
  try {
    await currentMount(currentContext);
  } catch (error) {
    roleContent.innerHTML = `<div class="error-card"><strong>The ${escapeHtml(currentContext.role)} workspace could not start.</strong><br>${escapeHtml(error.message || 'Unexpected error')}</div>`;
    showToast(error.message || 'Workspace failed to load.', 'error');
  } finally {
    refreshButton.disabled = false;
  }
}

async function showAuthenticated(session) {
  const role = normalizeRole(session?.user?.role || session?.user?.roles?.[0]);
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
    uncertainCollection: null,
  };
  await mountCurrentWorkspace();
  roleContent.focus({ preventScroll: true });
}

loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = loginForm.querySelector('button[type="submit"]');
  const data = new FormData(loginForm);
  setButtonBusy(button, true, 'Signing in…');
  try {
    const session = await api.login(data.get('username'), data.get('password'));
    loginForm.reset();
    showToast('Secure sign-in completed.', 'success');
    await showAuthenticated(session);
  } catch (error) {
    const message = error.code === 'device_approval_required'
      ? 'This device is registered as pending. Management must approve it before Collector access is activated.'
      : error.message;
    showToast(message, 'error', 7600);
  } finally {
    setButtonBusy(button, false);
  }
});

refreshButton.addEventListener('click', () => mountCurrentWorkspace());
logoutButton.addEventListener('click', async () => {
  setButtonBusy(logoutButton, true, 'Signing out…');
  try {
    await api.logout();
  } catch (error) {
    showToast(error.message, 'error');
  } finally {
    setButtonBusy(logoutButton, false);
    showAuthentication();
  }
});

globalThis.addEventListener('spina:unauthorized', () => {
  showAuthentication();
  showToast('Your session ended. Sign in again.', 'error');
});
globalThis.addEventListener('online', () => {
  updateConnectionStatus();
  showToast('Connection restored. Refresh to load authoritative records.', 'success');
});
globalThis.addEventListener('offline', () => {
  updateConnectionStatus();
  showToast('Connection lost. Financial entry is unavailable while offline.', 'error');
});

bindNavigation(roleNavigation, roleContent);

if ('serviceWorker' in navigator) {
  globalThis.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      // The portal remains usable online when service worker registration is blocked.
    });
  });
}

async function boot() {
  updateConnectionStatus();
  const session = sessionStore.load();
  if (!session) {
    showAuthentication();
    return;
  }
  try {
    const current = await api.request('/api/v1/auth/me');
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

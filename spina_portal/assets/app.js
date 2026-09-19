import { SpinaApi } from './api.js';
import { PORTAL_CONFIG } from './config.js';
import { normalizeRole, sessionWorkspaceRoles } from './roles.js';
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
const workspaceChoice = document.getElementById('workspace-choice');
const workspaceChoiceLabel = document.getElementById('workspace-choice-label');

let currentMount = null;
let currentContext = null;
let workspaceController = null;

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
  workspaceController?.abort();
  workspaceController = null;
  currentMount = null;
  currentContext = null;
  roleNavigation.innerHTML = '';
  roleContent.innerHTML = '';
  signedInName.textContent = '';
  if (workspaceChoice) workspaceChoice.innerHTML = '';
  if (workspaceChoiceLabel) workspaceChoiceLabel.hidden = true;
}

function showAuthentication() {
  clearWorkspace();
  authenticatedApp.hidden = true;
  authView.hidden = false;
  loginForm.querySelector('input[name="username"]')?.focus();
}

async function mountCurrentWorkspace() {
  if (!currentMount || !currentContext) return;
  workspaceController?.abort();
  const controller = new AbortController();
  workspaceController = controller;
  const mount = currentMount;
  const context = { ...currentContext, signal: controller.signal };
  refreshButton.disabled = true;
  try {
    await mount(context);
  } catch (error) {
    if (controller.signal.aborted) return;
    roleContent.innerHTML = `<div class="error-card"><strong>The ${escapeHtml(context.role)} workspace could not start.</strong><br>${escapeHtml(error.message || 'Unexpected error')}</div>`;
    showToast(error.message || 'Workspace failed to load.', 'error');
  } finally {
    if (workspaceController === controller) refreshButton.disabled = false;
  }
}

async function showAuthenticated(session, requestedRole) {
  const roles = sessionWorkspaceRoles(session);
  const role = roles.includes(normalizeRole(requestedRole)) ? normalizeRole(requestedRole) : roles[0] || 'unknown';
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
    workspaceChoice.innerHTML = roles.map((value) => `<option value="${value}">${roleDisplayName(value)}</option>`).join('');
    workspaceChoice.value = role;
  }
  if (workspaceChoiceLabel) workspaceChoiceLabel.hidden = roles.length < 2;
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
  if (currentContext?.session === session) roleContent.focus({ preventScroll: true });
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
workspaceChoice?.addEventListener('change', () => {
  const session = currentContext?.session;
  if (session && sessionWorkspaceRoles(session).includes(workspaceChoice.value)) {
    void showAuthenticated(session, workspaceChoice.value);
  }
});
logoutButton.addEventListener('click', async () => {
  setButtonBusy(logoutButton, true, 'Signing out…');
  clearWorkspace();
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

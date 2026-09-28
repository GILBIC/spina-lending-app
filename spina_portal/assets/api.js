export class ApiError extends Error {
  constructor(message, { status = 0, code = 'request_failed', data = null, cause } = {}) {
    super(message, cause ? { cause } : undefined);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.data = data;
  }
}

function normalizeBaseUrl(value) {
  const normalized = String(value ?? '').trim();
  return normalized.endsWith('/') ? normalized.slice(0, -1) : normalized;
}

function errorDetail(payload, fallback) {
  const error = payload?.error;
  const detail = payload?.detail;
  if (error && typeof error === 'object') {
    return {
      code: String(error.code || fallback),
      message: String(error.message || payload?.message || 'The request could not be completed.'),
      data: payload?.data ?? null,
    };
  }
  if (detail && typeof detail === 'object') {
    return {
      code: String(detail.code || fallback),
      message: String(detail.message || payload?.message || 'The request could not be completed.'),
      data: payload?.data ?? detail,
    };
  }
  return {
    code: fallback,
    message: String(detail || payload?.message || 'The request could not be completed.'),
    data: payload?.data ?? null,
  };
}

function emitUnauthorized() {
  if (
    typeof globalThis.dispatchEvent === 'function' &&
    typeof globalThis.CustomEvent === 'function'
  ) {
    globalThis.dispatchEvent(new CustomEvent('spina:unauthorized'));
  }
}

export class SpinaApi {
  constructor({
    apiBaseUrl = '',
    appVersion = '0.1.0',
    sessionStore,
    fetchImpl = globalThis.fetch?.bind(globalThis),
    logoutTimeoutMs = 5000,
    refreshTimeoutMs = 15000,
  }) {
    if (!sessionStore) {
      throw new TypeError('sessionStore is required.');
    }
    if (typeof fetchImpl !== 'function') {
      throw new TypeError('fetchImpl must be a function.');
    }
    this.apiBaseUrl = normalizeBaseUrl(apiBaseUrl);
    this.appVersion = String(appVersion || '0.1.0');
    this.sessionStore = sessionStore;
    this.fetchImpl = fetchImpl;
    this.logoutTimeoutMs = logoutTimeoutMs;
    this.refreshTimeoutMs = refreshTimeoutMs;
  }

  async request(
    path,
    {
      method = 'GET',
      body,
      rawBody,
      responseType = 'json',
      headers = {},
      authenticated = true,
      financial = false,
      signal,
    } = {},
  ) {
    const normalizedMethod = String(method).toUpperCase();
    const sessionRevision = this.sessionStore.revision;
    if (body !== undefined && rawBody !== undefined) throw new TypeError('Choose JSON or raw request content.');
    const requestHeaders = {
      'X-App-Platform': 'web',
      'X-App-Version': this.appVersion,
      ...headers,
    };
    if (authenticated) {
      const session = this.sessionStore.load();
      if (!session) {
        throw new ApiError('Your session has expired. Sign in again.', {
          status: 401,
          code: 'session_required',
        });
      }
      requestHeaders.Authorization = `Bearer ${session.access_token}`;
      requestHeaders['X-Device-Id'] = this.sessionStore.deviceId();
    }

    const init = {
      method: normalizedMethod,
      headers: requestHeaders,
      signal,
      cache: 'no-store',
    };
    if (body !== undefined) {
      requestHeaders['Content-Type'] = 'application/json';
      init.body = JSON.stringify(body);
    }
    if (rawBody !== undefined) init.body = rawBody;

    let response;
    try {
      response = await this.fetchImpl(`${this.apiBaseUrl}${path}`, init);
    } catch (cause) {
      const uncertain = financial || !['GET', 'HEAD', 'OPTIONS'].includes(normalizedMethod);
      throw new ApiError(
        uncertain
          ? 'The connection ended before SPINA could confirm the result. Refresh the authoritative record before trying again.'
          : 'SPINA could not reach the server. Check the connection and try again.',
        {
          status: 0,
          code: uncertain ? 'network_uncertain' : 'network_unavailable',
          cause,
        },
      );
    }

    if (response.ok && responseType === 'blob') return response.blob();
    let payload = null;
    const contentType = response.headers?.get?.('content-type') ?? '';
    if (response.status !== 204) {
      try {
        payload = contentType.includes('application/json')
          ? await response.json()
          : { message: await response.text() };
      } catch {
        payload = null;
      }
    }

    if (!response.ok || payload?.success === false) {
      const detail = errorDetail(payload, `http_${response.status}`);
      if (authenticated && response.status === 401 && this.sessionStore.revision === sessionRevision) {
        this.sessionStore.clear();
        emitUnauthorized();
      }
      throw new ApiError(detail.message, {
        status: response.status,
        code: detail.code,
        data: detail.data,
      });
    }

    if (payload?.success === true && Object.hasOwn(payload, 'data')) {
      return payload.data;
    }
    return payload;
  }

  async login(identifier, password) {
    this.sessionStore.clear();
    const revision = this.sessionStore.revision;
    const data = await this.request('/api/v1/auth/login', {
      method: 'POST',
      authenticated: false,
      body: {
        username: String(identifier ?? '').trim(),
        password: String(password ?? ''),
        device_id: this.sessionStore.deviceId(),
        platform: 'web',
        app_version: this.appVersion,
      },
    });
    this.assertSessionRevision(revision);
    this.sessionStore.save(data);
    return data;
  }

  register(input) {
    return this.request('/api/v1/auth/register', {
      method: 'POST',
      authenticated: false,
      body: {
        username: String(input.username ?? '').trim(),
        email: String(input.email ?? '').trim().toLowerCase(),
        full_name: String(input.fullName ?? '').trim(),
        client_code: String(input.clientCode ?? '').trim(),
        phone_number: String(input.phoneNumber ?? '').trim() || null,
        password: String(input.password ?? ''),
      },
    });
  }

  async refresh() {
    const current = this.sessionStore.load();
    const revision = this.sessionStore.revision;
    if (!current?.refresh_token) {
      throw new ApiError('There is no refresh session. Sign in again.', {
        status: 401,
        code: 'refresh_session_required',
      });
    }
    let data;
    const controller = new AbortController();
    let timer;
    try {
      data = await Promise.race([
        this.request('/api/v1/auth/refresh', {
          method: 'POST',
          authenticated: false,
          signal: controller.signal,
          headers: { 'X-Device-Id': this.sessionStore.deviceId() },
          body: { refresh_token: current.refresh_token },
        }),
        new Promise((resolve, reject) => {
          timer = setTimeout(() => {
            controller.abort();
            reject(new ApiError('Session renewal could not be confirmed. Try again while the current session is valid.', { code: 'refresh_timeout' }));
          }, this.refreshTimeoutMs);
        }),
      ]);
    } catch (error) {
      if (this.sessionStore.revision === revision && [401, 403].includes(error.status)) {
        this.sessionStore.clear();
        emitUnauthorized();
      }
      throw error;
    } finally {
      clearTimeout(timer);
    }
    this.assertSessionRevision(revision);
    this.sessionStore.save(data);
    return data;
  }

  assertSessionRevision(revision) {
    if (this.sessionStore.revision !== revision) {
      throw new ApiError('This request belongs to a session that has ended.', { code: 'session_changed' });
    }
  }

  async logout() {
    const current = this.sessionStore.load();
    this.sessionStore.clear();
    if (!current) return;
    const controller = new AbortController();
    let timer;
    try {
      await Promise.race([
        this.request('/api/v1/auth/logout', {
          method: 'POST', authenticated: false, signal: controller.signal,
          headers: { Authorization: `Bearer ${current.access_token}`, 'X-Device-Id': this.sessionStore.deviceId() },
        }),
        new Promise((resolve) => { timer = setTimeout(() => { controller.abort(); resolve(); }, this.logoutTimeoutMs); }),
      ]);
    } catch {
      // Remote revocation is best effort; local sign-out has already completed.
    } finally {
      clearTimeout(timer);
    }
  }
}

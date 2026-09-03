const runtime = globalThis.SPINA_CONFIG ?? {};

export const PORTAL_CONFIG = Object.freeze({
  apiBaseUrl: String(runtime.apiBaseUrl ?? '').trim(),
  appVersion: String(runtime.appVersion ?? '0.1.0').trim() || '0.1.0',
  environment: String(runtime.environment ?? 'Company').trim() || 'Company',
});

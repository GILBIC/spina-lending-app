export class MemoryStorage {
  constructor(initial = {}) {
    this._values = new Map(
      Object.entries(initial).map(([key, value]) => [String(key), String(value)]),
    );
  }

  getItem(key) {
    const normalized = String(key);
    return this._values.has(normalized) ? this._values.get(normalized) : null;
  }

  setItem(key, value) {
    this._values.set(String(key), String(value));
  }

  removeItem(key) {
    this._values.delete(String(key));
  }

  clear() {
    this._values.clear();
  }
}

function requireStorage(value, name) {
  if (
    value == null ||
    typeof value.getItem !== 'function' ||
    typeof value.setItem !== 'function' ||
    typeof value.removeItem !== 'function'
  ) {
    throw new TypeError(`${name} must implement the Web Storage interface.`);
  }
  return value;
}

export class SessionStore {
  static SESSION_KEY = 'spina.mvp.session.v1';
  static DEVICE_KEY = 'spina.mvp.device.v1';
  static SEQUENCE_KEY = 'spina.mvp.device-sequence.v1';

  constructor({
    sessionStorageRef = globalThis.sessionStorage,
    localStorageRef = globalThis.localStorage,
    cryptoRef = globalThis.crypto,
  } = {}) {
    this._sessionStorage = requireStorage(sessionStorageRef, 'sessionStorageRef');
    this._localStorage = requireStorage(localStorageRef, 'localStorageRef');
    if (cryptoRef == null || typeof cryptoRef.randomUUID !== 'function') {
      throw new TypeError('cryptoRef.randomUUID is required.');
    }
    this._crypto = cryptoRef;
  }

  deviceId() {
    const current = this._localStorage.getItem(SessionStore.DEVICE_KEY)?.trim();
    if (current) {
      return current;
    }
    const value = `spina-web-${this._crypto.randomUUID()}`;
    this._localStorage.setItem(SessionStore.DEVICE_KEY, value);
    return value;
  }

  save(session) {
    if (
      session == null ||
      typeof session !== 'object' ||
      typeof session.access_token !== 'string' ||
      session.access_token.trim() === '' ||
      session.user == null ||
      typeof session.user !== 'object'
    ) {
      throw new TypeError('A valid authenticated session is required.');
    }
    this._sessionStorage.setItem(
      SessionStore.SESSION_KEY,
      JSON.stringify(session),
    );
    return session;
  }

  load() {
    const raw = this._sessionStorage.getItem(SessionStore.SESSION_KEY);
    if (!raw) {
      return null;
    }
    try {
      const session = JSON.parse(raw);
      if (
        session == null ||
        typeof session !== 'object' ||
        typeof session.access_token !== 'string' ||
        session.access_token.trim() === '' ||
        session.user == null ||
        typeof session.user !== 'object'
      ) {
        throw new TypeError('Stored session is incomplete.');
      }
      return session;
    } catch {
      this._sessionStorage.removeItem(SessionStore.SESSION_KEY);
      return null;
    }
  }

  clear() {
    this._sessionStorage.removeItem(SessionStore.SESSION_KEY);
  }

  nextDeviceSequence() {
    const currentText = this._localStorage.getItem(SessionStore.SEQUENCE_KEY);
    const current = Number.parseInt(currentText ?? '0', 10);
    const next = Number.isSafeInteger(current) && current >= 0 ? current + 1 : 1;
    this._localStorage.setItem(SessionStore.SEQUENCE_KEY, String(next));
    return next;
  }
}

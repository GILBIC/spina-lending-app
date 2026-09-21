// One workspace owns one financial write. A lost connection needs an authoritative remount.
export function createCollectorWriteGuard({
  eventTarget = globalThis,
  signal,
  isOnline = () => globalThis.navigator?.onLine !== false,
  onLock,
}) {
  let disposed = false;
  let busy = false;
  let lockMessage = '';
  const offlineMessage = 'Connection lost. New payments and remittances are blocked. An in-flight request may already be saved; reconnect and refresh the route before another attempt.';
  function lock(message) {
    if (disposed) return;
    lockMessage ||= message;
    onLock(lockMessage);
  }
  function offline() { lock(offlineMessage); }
  function sync() {
    if (disposed) return;
    if (!isOnline()) offline();
    else if (lockMessage) onLock(lockMessage);
  }
  function dispose() {
    if (disposed) return;
    disposed = true;
    eventTarget.removeEventListener?.('offline', offline);
    signal?.removeEventListener('abort', dispose);
  }
  eventTarget.addEventListener?.('offline', offline);
  signal?.addEventListener('abort', dispose, {once: true});
  if (signal?.aborted) dispose();
  else sync();
  return {
    get current() { return !disposed; },
    get locked() { return Boolean(lockMessage); },
    begin() {
      if (disposed || busy) return false;
      sync();
      if (lockMessage) return false;
      busy = true;
      return true;
    },
    finish() { busy = false; sync(); },
    lock,
    sync,
    dispose,
  };
}

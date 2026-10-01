// Refresh only authentication. Never replay an interrupted financial request.
export class SessionRefreshController {
  constructor({ api, sessionStore, onRefreshed = () => {}, onExpired = () => {}, now = Date.now,
    setTimer = (callback, delay) => globalThis.setTimeout(callback, delay), clearTimer = (timer) => globalThis.clearTimeout(timer) }) {
    Object.assign(this, { api, sessionStore, onRefreshed, onExpired, now, setTimer, clearTimer });
    this.generation = 0;
    this.timer = null;
  }

  stop() {
    this.generation += 1;
    if (this.timer != null) this.clearTimer(this.timer);
    this.timer = null;
  }

  start() {
    this.stop();
    const session = this.sessionStore.load();
    const expiry = Date.parse(session?.expires_at);
    if (!session?.refresh_token || !Number.isFinite(expiry)) return;
    this.schedule(Math.max(0, expiry - this.now() - 120000));
  }

  schedule(delay) {
    const generation = this.generation;
    const revision = this.sessionStore.revision;
    this.timer = this.setTimer(async () => {
      this.timer = null;
      if (generation !== this.generation || revision !== this.sessionStore.revision) return;
      try {
        const refreshed = await this.api.refresh();
        if (generation !== this.generation) return;
        await this.onRefreshed(refreshed);
        if (generation === this.generation) this.start();
      } catch {
        if (generation !== this.generation || revision !== this.sessionStore.revision) return;
        const expiry = Date.parse(this.sessionStore.load()?.expires_at);
        if (!Number.isFinite(expiry) || expiry <= this.now()) {
          this.sessionStore.clear();
          this.stop();
          this.onExpired();
        } else {
          this.schedule(Math.min(30000, expiry - this.now()));
        }
      }
    }, Math.min(delay, 2147483647));
  }
}

# Standard production deployment

Dispatch `Spina DigitalOcean Production Deploy` from protected `main`. The job
uses the fixed GitHub `Production` environment and checks the event, protected
ref, workflow identity and full source SHA again before staging credentials.
Configure that environment to allow only protected `main` and retain its release
review rules. Source code no longer publishes rendezvous files or calls the old
secret broker.

The environment needs these independently provisioned inputs:

| Input | Kind | Content |
| --- | --- | --- |
| `SPINA_DEPLOY_TARGET_JSON` | Environment variable | JSON target described below |
| `SPINA_DEPLOY_SSH_KEY` | Environment secret | Deployment SSH key already authorized on the exact host |
| `SPINA_DEPLOY_KNOWN_HOSTS` | Environment secret | OpenSSH known-hosts entry for the target IP, verified through existing trusted host access or the provider console |
| `SPINA_RUNTIME_SECRETS_JSON` | Environment secret | JSON with `database_pooler_url`, `supabase_url`, `supabase_publishable_key`, `supabase_secret_key` |

Do not obtain the host pin from an unauthenticated scan. A missing pin, wrong
target or different server key stops SSH before any upload. Manage deployment-key
rotation separately; an application deploy does not remove deployment/recovery
keys from the host. No real environment values are supplied by this source change.

The target JSON requires a positive `droplet_id`, public IPv4 `host`, primary
`hostname`, nonempty `aliases` list, explicit `cors_origins` list and
`staff_invite_redirect_url`. Origins and the invite redirect must use HTTPS on
declared domains. The fallback hostname must match the declared IP. The workflow
binds `run_id` itself. Production currently needs primary `spina.com.ph`, aliases
`app.spina.com.ph`, `api.spina.com.ph`, `www.spina.com.ph` and the existing matching
sslip hostname. Enter the actual retained origin list and invite URL; they are not
inferred from the primary domain.

An upgrade copies the active Caddy configuration unchanged, including redirects
and host-specific behavior. A first installation renders all declared hosts.
Before activation Caddy validates/adapts the candidate, and the deployment helper
requires every declared hostname to be present. Missing coverage stops the
release before switching runtime, portal or Caddy. Current CORS/invite assignments
are retained in the operator environment when it does not already own them;
existing operator values keep precedence. A deliberate domain/origin change is
an operator configuration change, with its own recovery copy and validation.

The release archive includes the exact Git SHA, target declaration, helper and
`requirements-runtime.lock`. SHA256 verifies the staged archive before extraction.
Each release owns its Python environment and installs only hash-verified wheels
from the Linux x86_64 / Python 3.12 lock, including pinned packaging tools. Local
packages build without dependency resolution or isolated build downloads. The
portal has no package dependencies and builds directly from the checked-out source.

Refresh the lock with a reviewed resolver for Linux x86_64 / Python 3.12 from
`requirements.txt` plus the packaging tools pinned in the lock; generate hashes,
review version changes, and verify installation/imports on Linux before release.
The September 2026 lock retains the dependency versions used by the local suite
and includes the Linux-only `uvloop` dependency. Development/test tools are absent.

Detached per-run launch, retry, completion files, source checks, private runtime
files and automatic activation rollback remain in the same bootstrap. Follow
[deployment recovery](../../docs/release/deployment-recovery.md) for recovery.
Repository tests use temporary synthetic files and stubbed service operations.
They do not demonstrate real credentials, environment setup, DNS, production
deployment or operational acceptance.

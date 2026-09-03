# DigitalOcean Production Cutover Design

## Goal

Publish Spina on a stable public HTTPS address that is usable from ordinary browsers without Vercel Preview authentication, while preserving the existing FastAPI, Supabase Auth, and Supabase PostgreSQL authority.

## Scope

- Host the current Spina web portal and FastAPI backend on one DigitalOcean Droplet in Singapore.
- Keep Supabase PostgreSQL and Supabase Auth unchanged.
- Provide a temporary publicly trusted HTTPS hostname through `sslip.io`; a company-owned domain can replace it later without changing application architecture.
- Preserve all four role experiences: Client, Employee, Collector, and Management.
- Do not import or modify real company financial records as part of the hosting cutover.

## Infrastructure

- Region: `sgp1`.
- Image: Ubuntu 24.04 LTS.
- Size: `s-1vcpu-1gb` at USD 6/month.
- Monitoring: enabled.
- Backups: initially disabled; enable after the deployment is proven and the backup/restore procedure is accepted.
- Reverse proxy: Caddy, providing automatic HTTPS and HTTP-to-HTTPS redirects.
- Application service: one `systemd`-managed Uvicorn worker bound to `127.0.0.1:8000`.
- Static portal: built by GitHub Actions and served by Caddy from `/var/www/spina`.

## Deployment Flow

1. A dedicated GitHub Actions workflow generates an ephemeral Ed25519 SSH key.
2. The workflow writes only the public key to a short-lived branch file and waits for a DigitalOcean target file.
3. Management automation creates the Droplet with that public key, enables IPv6, and writes the Droplet IP and HTTPS hostname into the target file.
4. The workflow obtains a GitHub OIDC token.
5. A temporary Supabase Edge Function validates the OIDC issuer, audience, repository, branch, event, and exact workflow path before returning the existing Supabase runtime connection values.
6. The workflow builds the portal, uploads the release and environment file by SSH, installs the server service, configures Caddy, and verifies health over HTTPS.
7. The temporary secret-broker Edge Function is disabled immediately after deployment.
8. The ephemeral public key and rendezvous files are removed from the release branch after verification.

## Secret Boundary

- No SSH private key, database URL, Supabase service-role key, password, or test credential is committed to GitHub, Notion, Create State, workflow logs, or deployment artifacts.
- The GitHub workflow receives Supabase values only after a successful short-lived OIDC verification.
- The server environment file is owned by root with mode `0600`.
- Caddy is the only public listener for application traffic; Uvicorn remains loopback-only.

## Public Address

The initial hostname is derived from the Droplet IP under `sslip.io`, for example:

```text
https://spina.203-0-113-10.sslip.io
```

This gives a publicly trusted TLS certificate for acceptance testing. A company-owned domain is still required before broad production launch because `sslip.io` is an external wildcard-DNS service intended as a transitional address.

## Runtime Layout

```text
/opt/spina/releases/<git-sha>/   immutable uploaded release
/opt/spina/current               symlink to active release
/opt/spina/venv                  Python virtual environment
/etc/spina/spina.env             root-only runtime environment
/etc/systemd/system/spina-api.service
/etc/caddy/Caddyfile
/var/www/spina                   active static portal
```

## Failure and Rollback

- The active release symlink changes only after the new files and Python packages are installed.
- A failed health check stops the workflow and leaves the prior active release available.
- The workflow records the exact Git SHA, Droplet ID, IP, hostname, and health response without recording secrets.
- Rollback consists of repointing `/opt/spina/current`, restoring the matching static directory, restarting `spina-api`, and re-running `/health/ready`.

## Acceptance

The cutover is accepted only when all of the following are freshly verified:

- HTTPS root returns the Spina sign-in page.
- `/health/live` returns HTTP 200.
- `/health/ready` returns HTTP 200 with `database: ok`.
- The Client, Employee, Collector, and Management test accounts can authenticate through the public HTTPS address.
- The temporary secret broker no longer returns deployment secrets.
- GitHub, Notion, and Create State contain the non-secret deployment evidence.

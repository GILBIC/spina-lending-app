# DigitalOcean Production Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the current Spina web portal and FastAPI backend on one stable DigitalOcean HTTPS address while retaining the existing Supabase database and authentication authority.

**Architecture:** GitHub Actions builds and deploys an immutable release to an Ubuntu Droplet over an ephemeral SSH key. A temporary Supabase Edge Function releases existing Supabase runtime values only after validating a GitHub OIDC token for the exact repository, branch, and workflow. Caddy terminates HTTPS and serves the portal while proxying API traffic to a loopback-only Uvicorn service.

**Tech Stack:** GitHub Actions, Ubuntu 24.04, Bash, Python 3.12, FastAPI/Uvicorn, Caddy, systemd, Supabase PostgreSQL/Auth, GitHub OIDC.

**Spec:** `docs/superpowers/specs/2026-09-03-digitalocean-production-cutover-design.md`

## Global Constraints

- Product name is **Spina** only.
- Supabase PostgreSQL remains the only authoritative company database.
- Supabase Auth remains the authentication authority.
- No secret may be committed, logged, added to an artifact, Notion, or Create State.
- Uvicorn binds only to `127.0.0.1:8000`.
- Caddy is the only public HTTP/HTTPS listener.
- Initial host uses a transitional `sslip.io` name and automatic HTTPS.
- Deployment must stop on any failed command or failed health check.
- iOS remains paused; this cutover serves Web and the backend used by Windows/Android.

---

### Task 1: Add deployment-contract checks

**Files:**
- Create: `tools/test_digitalocean_deployment_contract.py`
- Test: `tools/test_digitalocean_deployment_contract.py`

**Interfaces:**
- Consumes: planned paths for the bootstrap script and workflow.
- Produces: a static safety contract that rejects secret literals, public Uvicorn binding, missing HTTPS verification, and missing cleanup behavior.

- [ ] **Step 1: Write the failing contract test**

Create a Python test that requires:

```python
assert "127.0.0.1:8000" in bootstrap
assert "caddy validate" in bootstrap
assert "https://$HOSTNAME/health/ready" in workflow
assert "id-token: write" in workflow
assert "SUPABASE_DB_URL" not in workflow
assert "SUPABASE_SERVICE_ROLE_KEY" not in workflow
```

It must fail because the deployment files do not exist yet.

- [ ] **Step 2: Run the test and confirm RED**

Run:

```bash
python tools/test_digitalocean_deployment_contract.py
```

Expected: non-zero exit reporting the missing workflow or bootstrap file.

- [ ] **Step 3: Commit the failing contract**

```bash
git add tools/test_digitalocean_deployment_contract.py
git commit -m "test: define DigitalOcean deployment safety contract"
```

### Task 2: Add the idempotent Droplet bootstrap

**Files:**
- Create: `ops/digitalocean/bootstrap.sh`
- Test: `tools/test_digitalocean_deployment_contract.py`

**Interfaces:**
- Consumes: `/tmp/spina-release.tar.gz`, `/tmp/spina.env`, Git SHA, and public hostname.
- Produces: `/opt/spina/current`, `/opt/spina/venv`, `/etc/spina/spina.env`, `spina-api.service`, Caddy configuration, and healthy HTTPS endpoints.

- [ ] **Step 1: Implement strict argument and file validation**

The script must start with `set -Eeuo pipefail`, require exactly the Git SHA and hostname, validate both with conservative regular expressions, and reject missing release/environment files.

- [ ] **Step 2: Install minimum server dependencies**

Install `python3`, `python3-venv`, `python3-pip`, `caddy`, `curl`, `ca-certificates`, and `ufw`. Create a 1 GiB swap file only when no swap exists.

- [ ] **Step 3: Install an immutable application release**

Extract into `/opt/spina/releases/$SHA`, create or refresh `/opt/spina/venv`, install root requirements plus both local Python packages, and update `/opt/spina/current` only after package installation succeeds.

- [ ] **Step 4: Install the root-only environment file**

Move `/tmp/spina.env` to `/etc/spina/spina.env` with owner `root:root` and mode `0600`. Never print the file.

- [ ] **Step 5: Configure systemd and Caddy**

Create `spina-api.service` with one Uvicorn worker bound to `127.0.0.1:8000`. Configure Caddy for the supplied hostname, automatic HTTPS, static portal service, `/api/*` and `/health/*` reverse proxying, and security headers.

- [ ] **Step 6: Enable the host firewall**

Allow only OpenSSH and Caddy’s HTTP/HTTPS service before enabling UFW non-interactively.

- [ ] **Step 7: Verify configuration and runtime**

Run `systemd-analyze verify`, `caddy validate`, restart services, then poll loopback liveness/readiness before returning success.

- [ ] **Step 8: Run the contract test and shell syntax check**

```bash
bash -n ops/digitalocean/bootstrap.sh
python tools/test_digitalocean_deployment_contract.py
```

Expected: PASS.

- [ ] **Step 9: Commit the bootstrap**

```bash
git add ops/digitalocean/bootstrap.sh tools/test_digitalocean_deployment_contract.py
git commit -m "ops: add hardened DigitalOcean bootstrap"
```

### Task 3: Add the GitHub OIDC deployment workflow

**Files:**
- Create: `.github/workflows/spina-digitalocean-deploy.yml`
- Modify: `tools/test_digitalocean_deployment_contract.py`

**Interfaces:**
- Consumes: the exact branch source, a target rendezvous file, and the OIDC secret broker.
- Produces: built portal files, uploaded release files, HTTPS health evidence, and a non-secret deployment artifact.

- [ ] **Step 1: Generate an ephemeral SSH key**

The workflow must run on `ubuntu-latest`, request `contents: write`, `issues: write`, and `id-token: write`, generate an Ed25519 key, and publish only the public key to `.deploy/digitalocean-public-key.txt` on the deployment branch.

- [ ] **Step 2: Wait for the target rendezvous**

Poll `.deploy/digitalocean-target.json` through the GitHub API and validate exact `droplet_id`, IPv4 `host`, and `hostname` values before any SSH attempt.

- [ ] **Step 3: Obtain Supabase runtime values through OIDC**

Request audience `spina-digitalocean-deploy`, call the temporary Edge Function with the bearer token, and write a root environment file without echoing values. Add each returned value to GitHub’s masking list before use.

- [ ] **Step 4: Build and package the exact source**

Run the existing portal tests/build and archive only `dist`, `gilbic_backend`, `spina_backend_mobile`, `requirements.txt`, and `ops/digitalocean/bootstrap.sh`.

- [ ] **Step 5: Upload and execute the bootstrap**

Use a pinned `known_hosts` entry from `ssh-keyscan`, upload the release and environment file, and run the bootstrap with the exact Git SHA and hostname.

- [ ] **Step 6: Verify public HTTPS**

Poll both `/health/live` and `/health/ready`, require HTTP 200 and `database: ok`, and verify the root HTML contains the Spina application shell.

- [ ] **Step 7: Persist non-secret evidence**

Upload a small JSON artifact containing Git SHA, Droplet ID, IPv4 address, hostname, and health status. Add the same non-secret checkpoint to Master Issue #296.

- [ ] **Step 8: Run the deployment contract**

```bash
python tools/test_digitalocean_deployment_contract.py
```

Expected: PASS.

- [ ] **Step 9: Commit the workflow**

```bash
git add .github/workflows/spina-digitalocean-deploy.yml tools/test_digitalocean_deployment_contract.py
git commit -m "ci: deploy Spina to DigitalOcean through OIDC"
```

### Task 4: Provision and rendezvous the Droplet

**Files:**
- Create temporarily: `.deploy/digitalocean-target.json`

**Interfaces:**
- Consumes: `.deploy/digitalocean-public-key.txt` written by the active workflow.
- Produces: one `sgp1` Ubuntu 24.04 Droplet with monitoring, IPv6, and the ephemeral SSH public key.

- [ ] **Step 1: Read the generated public key**

Read the deployment-branch public-key file and verify it starts with `ssh-ed25519`.

- [ ] **Step 2: Register the public key in DigitalOcean**

Create a uniquely named account SSH key and retain only its numeric ID and fingerprint as evidence.

- [ ] **Step 3: Create the approved server**

Create `spina-production-1` in `sgp1` from `ubuntu-24-04-x64` using `s-1vcpu-1gb`, monitoring enabled, backups disabled, and tags `spina`, `production`, and `fastapi`.

- [ ] **Step 4: Enable IPv6 and wait for active status**

Require the create and IPv6 actions to complete and record the assigned public IPv4 address.

- [ ] **Step 5: Form the HTTPS hostname**

Use `spina.<dashed-ip>.sslip.io` and verify that it is syntactically valid.

- [ ] **Step 6: Publish the target rendezvous**

Create `.deploy/digitalocean-target.json` on the deployment branch with only the Droplet ID, public IPv4 address, and hostname. The waiting workflow then continues.

### Task 5: Verify role access and close temporary infrastructure

**Files:**
- Delete temporarily: `.deploy/digitalocean-public-key.txt`
- Delete temporarily: `.deploy/digitalocean-target.json`
- Disable: temporary Supabase OIDC broker function
- Update: GitHub Issue #296, Notion project state, Create State

**Interfaces:**
- Consumes: deployed HTTPS application and the four isolated test accounts.
- Produces: accepted public deployment evidence with temporary secret paths disabled.

- [ ] **Step 1: Verify all four role logins**

Send login requests through the public HTTPS API for Client, Employee, Collector, and Management test accounts. Require the returned canonical role to match each account and do not persist tokens.

- [ ] **Step 2: Verify authorization separation**

Use each short-lived session to call one allowed endpoint and one forbidden cross-role endpoint. Require the allowed request to succeed and the forbidden request to return 403/404 as designed.

- [ ] **Step 3: Disable the secret broker**

Redeploy the broker with JWT verification enabled and a body that always returns 404. Confirm it no longer returns runtime values.

- [ ] **Step 4: Remove rendezvous files**

Delete the temporary public-key and target files from the deployment branch. The SSH private key exists only inside the completed GitHub runner and is destroyed with the runner.

- [ ] **Step 5: Update project tracking**

Record the final HTTPS URL, exact Git SHA, Droplet ID, health evidence, role-verification result, transitional-domain warning, and remaining domain/backup tasks in GitHub Issue #296, Notion, and Create State. Record no password, token, database URL, or private key.

- [ ] **Step 6: Final verification**

Freshly verify the HTTPS root and both health endpoints after cleanup. Do not claim completion unless the final checks pass.

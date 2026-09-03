# DigitalOcean Direct Deployment Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the Spina DigitalOcean deployment without first-boot package races and leave Management with one encrypted owner recovery key.

**Architecture:** The existing GitHub Actions workflow remains the exact-source builder and receives runtime secrets only through its validated GitHub OIDC identity. Management automation creates the approved Singapore Droplet with both a passphrase-protected owner public key and the workflow’s short-lived public key; the bootstrap waits for cloud-init/APT locks, deploys Caddy plus a loopback-only Uvicorn service, verifies all four roles, and removes the short-lived key.

**Tech Stack:** DigitalOcean Droplet, Ubuntu 24.04 LTS, OpenSSH Ed25519, GitHub Actions/OIDC, Bash, Python 3.12, FastAPI/Uvicorn, Caddy, systemd, Supabase PostgreSQL/Auth.

**Spec:** `docs/superpowers/specs/2026-09-03-digitalocean-direct-deployment-hardening-design.md`

## Global Constraints

- Monthly server size remains `s-1vcpu-1gb` at USD 6/month in `sgp1`.
- Supabase PostgreSQL and Supabase Auth remain authoritative.
- No private key, passphrase, database URL, service-role key, session token, or test password may be committed or copied into project tracking.
- Uvicorn binds only to `127.0.0.1:8000`.
- Failed or superseded Droplets and short-lived DigitalOcean account keys must be deleted.
- Completion requires fresh public HTTPS, database readiness, and four-role login evidence.

---

### Task 1: Prove first-boot lock handling

**Files:**
- Modify: `tools/test_digitalocean_deployment_contract.py`
- Modify: `ops/digitalocean/bootstrap.sh`

**Interfaces:**
- Consumes: standard Ubuntu `cloud-init`, APT, and dpkg state.
- Produces: `wait_for_first_boot_packages()` and `apt_retry()` shell functions used before package installation.

- [ ] **Step 1: Add failing contract assertions**

Require the bootstrap source to contain `cloud-init status --wait`, checks for `/var/lib/dpkg/lock-frontend`, `/var/lib/dpkg/lock`, `/var/lib/apt/lists/lock`, and `/var/cache/apt/archives/lock`, plus bounded retry logic for both `apt-get update` and `apt-get install`.

- [ ] **Step 2: Run the contract and confirm RED**

Run:

```bash
python tools/test_digitalocean_deployment_contract.py
```

Expected: failure because the first-boot wait and retry functions are absent.

- [ ] **Step 3: Implement the minimal wait and retry functions**

Add a bounded `cloud-init status --wait` call, poll lock owners with `fuser`, run `dpkg --configure -a`, and retry failed APT commands with a short delay. A timeout exits through the existing `fail()` helper.

- [ ] **Step 4: Run contract and shell checks**

```bash
python tools/test_digitalocean_deployment_contract.py
bash -n ops/digitalocean/bootstrap.sh
```

Expected: PASS.

### Task 2: Add short-lived SSH-key cleanup

**Files:**
- Modify: `.github/workflows/spina-digitalocean-deploy.yml`
- Modify: `tools/test_digitalocean_deployment_contract.py`

**Interfaces:**
- Consumes: workflow key comment `spina-digitalocean-run-${GITHUB_RUN_ID}`.
- Produces: final server `authorized_keys` without that short-lived key after deployment verification.

- [ ] **Step 1: Add a failing contract assertion**

Require a final SSH command that removes only the line containing the exact workflow key comment after public verification succeeds.

- [ ] **Step 2: Run the contract and confirm RED**

```bash
python tools/test_digitalocean_deployment_contract.py
```

Expected: failure because server-side key cleanup is absent.

- [ ] **Step 3: Add exact-comment cleanup**

After role and public health checks, run a final remote command that rewrites `/root/.ssh/authorized_keys` excluding `spina-digitalocean-run-${GITHUB_RUN_ID}`, preserves mode `0600`, and refuses to remove unrelated keys.

- [ ] **Step 4: Re-run the contract**

```bash
python tools/test_digitalocean_deployment_contract.py
```

Expected: PASS.

### Task 3: Generate and retain the owner recovery key

**Files:**
- Create locally: `/mnt/data/spina-digitalocean-owner-ed25519`
- Create locally: `/mnt/data/spina-digitalocean-owner-ed25519.pub`

**Interfaces:**
- Consumes: a cryptographically generated passphrase.
- Produces: one encrypted OpenSSH private key, public key, SHA256 fingerprint, and DigitalOcean account key ID.

- [ ] **Step 1: Generate the encrypted key**

Use Ed25519 with modern OpenSSH private-key encryption and a random passphrase of at least 24 characters. Set private-key mode to `0600`.

- [ ] **Step 2: Verify encryption and fingerprint**

Require `ssh-keygen -y` to fail without the passphrase, succeed with it, and reproduce the exact public key. Record only the fingerprint in project tracking.

- [ ] **Step 3: Register the public key in DigitalOcean**

Create the account key as `spina-owner-recovery-2026-09-03` and retain its key ID for Droplet creation.

### Task 4: Execute the clean deployment

**Files:**
- Temporary: `.deploy/digitalocean-public-key.txt`
- Temporary: `.deploy/digitalocean-target.json`

**Interfaces:**
- Consumes: active GitHub workflow public key and owner recovery key ID.
- Produces: one active Singapore Droplet and a public HTTPS Spina address.

- [ ] **Step 1: Trigger the hardened workflow**

Push the bootstrap/workflow changes on `ops/digitalocean-production` and identify the new active workflow run ID.

- [ ] **Step 2: Register the workflow public key**

Read the run-specific public key, register it in DigitalOcean, and verify its comment matches the active run ID.

- [ ] **Step 3: Create the Droplet**

Create `spina-production-1` in `sgp1` from `ubuntu-24-04-x64`, size `s-1vcpu-1gb`, monitoring enabled, backups disabled, with both owner and workflow key IDs.

- [ ] **Step 4: Enable IPv6 and publish the target**

Wait for active networking, create `spina.<dashed-ip>.sslip.io`, and write the target file containing the exact run ID, Droplet ID, public IPv4 address, and hostname.

- [ ] **Step 5: Wait for workflow completion**

Require the workflow conclusion to be `success`. On failure, inspect the exact boundary, delete the failed Droplet and short-lived key, and do not claim deployment readiness.

### Task 5: Verify roles and clean temporary access

**Files:**
- Delete: `.deploy/digitalocean-public-key.txt`
- Delete: `.deploy/digitalocean-target.json`
- Disable: temporary Supabase OIDC secret broker
- Update: GitHub Issue #296, Notion, Create State

**Interfaces:**
- Consumes: public HTTPS Spina deployment and isolated acceptance accounts.
- Produces: non-secret acceptance evidence and owner recovery material for Management.

- [ ] **Step 1: Verify public endpoints**

Require HTTP 200 from root, `/health/live`, and `/health/ready`, with `status: ready` and `database: ok`.

- [ ] **Step 2: Verify all four live logins**

Authenticate Client, Employee, Collector, and Management through the public address and require the returned canonical role to match each test identity. Discard all access tokens after verification.

- [ ] **Step 3: Verify temporary-key removal**

Confirm the workflow key is absent from `/root/.ssh/authorized_keys`, delete its DigitalOcean account key, and retain only the owner recovery key.

- [ ] **Step 4: Disable the temporary secret broker**

Redeploy it to always return 404 with JWT verification enabled and verify it no longer releases runtime values.

- [ ] **Step 5: Remove rendezvous files and synchronize tracking**

Delete both temporary branch files. Update GitHub Issue #296, Notion, and Create State with URL, exact Git SHA, Droplet ID, health status, role result, owner-key fingerprint, and remaining custom-domain/backup work—never credentials.

- [ ] **Step 6: Final fresh verification**

Re-run public root and health checks after all cleanup. Only then report the deployment as available.

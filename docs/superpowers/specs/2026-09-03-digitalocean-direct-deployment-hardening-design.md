# DigitalOcean Direct Deployment Hardening Design

## Purpose

Complete the approved DigitalOcean cutover after the first deployment attempts proved that the application build, Supabase secret boundary, and DigitalOcean SSH path work, but Ubuntu first-boot package processes can temporarily hold APT and dpkg locks.

## Approved refinement

The deployment keeps the existing GitHub Actions build and OIDC secret-delivery boundary, but adds a Management recovery path and first-boot coordination:

1. Generate one passphrase-protected Ed25519 owner key outside GitHub.
2. Deliver the encrypted private key and its passphrase only to Management.
3. Create the Droplet with both the owner public key and the workflow’s short-lived deployment public key.
4. Wait for `cloud-init` and all APT/dpkg locks before installing packages.
5. Deploy the exact Git revision, verify HTTPS, database readiness, and all four roles.
6. Remove the short-lived deployment key from the server and DigitalOcean account after acceptance; retain only the owner recovery key.

## Security boundary

- The owner private key is encrypted at rest and never committed to GitHub, Notion, Create State, Supabase, or the Droplet.
- The owner passphrase is delivered only in the Management conversation and is not copied to project tracking.
- The short-lived workflow private key exists only on its GitHub runner.
- Supabase database and service credentials continue to be released only to the exact approved GitHub workflow through short-lived OIDC validation.
- The final server exposes only SSH, HTTP, and HTTPS. Uvicorn remains loopback-only.

## First-boot behavior

The bootstrap must call `cloud-init status --wait`, then poll the known APT and dpkg lock files until no process owns them. It must run `dpkg --configure -a` before package installation and retry `apt-get update` and `apt-get install` on transient package-manager failures. A lock timeout must stop deployment without claiming readiness.

## Recovery-key behavior

The final `/root/.ssh/authorized_keys` retains the owner public key. After the public health and role checks pass, the workflow removes its own comment-tagged short-lived key from `authorized_keys`. DigitalOcean account cleanup then removes the short-lived account key while keeping the owner key registered.

## Acceptance criteria

- Ubuntu package installation does not race cloud-init or unattended upgrades.
- Public HTTPS root, liveness, and database readiness pass.
- Client, Employee, Collector, and Management each authenticate with the correct canonical role.
- The workflow key is removed from the server and DigitalOcean account.
- The encrypted owner key can be downloaded by Management and its fingerprint matches the retained public key.
- No unused failed Droplet remains billable.

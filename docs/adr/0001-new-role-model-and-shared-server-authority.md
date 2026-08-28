# ADR 0001: New Role Model and Shared Server Authority

- **Status:** Accepted as platform direction; implementation requires phased plan approval
- **Date:** 2026-08-28
- **Decision owner:** Management

SPINA will create a clean authorization model around the canonical roles
Management, Employee, Collector, and Client, with narrow server-derived
permissions and resource scopes. It will not translate `Admin`, `Encoder`,
`Viewer`, or `System` into templates, aliases, or starting permission sets. Each
legacy account will instead receive a new assignment from its real current job
responsibilities, be verified under least privilege and approved-device rules,
and then have legacy access disabled; the old identity and profile remain only
as historical cutover evidence. Supabase Auth proves identity, FastAPI enforces
authorization and device policy, and PostgreSQL holds official records and
permanent audit evidence for every platform. The current Desktop's local access
checks and direct database paths are transitional behavior to replace safely,
not architecture to copy into the current project.

## Alternatives considered

- **Map old roles to transitional permission templates:** rejected because it
  carries accidental historical access into the new system.
- **Keep separate role systems per platform:** rejected because it permits
  inconsistent authority and client-controlled access assumptions.
- **Replace every legacy account at once:** rejected because it lacks a safe,
  auditable access-validation and recovery window.

## Consequences

- A new permission catalog and role composition must be approved before account
  cutover.
- No automated rule may derive new permissions from a legacy profile.
- A temporary legacy login path can exist only for accounts not yet cut over.
- Desktop, mobile, and web clients must consume the same FastAPI authorization
  decisions and cannot become financial or permission authorities.

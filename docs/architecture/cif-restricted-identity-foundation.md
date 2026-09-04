# CIF and Restricted Identity Foundation

## Authority

PostgreSQL owns Client Information Form lifecycle, versioning, new-credit
eligibility, restricted verification metadata, and immutable access evidence.
FastAPI owns authenticated transitions and safe serialization. The portal only
renders server-authorized responses.

This foundation does not replace `lending.clients`, account registration,
loans, contract schedules, collections, remittances, or accounting.

## Ordinary CIF flow

```text
Employee/Management registered device
  -> cif.prepare
  -> versioned Draft tied to lending.clients.id
  -> Management cif.verify freezes canonical digest
  -> different Management user cif.approve
  -> client-scoped lock
  -> prior Active CIF becomes Superseded
  -> new CIF becomes Active for exactly five years
  -> public status derived as Active / Expiring / Expired
```

An open early re-verification requirement makes an otherwise current CIF
ineligible for new credit without rewriting its historical lifecycle state.
CIF status never blocks payment, correction, reversal, remittance, or statement
access for an existing obligation.

## Restricted evidence flow

```text
Management registered device
  + identity_evidence permission
  + allowlisted X-Evidence-Purpose
  + unique X-Request-Id
  -> restricted_identity repository
  -> safe metadata response
  -> immutable evidence_access_events row in the same transaction
```

Only allowlisted metadata is stored: evidence type, method, result, dates,
masked reference, approved external-object reference, SHA-256 digest, retention
class, legal-hold state, verifier/reviewer, and lifecycle state.

The application does not accept or return raw document bytes, OTPs, MPINs,
passwords, ATM details, contact lists, full National ID numbers, or arbitrary
provider payloads. Raw-file custody remains disabled until a separate encrypted
repository, DPO-approved purpose, retention policy, and operational access
review are approved.

## Exposure matrix

| Surface | Ordinary CIF | Restricted metadata | Raw evidence |
| --- | --- | --- | --- |
| Management with CIF permission | Allowed | No | No |
| Management with evidence permission and purpose | Allowed | Allowed and logged | No |
| Employee/Office with CIF permission | Allowed | No | No |
| Collector | No administration access | No | No |
| Client | No administration access | No | No |
| Contract compiler | Explicit ordinary-field allowlist only | No | No |

## Database boundaries

- `lending.client_information_forms`: versioned ordinary CIF source.
- `lending.client_cif_reverification_requirements`: early-review workflow.
- `lending.client_cif_events`: immutable lifecycle evidence.
- `lending.client_information_form_status`: deterministic status and
  eligibility projection.
- `restricted_identity.cif_verification_evidence`: metadata-only restricted
  evidence.
- `restricted_identity.evidence_access_events`: immutable purpose-bound access
  evidence.

`restricted_identity` revokes PUBLIC schema, table, sequence, and function
access. Ordinary repositories do not join it.

## Release boundary

Migration `0110` and its APIs are additive source changes only. Merging the
source does not apply the migration to production, upload real client evidence,
approve a loan, create a contract, release funds, enable GCash, or provide a
legal conclusion. Those remain separately controlled decisions.

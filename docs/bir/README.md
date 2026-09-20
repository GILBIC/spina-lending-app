# BIR registration preparation

These are public engineering drafts for Spina Priority 11, reviewed against the official-source inventory dated **20 September 2026**. They describe preparation and evidence gaps; they do not certify the software, classify a taxpayer, file an application or authorize production use.

Start with [official requirements](official-requirements.md), then the [system description](system-description.md), [technical matrix](technical-matrix.md) and [registration checklist](registration-checklist.md). Keep taxpayer facts in a private copy of [profile.example.json](profile.example.json). Preserve each reviewed candidate using [version control](version-control.md).

## Two technical outputs

1. **Accounting review ZIP:** an authorized Management user selects an inclusive date range in the existing General Journal page. The download contains posted General Journal and General Ledger data, Trial Balance, chart of accounts, scoped accounting audit, cancelled-draft evidence, a printable view and a hash manifest. It is a CSV review export, not a validated Standard Audit File (SAF), tax invoice or government submission.
2. **Offline registration draft:** [build_bir_registration_package.py](../../tools/build_bir_registration_package.py) records an exact clean source revision and explicitly supplied evidence. It does not contact a database, ORUS or another government service. Its output remains an unsigned draft with `registration_verified: false` and `filing_ready: false`.

From the clean repository checkout, choose a new directory outside the repository:

```powershell
$candidateSha = (git rev-parse HEAD).Trim()
python tools/build_bir_registration_package.py --repository . --expected-sha $candidateSha --output-dir ../bir-review-candidate
```

Optional inputs are `--profile PRIVATE_JSON`, `--evidence PRIVATE_JSON`, `--accounting-export ZIP` and `--compare-manifest PRIOR_JSON`. Supply only files that the operator is authorized to include. The output directory must not already exist. `DRAFT_PENDING_INPUTS` and `DRAFT_FOR_OWNER_REVIEW` describe input completeness only; neither means government acceptance.

The profile uses `schema_version: 1`; actual taxpayer and reviewer values begin as null. Each applicability entry (`invoice`, `saf`, `electronic_invoicing`, `sales_reporting`) starts pending. A required/not-applicable decision needs a rationale and evidence reference, with accountable review. A status alone does not establish the law's application.

Evidence JSON has this empty starting shape:

```json
{"schema_version": 1, "items": []}
```

Each supplied item has `key`, `path`, `status` and `reference`. Paths name individual files, absolute or relative to that evidence JSON. Status is `unsigned`, `signed` or `reviewed`; these are operator declarations, not authenticated signatures. Allowed keys are listed in the [checklist](registration-checklist.md). No directory ingestion is supported. Technical evidence is bounded to 25 MB per file and 64 MB total; these software limits do not make its ZIP an ORUS attachment.

Keep real profiles, taxpayer records, identity/authority documents, signed forms and financial exports outside the public repository and public CI artifacts. Use synthetic records for public examples. The current official RMO 9 form bytes remain a retrieval-and-review gate; these Markdown drafts must not be substituted for them.

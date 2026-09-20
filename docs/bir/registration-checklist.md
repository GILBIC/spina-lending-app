# Registration preparation checklist

Use this as an unsigned work list. The [official requirements](official-requirements.md) and the current BIR forms govern the actual filing. Each item requires an owner, evidence reference/hash and review date; an unchecked item stays pending.

## Initial system package

- [ ] Confirm actual legal name/address/TIN/branch/RDO, taxpayer/VAT category, system classification and in-house/provider maintenance arrangement in the private profile.
- [ ] Record separate supported decisions for invoice, SAF, electronic invoicing and electronic-sales reporting. Do not mark a missing capability not-applicable merely to complete the package.
- [ ] Retrieve the current applicable RMO 9 official checklist and Annex C/E, C-1 and B forms; retain sources, revisions and hashes. **The current Annex B/C-1 bytes are not verified here.** RMC 5 Annex B is historical reference only.
- [ ] Reconcile the [system-summary field list](system-description.md) and [technical matrix](technical-matrix.md) to those actual forms; obtain the correct accountable reviews and signatures.
- [ ] Review synthetic examples of the applicable books, principal/supplementary documents, corrections/reprints and printable audit activity. An internal receipt copy is not an approved invoice sample.
- [ ] Supply actual representative authority and parent/affiliate licensing permission where applicable; retain identity documents privately.
- [ ] Supply approved access, retention/hold, backup and recovery policies, plus actual operational evidence.
- [ ] Review the exact candidate source/version, original evidence hashes and output scope. Select the applicable submission route and prepare the actual permitted attachments. The engineering ZIP is not a direct ORUS upload.
- [ ] Only the authorized taxpayer/representative submits. Retain the genuine receipt/acknowledgement separately; do not infer registration from a successful builder run.

The initial checklist is grounded in the [2026 Citizen’s Charter, printed pages 66–68](https://bir-cdn.bir.gov.ph/BIR/pdf/BIR%20Citizen%27s%20Charter%20%282026%20Edition%29v2.pdf). These checkboxes do not reproduce its official forms.

## Sworn-statement preparation field list

Collect the declarant's actual identity and capacity; taxpayer/branch facts; system/version/module scope; maintenance/provider arrangement; applicable supporting samples and controls; evidence/review references; authorized signers; and the required execution/notarization process from the retrieved current form. Select taxpayer-only or joint-statement treatment only after reviewing the actual arrangement. This is a **field list only**: no oath/declaration wording, signature block, notarization, official form, acknowledgement or QR is fabricated.

## Explicit private evidence inputs

The offline builder accepts only these keys. A supplied `signed` or `reviewed` status is an operator declaration; it cannot authenticate the file, signer, form revision or government origin.

| Evidence key | Intended retained evidence |
| --- | --- |
| `official_sworn_statement` | Actual applicable official statement; unsigned/signed status reported honestly. |
| `official_system_summary` | Current official system-summary form, reconciled to source/system facts. |
| `official_technical_checklist` | Current official technical checklist with its accountable review/signature status. |
| `taxpayer_registration` | Actual taxpayer/branch registration evidence. |
| `authority_to_file` | Applicable representative or organizational authority. |
| `invoice_sample` | Applicable reviewed principal-document example; otherwise retain the applicability gap. |
| `supplementary_document_sample` | Applicable reviewed collection/other supplementary example. |
| `saf_assessment` | Supported applicability and format/mapping assessment. |
| `retention_policy` | Approved accounting/source-document retention and hold policy. |
| `access_policy` | Approved access/administrator/revocation policy and accountable ownership. |
| `backup_restore_evidence` | Clearly scoped synthetic or actual operational backup/restore evidence. |
| `system_flow_diagram` | Reviewed actual data/process/interface description. |
| `accountant_review` | Actual review covering classification, financial scope and outstanding requirements. |
| `submission_receipt` | Genuine submission evidence, if submission actually occurred. |
| `acknowledgement_certificate` | Genuine BIR acknowledgement, if actually issued. |
| `annual_books_qr` | Genuine ORUS annual-books registration QR evidence, if actually generated. |

Supply each file explicitly using `key`, `path`, `status` (`unsigned`, `signed`, `reviewed`) and `reference`. Relative paths resolve from the private evidence JSON. Missing evidence is recorded as missing. Even a supplied acknowledgement does not make the offline tool independently verify registration or mark a filing ready.

## Recurring books and later changes

- [ ] Establish the actual taxable-year/cessation dates and current annual-books deadline with the accountant; complete the separate ORUS books process and retain authentic QR evidence. See [annual-books rules](official-requirements.md#annual-books-registration).
- [ ] Reassess retention/holds, invoice/electronic reporting applicability and current source updates before each relevant submission or release.
- [ ] Preserve the previously submitted artifact unchanged. Compare each proposed version to it, review financial/control impacts and determine the required notification or updated registration with the responsible adviser. See [version control](version-control.md).

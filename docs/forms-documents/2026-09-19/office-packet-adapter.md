# Controlled office packet adapter

The adapter fills configured Disclosure, Agreement and Promissory Note PDF forms,
then appends one complete Annex A from the retained R2 DOCX layout. It uses the
existing schedule projection to validate the immutable approved rows. It does not
calculate a second schedule or approve legal wording, pricing, taxes or production
configuration. The counsel files remain unchanged.

`GILBIC_FIRST_LOAN_TEMPLATE_MANIFEST` points to an absolute JSON file containing:

- `version` and literal `approved_for_execution: true`, matching the separately
  registered active backend template record.
- `documents.disclosure`, `documents.agreement` and
  `documents.promissory_note`, each with an absolute PDF `path` and `sha256`.
- `annex_a.path` pointing to the original R2 DOCX and `annex_a.sha256` equal to
  `80ef81aec3141f9c96a5d78f1edd1e7367c8a6be9ab7dca92e81b07756217ddb`.
- `agreement_annex_mode: "separate_complete_annex"`. The controlled Agreement PDF
  must have its abbreviated schedule removed before registration; the complete
  attached schedule is the single contractual Annex A.
- `disclosure_rules.regular` and `disclosure_rules.seven_by_seven`, each containing
  finalized `allocation`, `post_maturity` and `interest_basis` text. Blank or
  unresolved placeholders fail. These are controlled legal disclosures, not text
  supplied by office staff at approval time.

All file hashes, the rule text, the version and Annex assembly mode enter the
template digest. The approved packet must contain that same digest. Editing any
of them requires a different controlled template registration and a fresh packet.
The adapter does not create that production registration.

The PDF forms accept supported saved packet fields only. Unknown financial
fields fail rather than inventing an EIR, tax, deduction or disclosure value. All
three forms require loan number, borrower name, principal, installment amount,
first payment date and maturity date. Final output has no editable form fields
or widget annotations. Every visible text font must be Arial and embedded; a
substitute or missing embedded resource blocks issuance.

`GILBIC_OFFICE_DOCUMENT_CONVERTER` is an absolute installed `soffice.exe` (or
platform-equivalent LibreOffice executable). Conversion uses a private temporary
directory, a separate temporary LibreOffice profile, no shell, hidden Windows
processes and a 60-second limit. Missing conversion or font support blocks
issuance. No font files are bundled or redistributed.

Regular Annex A displays **Remaining Total Payable** using the established
approved display rule. The 7x7 schedule displays **Scheduled Remaining
Principal** and prints the exact reviewed penalty-policy tuple. Missing 7x7
pricing authority blocks the document. Both retain all contractual rows and the
same version references; they are distinct from later operational schedules.

The explicit offline proof command is:

```powershell
$env:PYTHONPATH = 'gilbic_backend/src;spina_backend_mobile/src;.'
.venv/Scripts/python.exe tools/run_first_loan_document_proof.py `
  --output <private-synthetic-output-directory> `
  --converter <absolute-soffice-path>
```

It creates synthetic Regular 1/7/8/104-row and 7x7 1/104-row artifacts, checks
real embedded Arial and conversion, verifies every printed installment against
the saved projection exactly once, checks page bounds and non-editable fields,
and writes a JSON report. Its three form
fixtures explicitly say they are adapter tests and are not legal execution
templates. This command performs no database writes, signatures or release.

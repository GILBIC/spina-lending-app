## 2026-09-13 update: bounded CI setup, exact asset still required

The new `Annex A PDF proof` workflow selects only this diagnostic scope on a disposable Windows runner. It explicitly runs the 18 Arial-gate tests and the 24 template tests, converts all five fixed fixtures, checks existing schedule assertions, verifies reported Arial identity plus embedded resources, and publishes PDFs/reports/page images for separate visual review. It does not repeat the full financial/backend/mobile suites.

The original DOCX upload is **still pending**. Put the unchanged source at `tools/annex_a_pdf_proof/assets/SPINA_Schedule_of_Payments_Annex_A_R2_Black_White_Draft.docx` on `docs/forms-documents-pdf-handoff`. The preflight requires the original 73022 bytes and SHA-256 below; missing or modified input is a blocking error, not a skipped test or fallback layout. A hash in this README is not an uploaded asset.

`font_gate.py` rejects Liberation Sans, Arimo and other substitutions, empty evidence, and unembedded Arial resources. Its 18 tests passed locally after the initial 17 missing-module failures. The five previously delivered substituted-font PDFs were independently rejected. Exact-source preflight locally accepted the original and rejected missing/modified copies. YAML and inline Python syntax were checked. **Windows installation/conversion and end-to-end repository PDF proof have not run successfully yet**; no Arial-rendering or production acceptance is claimed by this setup.

The runner uses installed Arial only and a SHA-256-pinned LibreOffice 26.2.5.2 installer from The Document Foundation. Installer provenance is the x64 entry of Microsoft winget-pkgs blob `63fdc92e77144fe63f8703dc8b2027ec0372db07`. No font files are copied, committed or uploaded as artifacts. Proof dependencies are isolated from application runtime dependencies.

After a successful exact-head PDF proof, visually review all generated pages. Then add Regular's own authoritative schedule binding and product-specific tests to the shared forms, as approved; the current fixtures remain 7x7-only. Full packet, protected ownership/version binding, signatures, immutable retention and professional reviews remain open.

---

## Original recovery checkpoint (historical)

# Annex A synthetic proof: recovered diagnostic tools

PR #427, recovery import dated 2026-09-13. These four Python files are byte-for-byte copies from the delivered offline proof archive. They preserve that work in the repository; this commit does not implement production document generation.

## What is here

- `synthetic_annex_a.py`: assembles only the five fixed synthetic fixtures into the exact approved Annex A R2 layout, using the repository's signed schedule generator and read-only projection. It does not accept real loans.
- `test_synthetic_annex_a.py`: 24 explicitly invoked source/template tests. Missing source assets fail rather than skip.
- `prepare_specimen_pdf.py`: stamps metadata and normalizes less-than-one-point page-box export drift without moving or scaling document content.
- `verify_synthetic_pdfs.py`: checks the five exported PDFs for every row, totals, context/version references, page size/numbering, non-fillable output and neutral text/borders. It reports observed fonts; it does NOT enforce Arial or replace visual review.
- `source-manifest.json`: exact source archive, template and recovered code identities. This is a provenance record, not a statement that every referenced asset is committed.

## Still open in this import

The original DOCX and five sample PDF binaries are **not in this commit**. They remain in the conversation archive identified below. Do not create a new template from the Markdown review mirror, substitute a logo, change the expected source hash, or use an incomplete binary fragment.

No DOCX-to-PDF converter or PDF-proof CI job is added here. Existing SPINA CI compiles Python under `tools`; its ordinary pytest command does not include this explicitly invoked diagnostic directory. A Green for this import establishes repository compatibility only, not execution of these 24 tests or PDF acceptance.

Prior offline evidence recorded 24 passing focused tests, five sample PDFs containing 180 installments across 15 pages, and separate visual inspection. That evidence is historical, not a new CI result. The converter substituted Liberation Sans for Arial. Exact Arial rendering remains unverified; reporting `fonts_observed` is not a font-acceptance gate.

Full A01-A12 application acceptance, protected borrower/CIF/signed-version binding, Regular mapping, other scheduled charges, real signature evidence, immutable storage, audit, retrieval and existing professional reviews remain open. Non-fillable does not mean immutable. Fixture prices are not approved live-loan pricing. No penalty is enabled.

## Exact external source

Archive: `SPINA_Annex_A_Synthetic_PDF_Proof.zip`, 392590 bytes.

SHA-256: `b38689bb928d4bff124088b4834251203c27612dd54f07fe99a794b10d3f3145`.

Member: `Source_Template/SPINA_Schedule_of_Payments_Annex_A_R2_Black_White_Draft.docx`, 73022 bytes.

Template SHA-256: `80ef81aec3141f9c96a5d78f1edd1e7367c8a6be9ab7dca92e81b07756217ddb`.

Expected template Git blob: `4426f2cccb23de6609c66c9e781d784ce825c448`. This identity is not evidence that the blob exists remotely.

## Explicit local use

Use a checkout of this PR and the exact external source; never supply live borrower data. The recorded proof environment used Python, python-docx and PyMuPDF. Install proof-only dependencies into an isolated environment rather than changing runtime dependencies.

Set `SPINA_ANNEX_TEMPLATE` to the absolute original DOCX path. Add `gilbic_backend/src` and `tools/annex_a_pdf_proof` to `PYTHONPATH` using the operating system's path separator.

```text
python -m pytest -q tools/annex_a_pdf_proof/test_synthetic_annex_a.py
python tools/annex_a_pdf_proof/synthetic_annex_a.py --template <exact-source.docx> --output-dir <new-specimen-directory>
```

Export all five specimen DOCX files with the separately verified converter. Do not overwrite the source or existing proof outputs. Then use `prepare_specimen_pdf.py <export.pdf> <new-final.pdf>` and:

```text
python tools/annex_a_pdf_proof/verify_synthetic_pdfs.py --pdf-dir <final-pdf-directory> --report <new-report.json>
```

The PDF verifier is exporter-sensitive because it checks extracted row text. A different converter requires fresh fixture verification, not weakened assertions. Review every rendered page and the actual embedded font identities.

## Resume next

Import the full hash-matching original DOCX as a repository asset, then add a bounded font-controlled conversion/verification job without duplicating the existing full CI suite. Prove Arial rather than accepting silent substitution. Do not distribute font files. Preserve #420 onboarding and #426 schedule/accounting ownership. Keep PR #427 Draft and unmerged; no production action is authorized.

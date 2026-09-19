# T02 / T03 controlled formatted draft assets

These are the exact Word copies delivered in the 16 September 2026 forms package:
Cash Loan Agreement R4 and Loan Disclosure R3. They remain **drafts, not
production-cleared or ready for signing**. Registering assets is not a completed
renderer, autofill endpoint or authorized issuance workflow.

`manifest.json` pins each delivered file, its existing review-text candidate and
the original layout source. The historical September 12 source package and
review mirrors are unchanged; they are not overwritten or duplicated here.
Original package member paths are provenance references, not repository paths.

The six focused tests in
`gilbic_backend/tests/test_loan_document_tax_docx_assets.py` compare the complete
paragraph/table content with the corresponding approved text candidate, check
file identities, Folio dimensions, the original logo, Arial specification and
dynamic page fields. They use only the Python standard library plus the existing
pytest runner; no new workflow or dependency is needed.

The only additional Word-body paragraph is T02's existing assembly warning. Its
abbreviated historical Annex illustration must be replaced by **one complete
product-specific Annex A** before signing. Do not issue two competing schedules
or treat the historical balance label as a replacement for the approved Regular
Remaining Total Payable display.

DST remains itemized upfront and GRT within the agreed repayments. Repeated
disclosures refer to one charge. Amount Financed and EIR retain their separate
approved meanings. Existing `loan_document_tax_breakdown` validates supplied
arithmetic, not legal applicability, ownership or source authorization. This
asset import does not compute taxes, alter pricing or schedules, or post money.

Remaining integration: authenticated Client/CIF/loan/approval/schedule/tax source
binding, populated packet assembly, pinned rendering and final visual review,
applicable pricing/EIR/early-settlement checks, signing, immutable storage,
audit and authorized retrieval. The normal company/privacy/professional review
gates remain. Draft placeholders and internal instructions cannot be mistaken
for final borrower data or completed approvals/signatures/cash receipts.

The earlier package review used an Arimo fallback. This local re-render used
Liberation Sans: all eight Agreement pages and five Disclosure pages were
inspected, with no clipped or overlapping text observed. The DOCX source page
size remains exactly 8 x 13 inches; the local preview PDF measured approximately
575.46 x 936 points. These are preview observations, not pinned rendering proof.
Arial is specified in the Word sources. No font files are redistributed, and
populated final output still needs the pinned Arial/LibreOffice check and fresh
visual inspection.

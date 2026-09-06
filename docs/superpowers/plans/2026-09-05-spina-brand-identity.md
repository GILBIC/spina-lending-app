# SPINA Brand Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standardize the existing Web SPINA `S` mark as the canonical company logo and carry the approved placeholder brand identity consistently across product surfaces.

**Architecture:** Keep one canonical vector logo source in version control, with Web referencing it directly and other surfaces consuming derivatives without redrawing the mark. Branding configuration stays separate from authentication/business logic.

**Tech Stack:** SVG, vanilla Web assets, Flutter assets, Python/Desktop assets, HTML email templates, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-05-spina-brand-identity-design.md`

## Global Constraints

- Preserve the recognizable pink rounded-square `S` concept from `spina_portal/assets/spina-icon.svg`.
- Company name: `SPINA Lending Company`.
- Placeholder site: `spina.com.ph`.
- Placeholder email: `spinalendingcompany@gmail.com`.
- Sender display name: `SPINA Lending Company`.
- Do not embed secrets or environment-specific credentials in assets.
- Brand cleanup must not alter financial/business behavior.
- Implement after the Client credential/security path is green.

---

### Task 1: Canonicalize the Web SVG

**Files:**
- Modify: `spina_portal/assets/spina-icon.svg`
- Add/modify portal asset tests.

- [ ] Write RED asset test for stable `viewBox`, single canonical gradient `S`, and parseable SVG.
- [ ] Verify RED if cleanup contract is not yet met.
- [ ] Clean SVG whitespace/geometry and optical centering without replacing the symbol.
- [ ] Verify GREEN and portal build success.

### Task 2: Adopt canonical asset across Web brand lockups

**Files:**
- Modify: `spina_portal/index.html`
- Modify Web CSS only where spacing is required.
- Add/modify portal tests.

- [ ] Write RED test that all primary Web brand lockups reference the canonical asset and approved company name.
- [ ] Verify RED.
- [ ] Update references/spacing while preserving existing layout behavior.
- [ ] Verify GREEN.

### Task 3: Add branded credential-email presentation

**Files:**
- Modify credential-email module created by the Client credential plan.
- Add email-template tests.

- [ ] Write RED tests for `SPINA Lending Company`, `spina.com.ph`, `spinalendingcompany@gmail.com`, and graceful fallback when images are blocked.
- [ ] Verify RED.
- [ ] Add canonical logo/fallback lockup to HTML email without embedding secrets.
- [ ] Verify GREEN.

### Task 4: Carry canonical logo to Mobile

**Files:**
- Add canonical/derived Flutter asset.
- Modify `pubspec.yaml` if required.
- Modify shared SPINA brand header widgets rather than per-page redraws.
- Add Flutter tests.

- [ ] Write RED widget/asset tests for canonical SPINA mark usage.
- [ ] Verify RED.
- [ ] Replace hand-drawn/text-only `S` brand marks with canonical asset where appropriate.
- [ ] Verify Flutter GREEN.

### Task 5: Carry canonical logo to Desktop/reports incrementally

**Files:**
- Modify shared Desktop brand/report asset helpers discovered during implementation.
- Add focused tests where available.

- [ ] Identify the single shared Desktop/report brand path rather than changing unrelated screens one by one.
- [ ] Add RED test or deterministic asset check before production change.
- [ ] Introduce canonical derivative with no business-logic change.
- [ ] Verify existing Desktop/report tests.

### Task 6: Exact-head visual/asset verification

- [ ] Run portal build/tests and Flutter tests.
- [ ] Verify SVG parses and no stale duplicate SPINA logo source remains in active product paths.
- [ ] Review screenshots/build only for visual consistency; do not use screenshot approval as a substitute for automated tests.
- [ ] Update PR, GitHub #296, Notion, and Create State with exact evidence.
- [ ] Do not merge without explicit approval.

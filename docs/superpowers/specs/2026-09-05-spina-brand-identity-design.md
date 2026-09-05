# SPINA Brand Identity Design

## Purpose

Clean and standardize the existing Web SPINA mark as the canonical company logo without redesigning its recognizable concept. The current portal asset `spina_portal/assets/spina-icon.svg` is the reference: a rounded square with a pink gradient stylized `S`.

## Approved brand placeholders

- Company name: `SPINA Lending Company`
- Website/domain placeholder: `spina.com.ph`
- Email placeholder: `spinalendingcompany@gmail.com`
- Email sender display name: `SPINA Lending Company`

These values are placeholders/configuration, not hard contractual identifiers. Business logic must not depend on the literal domain or Gmail address.

## Canonical logo

The current portal logo remains the design source. Cleanup may:

- normalize SVG geometry/viewBox and whitespace;
- remove unnecessary decorative noise that does not contribute to the recognizable `S` mark;
- improve optical centering and consistency at small icon sizes;
- preserve the pink SPINA visual language and rounded-square silhouette;
- provide the same canonical asset or generated derivatives for Web, Mobile, Desktop, email templates, receipts, and future company documents.

Cleanup must not replace the logo with a new unrelated symbol or wordmark.

## Asset strategy

- Keep one canonical vector source under version control.
- Web references the canonical SVG directly where practical.
- Mobile/Desktop raster or platform-specific icons are generated from the canonical vector rather than independently redrawn.
- Email uses a lightweight compatible version and must still render acceptably if remote images are blocked.
- Do not embed secrets or environment-specific URLs in image assets.

## Email presentation

Authentication/account emails should render as SPINA, not as generic Supabase branding. The application credential-email layer uses the sender display name `SPINA Lending Company` and current placeholder mailbox `spinalendingcompany@gmail.com`. If Supabase Auth system emails remain enabled for other flows, custom SMTP/templates should be configured later so those messages also use SPINA branding instead of `Supabase Auth <noreply@mail.app.supabase.io>`.

## Delivery order

Brand cleanup is independent of the Client credential lifecycle. It should be implemented in a separate focused change after the account-security path is green, so visual asset changes cannot mask or block authentication/security review.

## Testing

- Portal tests/build verify the canonical logo path resolves and no stale duplicate logo reference is introduced.
- Asset validation confirms the SVG parses and retains a stable viewBox.
- Email-template tests verify company name, placeholder site/email, and accessible text/fallbacks without asserting on SMTP secrets.
- Cross-surface adoption occurs incrementally; each surface keeps its existing functional behavior while swapping to the canonical asset.

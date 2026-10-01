# Consented Spina screen viewing

Status: implementation authorized by the owner's request to continue technical work and literal live-screen mirroring, 2026-10-01. This implements viewing, not account impersonation or a broad grant of business permissions.

## User outcome

Management chooses another account's registered device and requests to view its Spina screen. The named account holder explicitly accepts. Both see that sharing is active and can stop. Accounts and existing roles remain separate. No capture starts merely because Management requests it. This is near-live viewing (at most one image per second), without remote input, audio, recording, history or download controls.

Keep the existing UI except the small request, consent, viewer and Stop controls. The separate unshipped Management layout restoration is outside this change. Deferred business/legal/tax/GCash work stays excluded.

## Privacy and boundaries

Only explicitly audited Spina daily-work content may be captured. Login/security/credential issuance, identity and proof media, document/file/native picker screens and the viewer itself are excluded. Unknown surfaces default to excluded. A sensitive transition invalidates pending captures synchronously and ends sharing before content can be transmitted. Navigation between eligible surfaces invalidates the capture generation before rendering the new surface. Never capture the entire Flutter application or a whole desktop/window as a fallback.

Native captures an audited `RepaintBoundary` subtree; dialogs, unknown routes, backgrounding, session/scope change and logout invalidate the capture. Web requires actual browser Element Capture restricted to `#role-content`, self-tab verification through Capture Handle, and completed restriction before any frame is encoded/uploaded. Runtime unsupported or failed restriction means unavailable, with no broad-capture fallback. Browser permission requires the holder's gesture. No DOM reconstruction substitute. The app Stop control is outside the captured content.

Consent binds exact viewer and holder users and registered devices. The requester must currently have Management role and `screen_share.view` permission. Holder rights derive only from participation. Both accounts and devices are rechecked at every operation. Disabled/revoked accounts/devices and removed viewer permissions end access. Clients never receive another account's bearer token.

## Shared HTTP contract

Base `/api/v1/screen-shares`; normal `Authorization: Bearer ...` and `X-Device-Id` headers; never credentials in URLs. All responses, including errors and images, are `Cache-Control: no-store`.

`Session` JSON (returned directly by mutation/status endpoints):

```
{id, state, generation, viewer_user_id, viewer_device_id, viewer_name,
 holder_user_id, holder_device_id, holder_name, created_at, expires_at,
 lease_expires_at, ended_reason}
```

IDs are UUID strings, timestamps UTC ISO strings, `lease_expires_at`/`ended_reason` nullable. `state` is `pending`, `active`, `stopped`, `declined` or `expired`; generation is a positive integer. All terminal transitions increment it and clear the retained image. Restart expires outstanding sessions; it never resurrects consent.

| Method/path | Request | Response/authority |
| --- | --- | --- |
| GET `/targets` | none | `{targets:[{user_id, device_id, display_name, device_name}]}`; Management plus permission only, active accounts/devices other than viewer's own account, bounded 100 results |
| POST base | `{holder_user_id, holder_device_id}` | 201 Session; requester identity/device derived server-side |
| GET `/pending` | none | `{sessions:[Session]}`; exact holder device only |
| GET `/{id}` | none | Session; exact participant only |
| POST `/{id}/accept` | `{generation}` | Session; exact holder pending request, accept once |
| POST `/{id}/decline` | `{generation}` | Session; exact holder pending request |
| POST `/{id}/stop` | `{generation}` | terminal Session; either participant; repeated stop harmless |
| PUT `/{id}/frame` | binary PNG; `X-Screen-Share-Generation`, `X-Screen-Share-Sequence` | 204; holder active grant only; increasing sequence |
| GET `/{id}/frame` | none | 200 PNG plus both generation/sequence headers, or 204 if no fresh image; active viewer only |

Client errors: 404 unrelated identity/device; 403 authorization failure; 409 invalid/terminal generation or state; 413 oversized frame; 422 malformed frame/request; 429 rate/cap limit. Clients clear their image and stop on authentication, authorization, terminal or protocol failure. Viewer must discard responses after local Stop/navigation/disposal and from old session generations. If no new image arrives within 3 seconds, clear the displayed image and show a waiting/ended state; never leave stale pixels visible indefinitely.

## Bounds and implementation

- Pending request expiry: 60 seconds. Active absolute limit: 600 seconds after acceptance.
- Active lease: 15 seconds, renewed only by an accepted new frame. No automatic reconnect/resume after expiry.
- Latest image only; expires after 3 seconds. At most 1 accepted frame per second per session.
- Noninterlaced 8-bit RGB/RGBA PNG only, at most 524288 bytes and at most 1024 pixels per dimension. Validate exact scanline sizes and filter bytes; reject APNG and unknown critical chunks. Clients target maximum 720-pixel long edge and drop overlarge images. Exactly one in-flight capture/upload; no queue/retries of stale frames.
- At most 2 active sessions hostwide; one pending/active session per viewer device and holder device. Request rate at most 3 requests per viewer per minute. Bound pending rows and target enumeration.
- Private SQL migration 0134 stores session/audit metadata only. No image bytes, screen text, hashes, secrets or tokens in SQL, logs or disk. Direct client roles have no table access. The new narrow view permission goes to Management only.
- Process-local cache retains at most approximately 1 MiB of encoded images. Expired bytes are actively evicted by a lightweight process timer, as well as before reads. No infrastructure/service purchase, capture SDK or third-party media relay.
- SQL transactions lock participants/devices and session consistently. A process lock serializes retained-frame changes and terminal transitions. Authentication happens before taking it. Stop acknowledged means subsequent operations cannot deliver or republish frames; previously delivered network data cannot be recalled.
- Use existing single-worker deployment, and document this operational limit. A process instance identifier invalidates rows belonging to an earlier server process without assuming an active session survives restart.

## Acceptance

Automated checks must cover wrong roles/accounts/devices, permission and device revocation, consent/expiry, Stop against late upload/read, stale sequence/generation, request/frame size/rate/cap limits, process restart and image eviction, SQL direct-client denial, no private frame persistence and unknown/sensitive route exclusion. Real disposable PostgreSQL checks cover atomic transitions. Web tests use synthetic content; browser capture support must be proved with harmless content before claiming platform acceptance. Android tests cover capture cancellation after dialog/navigation/background/logout and buffer disposal. A small synthetic load check establishes the bounded polling cost. User/device/browser acceptance must be labelled untested until observed; do not equate unit tests with actual capture acceptance.

The owner explicitly deferred the harmless browser capture check on1October (“I'll test it later”). Automated implementation and review continue; actual browser/Windows capture acceptance remains pending.

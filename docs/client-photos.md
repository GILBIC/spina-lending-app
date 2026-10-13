# Client photos

Office Staff and Management with `client_onboarding.requirement.review` can add or replace a client portrait from the selected client's CIF screen on Web and Android. Choose a file/gallery picture or use the camera, review the preview beside the client name, and save. Browser camera capture depends on device/browser support.

Management can also open **Client photo** from an existing loan in Loan Portfolio. Users who already have Area Management borrower-search access can find any existing client by name or code and open the same photo controls there, including clients with neither a loan nor an intake. Photo upload still requires the office photo permission above; area assignment permission alone does not grant it. A saved CIF, loan, intake or linked Client account is not required to store a client's photo.

Collectors can view photos from the current route's client details. Linked client accounts can view their own photo. Missing photos are optional and never block lending or payments. A portrait does not mark CIF liveness, face matching or identity verification as passed.

JPEG and PNG inputs are limited to 5 MiB, one frame, 24 megapixels and 8,192 pixels per side. The server applies camera orientation, reduces the longest side to at most 1,600 pixels, and stores a JPEG containing pixels only, without EXIF/GPS metadata. The original file is not retained on the server.

Each saved version retains its uploader and server timestamp in private database storage. Replacement appends history and an audit record; prior bytes are not exposed by the current-photo API. Authenticated reads check current client ownership or collector route/delegation scope. Responses prohibit caching. Direct anonymous and client database roles cannot read the table.

An uncertain upload keeps its original request ID, expected version and input bytes for an identical retry while the screen/session remains active. A retry cannot create a duplicate or bring back an old version. Conflicting replacements require refreshing the current photo before explicitly saving again. Ending the authenticated session clears private data; this feature does not introduce an offline upload queue.

## Delivery

Apply `gilbic_backend/sql/0143_add_private_client_photos.sql` after the existing migrations, then deliver the backend before clients that use the new endpoints. The migration is additive and preserves all lending, financial and liveness records. It stores private image bytes in PostgreSQL, so the existing private database backup/storage controls apply; no new public object store is required.

The API supports `/api/v1/clients/{client_id}/photo` and the equivalent `/api/mobile/v1` paths. GET returns current metadata (or `photo: null`). POST accepts raw image bytes with `request_id` and `expected_version` query parameters. A successful retry returns current metadata, which may represent a newer photo saved afterward. The authenticated `photo/content?photo_id=...` endpoint serves only the current version.

## Verification

Run `python tools/run_client_photo_disposable_postgres_validation.py --database-url <loopback-test-url>` with `SPINA_ALLOW_DISPOSABLE_DATABASE=1`. It creates a fresh synthetic database, replays migrations through 0143, runs image/API/database tests, then drops only that generated database. Web verification uses `npm test`; Android uses `flutter analyze` and `flutter test` in `gilbic_mobile`.

Camera hardware, installation and production deployment require separate release acceptance. Local automated tests do not establish that those steps have happened.

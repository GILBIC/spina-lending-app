# Gilbic collection contract version

Current version: `gilbic-collection-v1`

Gilbic sends this value in the `X-Gilbic-Contract-Version` header for collection submissions. FastAPI should reject unsupported versions with a stable machine-readable error instead of interpreting an unknown payload shape.

A future breaking request or response change must use a new contract version. Additive optional response fields do not require a version change when older mobile clients can safely ignore them.

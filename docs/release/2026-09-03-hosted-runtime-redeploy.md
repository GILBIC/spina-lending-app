# Hosted runtime redeploy

Management connected the Spina Vercel project to the company Supabase project on 2026-09-03 and added the required runtime variables.

A fresh deployment is required because Vercel applies changed environment variables only to new deployments.

Verification gate:

- `/health/live` returns 200;
- `/health/ready` returns 200 with `database: ok`;
- Client, Employee, Collector, and Management authentication is verified;
- no secret values are committed to GitHub.

A new Preview deployment was triggered from `mvp/cross-platform-four-role` after Management confirmed that `POSTGRES_URL` was saved. This checkpoint verifies the Preview environment rather than the older `main` production deployment.

Management then removed the literal square brackets around the database password. This commit triggers a fresh Preview deployment so the corrected `POSTGRES_URL` can be verified without exposing its value.

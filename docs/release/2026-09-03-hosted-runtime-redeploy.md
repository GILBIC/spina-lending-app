# Hosted runtime redeploy

Management connected the Spina Vercel project to the company Supabase project on 2026-09-03 and added the required runtime variables.

A fresh deployment is required because Vercel applies changed environment variables only to new deployments.

Verification gate:

- `/health/live` returns 200;
- `/health/ready` returns 200 with `database: ok`;
- Client, Employee, Collector, and Management authentication is verified;
- no secret values are committed to GitHub.

A new Preview deployment was triggered from `mvp/cross-platform-four-role` after Management confirmed that `POSTGRES_URL` was saved. This checkpoint verifies the Preview environment rather than the older `main` production deployment.

Management then removed the literal square brackets around the database password.

Management has now replaced the database address with the Supabase Shared transaction pooler URI on port 6543. This commit triggers a fresh Preview deployment to verify the corrected IPv4-compatible serverless connection without exposing any credential value.

# Hosted runtime redeploy

Management connected the Spina Vercel project to the company Supabase project on 2026-09-03 and added the required runtime variables.

A fresh deployment is required because Vercel applies changed environment variables only to new deployments.

Verification gate:

- `/health/live` returns 200;
- `/health/ready` returns 200 with `database: ok`;
- Client, Employee, Collector, and Management authentication is verified;
- no secret values are committed to GitHub.

Latest redeploy trigger: 2026-09-03 11:00 Asia/Manila.

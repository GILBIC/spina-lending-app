# Hosted runtime redeploy

Management connected the Spina Vercel project to the company Supabase project on 2026-09-03.

This checkpoint triggers a fresh deployment so the hosted FastAPI runtime can load the new database and authentication environment variables.

Release acceptance requires:

- `/health/live` returns 200;
- `/health/ready` returns 200 with `database: ok`;
- Client, Employee, Collector, and Management authentication is verified;
- no secret values are committed to GitHub.

# Infrastructure security notes

**Review date:** 2026-10-26. This is a repository/configuration review, not a production certification. Refer to [`PRODUCTION_HARDENING.md`](PRODUCTION_HARDENING.md) for release steps and [`AUDIT_AND_REPAIR_REPORT.md`](AUDIT_AND_REPAIR_REPORT.md) for measured checks.

## Current repository evidence

- The repository contains API, research-frontend and admin-frontend Dockerfiles. The API image creates a non-root `app` user. API image and Compose healthchecks now use `/readyz`; `/health` remains a liveness endpoint.
- Compose mounts `api-data` at `/app/data`, where the single API replica stores uploaded evidence and Chroma indexes. The volume must be backed up and restore-tested. This local vector/evidence state is not safe for multiple API replicas or Vercel serverless functions.
- Both Next.js frontends have same-origin server-side auth/BFF routes. Compose provides `BACKEND_INTERNAL_URL` for internal API access and a separate browser-facing `NEXT_PUBLIC_API_BASE_URL`.
- Production readiness fails unless required secret/auth/MFA/provider settings, explicit origins, shared rate limits and Supabase migrations/connectivity are present. It intentionally returns not-ready for Vercel because evidence files/vector state are ephemeral there.
- `.gitignore` and `.dockerignore` exclude `.env` and `.env.*` while retaining `.env.example`; these are not a substitute for managed secrets or secret scanning.
- Main and admin frontends each report **zero npm audit vulnerabilities** in the latest captured full dependency audit. Python dependency findings are being remediated in this branch; check the final audit report for the retest result.
- GitHub Actions checks backend tests/Python dependency audit and frontend install/typecheck/lint/build/npm audit; it does not deploy production or establish remote host security.

## Validation limits and deployment controls

- The environment does not have Docker or a Docker daemon. `docker compose config`, image builds, container health, TLS proxy behavior, volume persistence, and restore tests were therefore not executable here. The deployment pipeline must run them before release.
- No live Supabase project, production secret manager, Vercel configuration, DNS/TLS endpoint, or production data was accessed or modified. Apply and review SQL migrations against a backed-up staging project first.
- Production Compose must keep the API at one replica while evidence files and Chroma use local `api-data`; use a shared durable object/vector service before horizontally scaling API instances.
- Put the service behind a maintained TLS reverse proxy, restrict direct API-port exposure, set exact `TRUSTED_PROXY_IPS` and HTTPS origins, and test request/body/time limits. Do not route large evidence uploads through Vercel serverless BFF limits.
- Dependency audit gates do not replace image scanning/SBOM, source licensing review, or independent application penetration testing.

## Release commands

```bash
# After production secrets and ordered Supabase migrations are provisioned:
docker compose config
docker compose up --build -d
docker compose ps
curl --fail https://api.example.com/readyz
```

Do not route user traffic until `/readyz` returns 200, authenticated BFF flows pass, evidence survives an API restart, configured backups restore successfully, and protected routes reject invalid/no-cookie/CSRF-invalid requests.

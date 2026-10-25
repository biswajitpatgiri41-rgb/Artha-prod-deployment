# Security architecture and current review

**Reviewed:** 2026-10-26. This is a code/configuration review, not a penetration test or a certification. The branch implements a hardened single-tenant administrator deployment profile; external production secrets, database migration state, host security, and runtime behavior must still be verified by the operator. See [`PRODUCTION_HARDENING.md`](PRODUCTION_HARDENING.md) for the release procedure and [`AUDIT_AND_REPAIR_REPORT.md`](AUDIT_AND_REPAIR_REPORT.md) for test evidence.

## Architecture and controls

- **Frontend:** the research and admin UIs use Next.js same-origin BFF endpoints for privileged actions. Access/refresh tokens remain in HttpOnly cookies, server-side handlers inject authorization to FastAPI, and cookie-authenticated mutations require a CSRF token. The admin route group validates the session server-side.
- **Backend authentication:** production admin login validates the Argon2id password and TOTP code. Access sessions are stored by hash in Supabase, carry role/tenant/permission/MFA claims, and can be revoked centrally. The production session store fails closed if it is unavailable.
- **Authorization:** protected research/evidence/admin and data mutation routes apply backend permission/role dependencies; research records are tenant-scoped. The only currently provisioned account is environment-based and single-tenant. There is no self-service account lifecycle or tested general-purpose multi-tenant onboarding.
- **Abuse/cost controls:** a shared Postgres RPC throttles admin login attempts. A second shared RPC limits assistant, research, upload, and admin operations across API workers using an HMAC of the client address and route scope. Assistant calls are bounded by the configured per-minute LLM quota. Readiness requires rate limiting to remain enabled and the required tables to exist.
- **Data:** Supabase stores canonical macro observations, upload provenance, research records/events/reports, sessions, and rate-limit windows. The API's evidence originals/metadata and Chroma vector index still use the API filesystem. They persist across restarts only on the Compose `api-data` volume; they are not durable/shared on Vercel or across multiple API replicas.
- **Transport and browser controls:** CORS uses an explicit allowlist and does not allow credentialed cross-origin cookies. API responses include security headers, validation errors omit rejected values, and the API trust-proxy logic accepts forwarded client IPs only from configured peers.

## Current risks and release requirements

| Area | Current status | Required control before wider rollout |
|---|---|---|
| Single-admin access | Production TOTP, password hashing, server-side sessions, role/permission checks, BFF cookies and CSRF are implemented. | Provision secrets securely; verify each protected path and session revocation in the target environment. |
| Multi-tenant isolation | Research records are tenant-scoped, but deployment/account provisioning is single-tenant. Evidence remains run-scoped on a shared API filesystem. | Build per-user account lifecycle and tenant ownership for evidence/data; do not onboard untrusted tenants before tests demonstrate isolation. |
| API abuse | Selected expensive mutations have shared DB-backed limits. They are IP/route scoped, not a mature per-customer quota/billing system. | Load-test the DB RPC and proxy chain; configure reverse-proxy request/body/timeouts and alert on 429/503 spikes. |
| Evidence data | Local disk plus persistent Chroma works in a single-volume deployment. | Use encrypted volume backups, test restores and retention. Do not use Vercel or multiple API replicas for evidence until object/vector persistence is moved to shared durable storage. |
| Upload security | Extension/MIME/size/parser bounds and authenticated permissions exist. | Add malware scanning/parser isolation and test the actual production reverse-proxy size/time limits. |
| Data integrity | Provenance and validations exist for macro uploads; the research panels contain overlapping snapshots and revised-history limitations. | Apply migrations; review source licensing, source checksums, release vintages, retention and authorized replacement controls. |
| Supply chain | Main and admin frontend dependency audits report zero vulnerabilities at this verification. CI also runs Python dependency audit. | Preserve CI gates, review new advisories continuously, and scan built container images/SBOMs in the deployment pipeline. |
| Operations | `/readyz` fails closed for required production secrets, model provider, Supabase/migrations, explicit origins, enabled rate limits and Vercel's ephemeral evidence storage. | Configure HTTPS/reverse proxy, backups/restore, monitoring, incident response and run authenticated smoke tests. The deployment was not changed in this task. |
| Model and policy claims | Forecast/scenario artifacts have research limitations; scenario sensitivities are illustrative/non-causal. | Do not use as official policy recommendations; validate point-in-time performance and calibrate uncertainty independently. |

## Security-sensitive release procedure

1. Apply the ordered SQL migrations in `supabase/migrations/`, including shared auth sessions and both rate-limit migrations, after reviewing and backing up the target Supabase project.
2. Provision `JWT_SECRET_KEY`, server-only Supabase key, Argon2id `ADMIN_PASSWORD`, `ADMIN_TOTP_SECRET`, `NVIDIA_API_KEY`, exact HTTPS CORS origins and trusted proxy IPs in a secret manager. Keep `ADMIN_DEV_BYPASS` false.
3. Use the persistent Docker Compose deployment for evidence workflows. Verify `/readyz` returns 200 and Docker health reports healthy. Vercel production deliberately returns not-ready because local evidence/vector state is ephemeral.
4. Exercise no-cookie denial, missing-CSRF denial, TOTP login, role denial, tenant-scoped research retrieval, login/API throttling, logout revocation, file persistence across restart, retention cleanup and volume restore.
5. Run backend tests, both frontend typecheck/lint/builds/audits, Docker image builds, compose validation and a security review in a Docker-enabled CI/release environment.

## Verification boundary

Code tests and frontend build/audit results are recorded in the audit report. This environment did not apply database migrations to a live Supabase project, set production secrets, build Docker images, run restore drills, or deploy the code. `/readyz` is an executable release gate; it does not certify economic validity, multi-tenant readiness, reverse-proxy configuration, or operational recovery.

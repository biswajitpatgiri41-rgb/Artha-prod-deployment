# Production hardening and deployment runbook

This is the release procedure for the hardened single-tenant administrator deployment. It is not a claim that any external production service was configured or that a release was deployed.

## Production security implemented in this branch

- Research and admin Next.js frontends authenticate through same-origin server-side BFF routes. The browser never receives access or refresh tokens; tokens are stored in HttpOnly cookies and forwarded to FastAPI by the frontend server.
- POST/DELETE calls that use the cookie session require a double-submit CSRF header. Cookie settings are Secure in production and SameSite=Lax.
- FastAPI applies role/permission checks to protected research, evidence, data-upload, and admin operations. Research records are fetched and written within the authenticated tenant scope.
- Production login requires a valid TOTP code. Access sessions are backed by a shared Supabase table and are revocable across API instances. A Postgres RPC applies an atomic five-attempt-per-minute login limit across workers.
- Supabase migrations provide durable research records/events/reports, macro observations and source-upload provenance, shared sessions, and shared login/API throttling. Service-role tables/functions are not granted to browser roles.
- `/health` is liveness. `/readyz` is the deployment gate: in production it checks required secrets, explicit CORS origins, model-provider configuration, Supabase connectivity and required tables. It returns 503 when incomplete and deliberately rejects Vercel production because local evidence files and vector indexes are ephemeral there.
- Both frontend lockfiles now pass `npm audit --audit-level=high`; the tested Next.js/Tailwind/ECharts upgrades are included in the code branch.

## Required secret configuration

Set these values in the hosting secret manager, never in source control or browser-visible variables:

- `ENVIRONMENT=production`.
- `JWT_SECRET_KEY`: at least 32 high-entropy characters (prefer 32 random bytes encoded as base64/hex). Rotate by an explicit session-revocation plan.
- `SUPABASE_URL` plus `SUPABASE_SECRET_KEY` (or the legacy `SUPABASE_SERVICE_ROLE_KEY`). Use the server-only key; never use the Supabase anon key for server persistence.
- `ADMIN_EMAIL`, an Argon2id `ADMIN_PASSWORD` hash, and a unique Base32 `ADMIN_TOTP_SECRET`. Set `ADMIN_ROLE=SUPER_ADMIN` only for the designated system owner. Keep `ADMIN_DEV_BYPASS=false`.
- `NVIDIA_API_KEY` and the intended supported `NVIDIA_MODEL` for LLM-backed agent/assistant features.
- `CORS_ALLOWED_ORIGINS` as an explicit JSON array of the browser-facing HTTPS frontend and admin origins; no wildcard.
- `NEXT_PUBLIC_API_BASE_URL` is the browser-facing FastAPI URL. `BACKEND_INTERNAL_URL` is the backend address reachable by the frontend server-side BFF. These can differ (for example, `https://api.example.com` vs. `http://api:8000`).
- Set `TRUSTED_PROXY_IPS` only to exact reverse-proxy addresses you control. Forwarded client IP headers are ignored from other peers.

Generate a JWT signing value with `openssl rand -base64 32`. Generate a TOTP seed once with `python -c 'import base64,secrets; print(base64.b32encode(secrets.token_bytes(20)).decode().rstrip("="))'`; provision that seed to the administrator's authenticator using a trusted enrollment method, then place it in the secret manager. Do not paste the seed into tickets, source code, or logs. Hash the admin password with the repository's Argon2 helper before setting `ADMIN_PASSWORD`; never store the cleartext password in deployment variables.

## Database and persistent storage

1. Back up the target Supabase project and verify the project URL and server key out-of-band.
2. Apply every SQL migration under `supabase/migrations/` in filename order, including `202610260005_auth_login_rate_limits.sql` and `202610260006_api_rate_limits.sql`. Review the generated schema/functions before applying them to a production database.
3. Confirm service-role PostgREST access to `auth_sessions`, `auth_login_rate_limits`, `macro_observations`, and `research_runs`; the API probes those tables through `/readyz`.
4. Use the supported Docker Compose deployment for production evidence work. The `api-data` named volume persists uploaded evidence, model/download artifacts, and the Chroma index across API container restarts. Configure encrypted volume backups and test restore before enabling user uploads.
5. Run a single API replica while Chroma and evidence files are on the local named volume. Adding API replicas requires moving both evidence objects and the vector index to shared durable storage first; shared auth sessions alone do not make local evidence/vector state multi-replica safe.
6. Vercel may host the public/read-only frontend, but the current evidence object files/vector index are not durable on Vercel. Production `/readyz` therefore returns 503 there. The 50 MB evidence limit is intended for the persistent API deployment; do not route large evidence uploads through a serverless frontend proxy.

## Release sequence

From the repository root, after setting the production secrets:

```bash
# Review interpolated values before starting containers.
docker compose config

# Build all three services and wait for API readiness.
docker compose up --build -d

docker compose ps
curl --fail https://api.example.com/readyz
```

Place a maintained TLS reverse proxy/load balancer in front of the services. Terminate HTTPS there, set exact trusted proxy addresses, restrict direct Internet access to port 8000, and forward only required traffic to the API. Keep the Supabase key server-only. Use `GET /health` for liveness and `GET /readyz` for readiness; never treat a healthy liveness response as proof that persistence, TOTP, provider, or migrations are ready.

After readiness returns HTTP 200, run the protected-path smoke check with a provisioned administrator account and authenticator code: sign in at `/login` on each frontend, verify the user/role is shown, create and retrieve a research record, upload/search/delete an evidence file, verify an unauthorized/no-cookie request receives 401 and a mutation without CSRF receives 403, and confirm logout invalidates the session. Confirm uploads survive an API container restart and that configured retention cleanup behaves as intended. Do not use real sensitive evidence until encrypted backups and restore have passed.

## Automated checks

```bash
python -m pytest -q
(cd frontend && npm ci && npm run typecheck && npm run lint && npm run build && npm audit --audit-level=high)
(cd admin-frontend && npm ci && npm run typecheck && npm run lint && npm run build && npm audit --audit-level=high)
```

The admin ESLint run currently emits a warning about a font loaded from the root layout; it has no lint errors. Existing frontend lint also contains warnings outside the new auth code. Docker image/Compose execution requires a Docker-enabled host; this sandbox has no Docker daemon, so `docker compose config`, image builds and volume-restore tests must run in the deployment pipeline before release.

## Product/model limitations that remain release controls

- The current account provisioning is environment-based and single-tenant. Do not onboard untrusted users or describe the service as self-service multi-tenant until individual account lifecycle, tenant administration, and ownership isolation are implemented and independently tested.
- The `/research` endpoint deliberately labels itself a prototype summary and does not yet execute the bounded graph in `app/workflows/graph.py`; several specialist agents are placeholders. Do not describe its current result as fully agent-orchestrated analysis.
- The scenario coefficients remain illustrative and non-causal. CPI data do not preserve complete point-in-time release/revision vintages. Do not market the simulator or backtests as validated policy recommendations or real-time decision tests.
- Some analysis/log/report pages remain demo/mock views. The deployment readiness gate covers infrastructure prerequisites, not economic validity, model calibration, licensing, or complete feature coverage.

## Verification boundary

Code and configuration changes in this branch have passed the recorded repository tests/builds and dependency audits; `docs/AUDIT_AND_REPAIR_REPORT.md` records the exact latest results. No production credentials were supplied to this run, no Supabase migration was applied to a live project, and no deployment was made. Do not mark the release live until the operator completes the secret provisioning, migration, readiness, volume persistence, restore, and protected-path smoke checks above.

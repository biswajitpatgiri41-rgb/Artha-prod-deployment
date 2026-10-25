# Artha AI production-hardening and audit report

**Review date:** 2026-10-26  
**Repository:** `biswajitpatgiri41-rgb/Artha_Ai`  
**Audited baseline:** `7cffffb1f9e72fc7a307f79afd388be1e9d6bbe9`  
**Work branch:** `manus/production-audit-fixes` (local only; no push or deployment performed)

## Executive outcome

This pass moved the code from an effectively public prototype toward a hardened **single-tenant, administrator-operated deployment profile**. Backend auth, server-side authorization, same-origin BFF sessions, CSRF checks, TOTP, durable shared sessions, atomic research persistence, shared login/API rate limits, frontend dependency fixes, and a fail-closed production readiness endpoint are implemented and regression-tested in the branch.

This is not a claim that the public deployment is fixed: no code was pushed, no external production settings were changed, no Supabase migration was applied to a live project, and no new production service was deployed. The Vercel evidence path is intentionally not considered ready because evidence files and the Chroma index still require a persistent API volume. This project also remains a research prototype for monetary-policy claims: the scenario coefficients are illustrative/non-causal, CPI release vintages are incomplete, and several specialist agents are placeholders. `POST /research` now invokes the separate bounded graph, but that integration does not make the analytical outputs official RBI recommendations or establish a self-service multi-tenant product.

The deployable code/runbook is in this checkout. The current release gate is `GET /readyz`; production secrets, ordered database migrations, the persistent storage profile, backups, and protected-path smoke tests must be completed before routing users.

## Previously observed public deployment

On 2026-10-25 the public frontend `https://artha-ai-beta.vercel.app/` loaded and eventually displayed API-derived values. The API at `https://artha-ai-api.vercel.app` returned HTTP 200 for `/health`, `/sources`, `/series/cpi_yoy`, and the seasonal-naive forecast endpoint; it reported eight available series and 153 CPI/y/y observations through 2026-09-01. The dashboard displayed headline CPI 5.54 for 2026-09. Those were point-in-time observations, not an independent validation of source vintage or model accuracy. The public deployment was not rechecked or changed during this hardening pass.

Earlier browser review found the chart said “0 macro observations” despite rendering CPI history, mislabeled a seasonal-naive baseline as a stored model forecast, and displayed an uncertainty band without supplied interval bounds. The local branch repairs these labels/counts and includes browser regression coverage; the live Vercel site remains unchanged until a reviewed release is deployed.

## Data assets and economic limitations

No new datasets were downloaded in this work. The repository has two overlapping snapshot directories with different coverage claims. `data/india_macro_dataset_snapshot/README.md` reports 54,008 observations across 34 series and headline CPI Jan 2025–Aug 2026. `data/india_macro_dataset_snapshot (1)/README.md` reports 58,686 observations across 46 series: a 2024-base headline CPI back-series Jan 2013–Aug 2026 (164 months per sector), CFPI index/y/y series, IIP under two base years, RBI USD/INR daily values/monthly means, EIA Brent, IMD rainfall, and FRED/IMF/World Bank context. These are repository-documented figures; this run did not independently regenerate every manifest row count.

The snapshots disclose missing WPI, money/credit, yields/liquidity, reserves/external accounts, incomplete CPI-component history, and incomplete release/revision timing. The expanded snapshot says it does not support vintage-perfect backtests. The root `data/processed/macro_monthly.csv` has 472 rows and is not the 1,510-row sparse monthly feature table documented in the expanded snapshot. Source links, fetch times, checksums and caveats are in the snapshot manifests. Primary-source links include [MoSPI CPI](https://esankhyiki.mospi.gov.in/macroindicators?product=cpi), [MoSPI IIP API schema](https://api.mospi.gov.in/layout/swagger_user_iip.yaml), [RBI reference rates](https://www.rbi.org.in/scripts/referenceratearchive.aspx), [RBI policy archive](https://www.rbi.org.in/scripts/annualpolicy.aspx), and [EIA Brent](https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=RBRTE&f=M).

## Implemented production hardening

- **Frontend authentication:** both Next.js applications now use same-origin BFF routes. Access/refresh tokens are kept in HttpOnly cookies, not exposed to browser JavaScript. CSRF validation is required on cookie-authenticated mutations. The admin route group validates session state server-side; the admin sign-in UI accepts password and TOTP and supports logout.
- **Backend authentication/authorization:** production login requires Argon2id password validation and TOTP; development bypass is disabled in production. Protected research/evidence/admin/data-mutation paths use server-side role/permission checks. Session rows are stored by hash in Supabase and can be revoked across API workers. Production auth fails closed if the shared store is unavailable.
- **Tenant-scoped research:** research records/events/reports are stored through a database RPC and reads are scoped to tenant ID. Provisioning remains environment-based/single-admin, so this is not general multi-tenant onboarding.
- **Durable macro data:** the active data-upload path persists canonical observations and raw-upload provenance to Supabase using migrations/RPCs. Original raw objects use private Supabase storage. Research record writes use a transactional RPC.
- **Shared rate limits:** login uses an atomic database-backed five-attempt/minute window. A second shared Postgres RPC applies configurable route limits to assistant, research, data/evidence upload and admin operations; assistant calls are capped by the LLM-per-minute quota. `/readyz` rejects disabled rate limits or missing rate-limit tables.
- **Readiness/deployment:** `/health` remains liveness; `/readyz` checks production auth secrets, Argon2id admin hash, TOTP seed, explicit CORS origins, configured provider, enabled shared rate limiting, Supabase connectivity/migration tables, and Vercel evidence-storage limitations. The API and Compose healthchecks now use readiness. Vercel production returns 503 until durable evidence/vector storage is implemented there.
- **Dependencies:** vulnerable `python-jose`/`ecdsa` were removed in favor of PyJWT; `cryptography` and pytest tooling were advanced to audited fixed ranges. The main and admin frontends use tested patched Next.js/Tailwind/ECharts stacks. Latest captured npm audits report zero vulnerabilities in both frontend dependency trees; Python requirements audit reports no known vulnerabilities.
- **Regression repairs from the previous pass:** critic false positives and report-agent schema/evidence handling; misleading CPI history/forecast labels; missing App Router client directive. Added dashboard, login flow, auth/session, rate-limit and infrastructure tests.

## Feature and deployment status

| Area | Status | Evidence and qualification |
|---|---|---|
| Baseline/live availability | Historical observation only | Public frontend/API were reachable on 2026-10-25; current deployment not modified or reverified. |
| Data panels and provenance | Partial | Multiple source snapshots/manifests exist, but coverage differs and real-time release vintages are incomplete. |
| Forecasts/backtests | Partial | Seasonal-naive and packaged model artifacts exist; no retraining, vintage-perfect backtest, or new accuracy claim was made. |
| Scenario/policy model | Not validated for policy decisions | Hand-set sensitivities are labeled illustrative/non-causal; intervals and stress-domain validation are not established. |
| Research graph | Connected; partial/prototype | `POST /research` now runs the bounded graph, records node events/status, and carries forecast/backtest context plus validated uploaded evidence into critic/report inputs. The inflation specialist is a placeholder and several agents remain provisional; workflow completion is not economic validation. |
| Research persistence | Implemented with configuration gate | Supabase transaction/migrations support tenant-scoped runs/events/reports; requires applied migrations and a functioning server credential. |
| Evidence storage | Persistent-volume only | Local files, metadata and Chroma index persist in the single-replica Compose `api-data` volume; not durable on Vercel or shared across API replicas. |
| Auth/sessions/rate limits | Code implemented; external config pending | TOTP, Argon2id, HttpOnly BFF cookies, CSRF, DB-backed sessions, revocation, login/API limits and role checks; must be provisioned and smoke-tested in the real deployment. |
| Frontend routes | Partial | Login and dashboard tests exist; analysis/log/report areas still contain mock/demo surfaces and require integration. |
| Production deployment | Not released | Runbook and fail-closed readiness checks are included. No live migrations, secrets, TLS changes, image builds, or deployment occurred. |

## Verification performed

- **Backend:** final local full suite after graph/API wiring and the route integration regression: **110 passed**. This includes workflow node validation, run/event/report persistence, authorization, rate limits, and the new `/research`-to-graph contract test.
- **Python supply chain:** `pip-audit -r requirements.txt` and the full isolated-venv audit report **no known vulnerabilities**. The venv audit initially found stale `python-jose`/`ecdsa` packages from the prior environment; both unused packages were removed and the audit passed.
- **Frontends:** both `frontend` and `admin-frontend` npm audits show **0 vulnerabilities**. Both frontends pass lint and TypeScript checks and production builds; the admin Google Fonts link was moved to Next's optimized self-hosted font loader, removing its lint warning. Two login-flow tests passed earlier; Playwright was not rerun in this continuation.
- **Readiness:** backend tests cover fail-closed missing configuration and route throttling. Production-ready status still requires actual Supabase migrations/secrets and cannot be simulated by a local test database.
- **Infrastructure:** Docker CLI/daemon is not installed in this environment; image builds, `docker compose config`, runtime health, TLS proxy behavior, volume durability and backup-restore were not verified here. These are mandatory CI/deployment-host release checks.
- **Warnings:** the backend final run completed without warnings. Both frontend lint runs are clean, and both production builds completed without the earlier ESLint/module-type warnings. Docker CLI/daemon and production services remain unavailable for host-level validation.
- **Data/model:** no dataset was ingested and no model was retrained. No causal, policy, MAE/RMSE, or vintage-perfect claim is made.

## Release blockers and controls

1. Apply all ordered SQL migrations (through `202610260006_api_rate_limits.sql`) to a backed-up staging Supabase project; verify `/readyz`, service-role permissions, and revocation/throttling behavior before production.
2. Provision a strong JWT secret, server-only Supabase key, Argon2id admin password hash, unique TOTP seed, NVIDIA provider config, explicit HTTPS origins and trusted reverse-proxy IPs in the host secret manager. Keep bypass disabled.
3. Deploy the API as one replica with a persistent `api-data` volume behind a TLS reverse proxy. Configure encrypted backups and complete a restore drill. Vercel remains a limited front-end/demo target for this architecture.
4. Complete protected-path smoke tests (no cookie, no CSRF, wrong role, TOTP, session revocation, shared rate limits, tenant-scoped run access, upload/search/delete, restart persistence and cleanup).
5. Before onboarding separate customers, add per-user account lifecycle and ownership isolation for evidence/files/data and run cross-tenant tests. Current IP/route throttles are an abuse cap, not a billing or per-customer quota service.
6. Keep model claims explicitly limited. Establish point-in-time CPI vintages, canonical dataset lineage, documented scenario estimation/calibration and independent evaluation before treating the simulator as policy decision support.
7. Finish remaining mock/demo frontend routes; add accessibility/route coverage. Add malware scanning/parser isolation, built-image SBOM/scanning, monitoring, incident response and a deployment-specific security review.

## Files and branch boundary

Current deployment and security instructions: [`PRODUCTION_HARDENING.md`](PRODUCTION_HARDENING.md), [`security-review.md`](security-review.md), and [`INFRASTRUCTURE_SECURITY_NOTES.md`](INFRASTRUCTURE_SECURITY_NOTES.md). The older `SECURITY_AUDIT.md` is explicitly marked historical. Code changes remain local on `manus/production-audit-fixes`; the public website/API and GitHub repository were not changed.

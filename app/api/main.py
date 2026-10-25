import asyncio
import hashlib
import hmac
import ipaddress
import logging
import os
import re
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routes import router
from .research_routes import router as research_router
from .data_routes import router as data_router
from .evidence_routes import router as evidence_router
from .advanced_routes import router as advanced_router
from .admin_auth_routes import router as admin_auth_router
from .admin_monitoring_routes import router as admin_monitoring_router
from .admin_telemetry import telemetry
from app.tools.research import catalog
from app.core.config import get_settings
from app.models.final_package import final_package_status
from app.security.config import get_security_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def _client_ip(request) -> str | None:
    """Resolve the socket peer, honoring X-Forwarded-For only from trusted proxies."""
    peer = request.client.host if request.client else None
    trusted = {
        item.strip() for item in os.getenv("TRUSTED_PROXY_IPS", "").split(",")
        if item.strip()
    }
    if not peer or peer not in trusted:
        return peer
    forwarded = request.headers.get("x-forwarded-for", "")
    chain = [item.strip() for item in forwarded.split(",") if item.strip()]
    # Walk from the socket peer toward the original client. Ignore trusted
    # proxy hops; the first untrusted address is the best available client IP.
    for candidate in reversed(chain):
        if candidate not in trusted:
            try:
                return str(ipaddress.ip_address(candidate))
            except ValueError:
                return peer
    return peer


def _parse_rate_limit(value: str, fallback: tuple[int, int]) -> tuple[int, int]:
    try:
        amount_text, unit = value.split("/", 1)
        amount = int(amount_text)
        seconds = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}[unit.rstrip("s")]
        if amount > 0:
            return amount, seconds
    except (ValueError, KeyError):
        pass
    return fallback


def _rate_limit_rule(method: str, path: str) -> tuple[str, int, int] | None:
    config = get_security_settings()
    if not config.rate_limit_enabled:
        return None
    if method == "POST" and path == "/assistant/chat":
        amount, seconds = _parse_rate_limit(config.rate_limit_chat_limit, (30, 60))
        return "assistant", min(amount, config.quota_max_llm_requests_per_minute), seconds
    if method == "POST" and path == "/research":
        amount, seconds = _parse_rate_limit(config.rate_limit_research_limit, (10, 60))
        return "research", amount, seconds
    if method == "POST" and (path == "/evidence/upload" or path.startswith("/data/upload/") or path == "/data-updates/upload"):
        amount, seconds = _parse_rate_limit(config.rate_limit_upload_limit, (10, 60))
        return "upload", amount, seconds
    if path.startswith("/api/admin/"):
        amount, seconds = _parse_rate_limit(config.rate_limit_admin_limit, (60, 60))
        return "admin", amount, seconds
    return None


def _enforce_shared_rate_limit(request):
    """Return an HTTP response when a production request exceeds its shared limit."""
    if os.getenv("ENVIRONMENT", "development").strip().lower() != "production":
        return None
    rule = _rate_limit_rule(request.method, request.url.path)
    if not rule:
        return None
    scope, limit, window_seconds = rule
    secret = os.getenv("JWT_SECRET_KEY", "").encode()
    if len(secret) < 32:
        return JSONResponse(status_code=503, content={"detail": "Rate-limit service is not ready"})
    try:
        from app.db import supabase
        if not supabase.is_configured():
            return JSONResponse(status_code=503, content={"detail": "Rate-limit service is not ready"})
        identity = _client_ip(request) or "unknown"
        material = f"{scope}|{request.method}|{identity}".encode()
        key_hash = hmac.new(secret, material, hashlib.sha256).hexdigest()
        if not supabase.consume_api_rate_limit(key_hash, limit=limit, window_seconds=window_seconds):
            return JSONResponse(status_code=429, content={"detail": "Request rate limit exceeded"},
                                headers={"Retry-After": str(window_seconds)})
    except Exception:
        logger.exception("Shared API rate limiter is unavailable")
        return JSONResponse(status_code=503, content={"detail": "Rate-limit service is unavailable"})
    return None


async def _temporary_evidence_retention_worker():
    while True:
        try:
            from app.evidence.service import get_evidence_service
            await asyncio.to_thread(lambda: get_evidence_service().cleanup_expired_evidence())
        except Exception:
            logger.exception("Temporary evidence retention cleanup failed")
        await asyncio.sleep(300)


@asynccontextmanager
async def lifespan(_app):
    worker = asyncio.create_task(_temporary_evidence_retention_worker())
    try:
        yield
    finally:
        worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker


app = FastAPI(title="Agentic Monetary Policy API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    # Browser clients use bearer tokens through same-origin BFF routes; do not
    # expose credentialed cross-origin cookies from the API host.
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Filename", "Authorization", "X-CSRF-Token"],
)
app.include_router(router)
app.include_router(research_router)
app.include_router(data_router)
app.include_router(evidence_router)
app.include_router(advanced_router)
app.include_router(admin_auth_router)
app.include_router(admin_monitoring_router)


@app.exception_handler(RequestValidationError)
async def safe_validation_error(request, exc: RequestValidationError):
    """Return validation locations/messages without echoing rejected values."""
    errors = [
        {"location": [str(part) for part in item.get("loc", ())],
         "message": item.get("msg", "Invalid value"),
         "type": item.get("type", "validation_error")}
        for item in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.middleware("http")
async def security_headers(request, call_next):
    """Apply browser hardening headers to API responses."""
    started = telemetry.begin()
    status_code = 500
    bytes_out = 0
    try:
        limited = _enforce_shared_rate_limit(request)
        response = limited if limited is not None else await call_next(request)
        status_code = response.status_code
        try:
            body = getattr(response, "body", None)
            bytes_out = len(body) if body is not None else int(response.headers.get("content-length", "0"))
        except ValueError:
            bytes_out = 0
    except Exception:
        raise
    finally:
        try:
            bytes_in = int(request.headers.get("content-length", "0"))
        except ValueError:
            bytes_in = 0
        telemetry.finish(
            started,
            request.method,
            request.url.path,
            status_code,
            max(0, bytes_in),
            max(0, bytes_out),
            _client_ip(request),
        )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
    response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.get("/health")
def health_check():
    """Health check endpoint reporting service status."""
    llm_status = "configured" if settings.is_llm_configured() else "not_configured"
    available_series = sum(1 for item in catalog() if item["available"])
    return {
        "status": "ok",
        "llm": llm_status,
        "data": "available" if available_series else "no_observations",
        "available_series": available_series,
        "econometrics": "baseline_tools_available",
        "final_model_package": final_package_status()["status"],
    }


@app.get("/readyz")
def readiness_check():
    """Production readiness check; liveness remains available at /health."""
    if os.getenv("ENVIRONMENT", "development").strip().lower() != "production":
        return {"status": "ready", "environment": "non-production"}

    missing: list[str] = []
    if len(os.getenv("JWT_SECRET_KEY", "")) < 32:
        missing.append("JWT_SECRET_KEY must contain at least 32 characters")
    if not os.getenv("ADMIN_EMAIL", "").strip():
        missing.append("ADMIN_EMAIL is required")
    if not os.getenv("ADMIN_PASSWORD", "").startswith("$argon2id$"):
        missing.append("ADMIN_PASSWORD must be an Argon2id hash")
    if not re.fullmatch(r"[A-Z2-7]{16,}={0,6}", os.getenv("ADMIN_TOTP_SECRET", "").strip().upper()):
        missing.append("ADMIN_TOTP_SECRET must be a valid Base32 TOTP secret")
    origins = settings.cors_allowed_origins
    if not origins or "*" in origins:
        missing.append("CORS_ALLOWED_ORIGINS must list explicit production origins")
    if not settings.is_llm_configured():
        missing.append("NVIDIA_API_KEY/model provider is not configured")
    if not get_security_settings().rate_limit_enabled:
        missing.append("RATE_LIMIT_ENABLED must be true in production")
    if os.getenv("VERCEL", "").strip().lower() == "1":
        missing.append("Vercel local evidence files and vector index are ephemeral; deploy with durable storage")

    from app.db import supabase
    if not supabase.is_configured():
        missing.append("Supabase service-role storage is not configured")
    elif not missing:
        try:
            for table in ("auth_sessions", "auth_login_rate_limits", "api_rate_limits", "macro_observations", "research_runs"):
                supabase.list_rows(table, select="*", page_size=1)
        except Exception:
            logger.exception("Production readiness storage probe failed")
            missing.append("Supabase connectivity or required database migrations are unavailable")

    if missing:
        return JSONResponse(status_code=503, content={"status": "not_ready", "missing": missing})
    return {"status": "ready", "environment": "production"}


@app.get("/visitor-heartbeat", include_in_schema=False)
def visitor_heartbeat():
    """Allow an open research page to stay visible between data requests.

    The middleware records only the network address and request metadata; no
    cookies, user identifiers, or request body are collected here.
    """
    return {"status": "ok"}

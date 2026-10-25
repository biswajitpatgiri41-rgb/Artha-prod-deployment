import hashlib

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.admin_auth_routes import _verify_totp
from app.db import supabase
from app.security import authentication


def test_totp_matches_rfc6238_sha1_vector_and_rejects_invalid_codes():
    # RFC 6238 test secret, SHA-1, 6 digits, T0=0, X=30, at t=59.
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert _verify_totp(secret, "287082", at_time=59)
    assert not _verify_totp(secret, "000000", at_time=59)
    assert not _verify_totp("not-base32!", "287082", at_time=59)


def test_production_sessions_use_shared_store_and_are_revocable(monkeypatch):
    monkeypatch.setattr(authentication.settings, "environment", "production")
    monkeypatch.setattr(supabase, "is_configured", lambda: True)
    records = {}

    def save(session_hash, record):
        records[session_hash] = dict(record)

    def touch(session_hash, last_activity):
        records[session_hash]["last_activity"] = last_activity

    def revoke(session_hash):
        if session_hash not in records:
            return False
        records[session_hash]["revoked"] = True
        return True

    monkeypatch.setattr(supabase, "save_auth_session", save)
    monkeypatch.setattr(supabase, "get_auth_session", lambda session_hash: records.get(session_hash))
    monkeypatch.setattr(supabase, "touch_auth_session", touch)
    monkeypatch.setattr(supabase, "revoke_auth_session", revoke)

    session_id = authentication.create_session(
        user_id="admin-test", email="admin@example.test", role="ADMIN",
        tenant_id="system", permissions=["research:read"], mfa_verified=True,
    )
    session_hash = hashlib.sha256(session_id.encode()).hexdigest()
    assert session_hash in records
    assert authentication.get_session(session_id)["mfa_verified"] is True
    assert authentication.revoke_session(session_id) is True
    assert authentication.get_session(session_id) is None


def test_production_readiness_reports_missing_requirements_without_leaking_secrets(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "sentinel-production-key-value")
    monkeypatch.setattr(supabase, "is_configured", lambda: False)
    with TestClient(app) as client:
        response = client.get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert any("JWT_SECRET_KEY" in item for item in body["missing"])
    assert any("Supabase" in item for item in body["missing"])
    assert "sentinel-production-key-value" not in str(body)


def test_production_admin_login_honors_shared_rate_limit(monkeypatch):
    monkeypatch.setattr(authentication.settings, "environment", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "a-test-signing-key-that-is-at-least-32-characters")
    monkeypatch.setattr(supabase, "is_configured", lambda: True)
    monkeypatch.setattr(supabase, "consume_api_rate_limit", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(supabase, "consume_admin_login_attempt", lambda _key: False)
    with TestClient(app) as client:
        response = client.post("/api/admin/auth/login", json={
            "email": "admin@example.com", "password": "not-a-real-password",
        })
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"


def test_production_assistant_quota_is_shared_and_fails_closed(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "a-test-signing-key-that-is-at-least-32-characters")
    monkeypatch.setattr(supabase, "is_configured", lambda: True)
    calls = []

    def reject(_key_hash, *, limit, window_seconds):
        calls.append((limit, window_seconds))
        return False

    monkeypatch.setattr(supabase, "consume_api_rate_limit", reject)
    with TestClient(app) as client:
        response = client.post("/assistant/chat", json={})
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert calls and calls[0][0] <= 20

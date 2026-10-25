from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app
from app.security import authentication
from app.security.authorization import Permission

client = TestClient(app)


def _token(role: str = "ADMIN", permissions: list[str] | None = None) -> str:
    permissions = permissions if permissions is not None else [p.value for p in Permission]
    session_id = authentication.create_session(
        user_id="test-user",
        email="test@example.com",
        role=role,
        tenant_id="test-tenant",
        permissions=permissions,
        mfa_verified=True,
    )
    return authentication.create_access_token(
        user_id="test-user",
        email="test@example.com",
        role=role,
        tenant_id="test-tenant",
        permissions=permissions,
        mfa_verified=True,
        session_id=session_id,
    )


def test_upload_and_admin_routes_reject_unauthenticated_requests() -> None:
    assert client.get("/evidence/config").status_code == 401
    assert client.post("/evidence/upload", data={"run_id": "00000000-0000-0000-0000-000000000001"}, files={"file": ("evidence.txt", b"text")}).status_code == 401
    assert client.post(
        "/data/upload/cpi_headline", content=b"date,value\n2024-01-01,100",
        headers={"x-filename": "data.csv", "content-type": "text/csv"},
    ).status_code == 401
    assert client.get("/api/admin/metrics").status_code == 401


def test_authorized_admin_can_access_evidence_data_upload_and_admin_routes(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(authentication.settings, "jwt_secret_key", "t" * 48)
    from app.api import data_routes
    monkeypatch.setattr(data_routes, "RAW", tmp_path / "raw")
    monkeypatch.setattr(data_routes, "INTERIM", tmp_path / "interim")
    monkeypatch.setattr(data_routes, "MANIFESTS", tmp_path / "manifests")
    monkeypatch.setattr(data_routes, "ROOT", tmp_path)
    token = _token()
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/evidence/config", headers=headers).status_code == 200
    upload = client.post(
        "/data/upload/cpi_headline", headers={**headers, "x-filename": "data.csv", "content-type": "text/csv"},
        content=b"date,value\n2024-01-01,100",
    )
    assert upload.status_code == 200
    assert upload.json()["series_id"] == "cpi_headline"
    assert client.get("/api/admin/metrics", headers=headers).status_code == 200


def test_non_admin_cannot_access_admin_monitoring(monkeypatch) -> None:
    monkeypatch.setattr(authentication.settings, "jwt_secret_key", "t" * 48)
    token = _token(role="RESEARCHER", permissions=[Permission.EVIDENCE_READ.value])
    response = client.get("/api/admin/metrics", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_production_with_missing_jwt_secret_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(authentication.settings, "environment", "production")
    monkeypatch.setattr(authentication.settings, "jwt_secret_key", "")
    response = client.post(
        "/data/upload/cpi_headline",
        content=b"date,value\n2024-01-01,100",
        headers={"x-filename": "data.csv", "content-type": "text/csv"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Authentication service unavailable"

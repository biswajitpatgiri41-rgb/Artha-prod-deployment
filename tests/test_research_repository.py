from __future__ import annotations

import json

import pytest

from app.db import supabase
from app.db.research_repository import ResearchPersistenceNotConfigured, ResearchRepository


def sample_run() -> dict:
    return {
        "run_id": "b17486f6-2a3a-49b4-99bd-a5030a97e17c",
        "created_at": "2026-10-25T12:00:00+00:00",
        "status": "completed",
        "events": [
            {"event_id": "e1", "event_type": "started", "occurred_at": "2026-10-25T12:00:01+00:00"},
            {"type": "finished", "created_at": "2026-10-25T12:00:02+00:00"},
        ],
        "report": {"created_at": "2026-10-25T12:00:00+00:00", "title": "Example"},
    }


def test_production_without_supabase_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    repo = ResearchRepository(tmp_path)
    with pytest.raises(ResearchPersistenceNotConfigured, match="requires SUPABASE_URL"):
        repo.save(sample_run())
    assert list(tmp_path.iterdir()) == []


def test_development_without_supabase_uses_atomic_local_json(monkeypatch, tmp_path):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    repo = ResearchRepository(tmp_path)
    run = sample_run()
    repo.save(run)
    assert repo.get(run["run_id"]) == run
    assert repo.list() == [run]
    assert json.loads((tmp_path / f"{run['run_id']}.json").read_text()) == run
    assert not list(tmp_path.glob("*.tmp"))


def test_local_missing_record_and_limit_validation(monkeypatch, tmp_path):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    repo = ResearchRepository(tmp_path)
    assert repo.get("missing") is None
    with pytest.raises(ValueError, match="limit"):
        repo.list(0)
    with pytest.raises(ValueError, match="run_id"):
        repo.save({})


def test_local_run_is_hidden_from_other_tenants(monkeypatch, tmp_path):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    run = sample_run()
    run["tenant_id"] = "tenant-a"
    repo = ResearchRepository(tmp_path)
    repo.save(run)
    assert repo.get(run["run_id"], tenant_id="tenant-a") == run
    assert repo.get(run["run_id"], tenant_id="tenant-b") is None
    assert repo.list(tenant_id="tenant-b") == []


def test_supabase_persists_the_complete_record_with_one_atomic_rpc(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_placeholder")
    calls = []

    def record(method, path, **kwargs):
        calls.append((method, path, kwargs))

    monkeypatch.setattr(supabase, "_request", record)
    run = sample_run()
    supabase.persist_research_record(run)
    assert len(calls) == 1
    assert calls[0][0:2] == ("POST", "rest/v1/rpc/persist_research_record")
    assert calls[0][2]["json_body"] == {"p_run": run}

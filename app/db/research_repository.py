"""Durable storage boundary for research runs, events, and reports.

Production never falls back to ephemeral/local files when Supabase is not configured.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.db import supabase


class ResearchPersistenceNotConfigured(RuntimeError):
    """Raised when durable production storage is required but unavailable."""


class ResearchRepository:
    def __init__(self, local_dir: Path | None = None) -> None:
        self.local_dir = Path(local_dir or os.getenv("RESEARCH_LOCAL_STORAGE_DIR", "data/research"))

    @staticmethod
    def _backend() -> str:
        if supabase.is_configured():
            return "supabase"
        if os.getenv("ENVIRONMENT", "development").strip().lower() == "production":
            raise ResearchPersistenceNotConfigured(
                "Research persistence requires SUPABASE_URL and SUPABASE_SECRET_KEY "
                "(or SUPABASE_SERVICE_ROLE_KEY) in production"
            )
        return "local"

    def save(self, run: dict[str, Any]) -> None:
        run_id = run.get("run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("run must contain a non-empty run_id")
        run.setdefault("tenant_id", "development")
        if not isinstance(run["tenant_id"], str) or not run["tenant_id"].strip():
            raise ValueError("run must contain a non-empty tenant_id")
        backend = self._backend()
        if backend == "supabase":
            supabase.persist_research_record(run)
            return
        self.local_dir.mkdir(parents=True, exist_ok=True)
        target = self.local_dir / f"{run_id}.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)

    def get(self, run_id: str, tenant_id: str = "development") -> dict[str, Any] | None:
        if self._backend() == "supabase":
            return supabase.get_research_run(run_id, tenant_id=tenant_id)
        path = self.local_dir / f"{run_id}.json"
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        if not isinstance(result, dict):
            raise ValueError("Stored research run is not an object")
        if result.get("tenant_id") != tenant_id:
            return None
        return result

    def list(self, limit: int = 20, tenant_id: str = "development") -> list[dict[str, Any]]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if self._backend() == "supabase":
            return supabase.list_research_runs(limit, tenant_id=tenant_id)
        if not self.local_dir.exists():
            return []
        paths = sorted(self.local_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        result = []
        for path in paths[:limit]:
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(item, dict) and item.get("run_id") and item.get("tenant_id") == tenant_id:
                result.append(item)
        return result


repository = ResearchRepository()

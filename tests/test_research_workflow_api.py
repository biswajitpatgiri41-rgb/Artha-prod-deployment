import asyncio

from app.api import research_routes
from app.tools.research import Observation
from app.workflows import graph


def test_create_research_run_persists_graph_results(monkeypatch):
    stored = {}
    observations = [Observation("2026-08-01", 5.4, "cpi_yoy", "MoSPI", "percent")]
    forecast = {"model": "seasonal_naive", "horizon_months": 6, "forecasts": []}
    backtest = {"model": "seasonal_naive", "mae": 0.5, "rmse": 0.7}

    monkeypatch.setattr(research_routes, "get_forecast", lambda *args: forecast)
    monkeypatch.setattr(research_routes, "get_backtest", lambda *args: backtest)
    monkeypatch.setattr(research_routes, "load_series", lambda series_id: observations)
    monkeypatch.setattr(graph, "load_series", lambda series_id: observations)
    monkeypatch.setattr(research_routes.research_repository, "save", lambda run: stored.update(run))

    request = research_routes.ResearchRequest(
        question="Analyze CPI inflation and external risks",
        horizon_months=6,
        scenarios=[research_routes.ResearchScenario(name="Oil shock", oil_pct=10)],
    )
    result = asyncio.run(research_routes.create_research_run(request, user=None))

    assert result["run_id"] == stored["run_id"]
    assert result["workflow_status"] == "COMPLETED"
    assert result["workflow"]["plan"]
    assert result["workflow"]["growth"]
    assert result["workflow"]["econometrics"]["forecast"] == forecast
    assert result["report"]["model_evidence"]
    assert result["report"]["scenarios"][0]["name"] == "Oil shock"
    assert result["events"]
    assert {event["node_id"] for event in result["events"]} >= {"planner", "data", "critic", "report"}
    assert all(event["event_id"].startswith(result["run_id"] + ":") for event in result["events"])
    assert all(event["type"].startswith("node_") and event["occurred_at"] for event in result["events"])
    assert all("prototype summary" not in warning.lower() for warning in result["warnings"])

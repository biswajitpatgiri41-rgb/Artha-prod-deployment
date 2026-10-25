import pytest

from app.workflows import graph


def test_workflow_completes_with_validated_evidence(monkeypatch):
    from app.tools.research import Observation
    monkeypatch.setattr(graph, "load_series", lambda sid: [Observation(
        "2025-01-01", 4.2, sid, "MoSPI", "percent")])
    result = pytest.importorskip("asyncio").run(graph.run_workflow("Analyze CPI and oil"))
    assert result.status == "COMPLETED"
    assert result.plan.required_indicators == ["cpi_headline", "brent_crude"]
    assert result.retrieved_evidence[0]["source"] == "MoSPI"
    assert result.final_report is not None
    assert [event["type"] for event in result.events].count("node_completed") == 9


def test_workflow_records_malformed_output_and_continues(monkeypatch):
    monkeypatch.setattr(graph.growth_agent, "run_growth", lambda question: {"summary": 7})
    result = pytest.importorskip("asyncio").run(graph.run_workflow("Analyze CPI"))
    assert result.status == "COMPLETED_WITH_ERRORS"
    assert result.growth is None
    assert any(error.startswith("growth:") for error in result.errors)
    assert result.final_report is not None
    assert any(event["node_id"] == "growth" and event["type"] == "node_failed" for event in result.events)


def test_workflow_records_raised_tool_failure(monkeypatch):
    def fail(_series_id):
        raise RuntimeError("local data unavailable")
    monkeypatch.setattr(graph, "load_series", fail)
    result = pytest.importorskip("asyncio").run(graph.run_workflow("Analyze CPI"))
    assert result.status == "COMPLETED_WITH_ERRORS"
    assert any(error.startswith("data:") for error in result.errors)
    assert result.data is None
    assert any(event["node_id"] == "data" and event["type"] == "node_failed" for event in result.events)


def test_tool_inputs_are_allowlisted(monkeypatch):
    from app.agents.schemas import ResearchPlan
    from app.workflows.state import ResearchState
    state = ResearchState(plan=ResearchPlan(
        objective="test", tasks=[], required_indicators=["cpi_headline", "__import__('os')"],
        required_agents=[]))
    assert graph._validate_tools(state) == ["cpi_headline"]

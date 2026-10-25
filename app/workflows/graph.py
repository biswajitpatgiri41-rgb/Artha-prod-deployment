"""Deterministic, bounded async orchestration for research agents.

This intentionally uses a small typed graph instead of LangGraph: every edge is
fixed, tool selection is allowlisted, execution is sequential, and failures are
recorded per node. It never asks a model to create plans or facts.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable

from ..agents import critic_agent, data_agent, econometrics_agent, external_agent, growth_agent, planner, policy_agent, report_agent
from ..agents.schemas import AgentAnalysis, CriticResult, PolicyAnalysis, ReportResult
from ..core.series_registry import SERIES_REGISTRY
from ..tools.research import load_series
from .state import ResearchState

MAX_QUESTION_LENGTH = 2000
MAX_SERIES = 16
ALLOWED_SERIES = frozenset(SERIES_REGISTRY.keys())


def _validate_tools(state: ResearchState) -> list[str]:
    """Return only registered tool input IDs derived from the deterministic plan."""
    requested = list(dict.fromkeys(state.plan.required_indicators if state.plan else []))
    return [series_id for series_id in requested if series_id in ALLOWED_SERIES][:MAX_SERIES]


def _event(state: ResearchState, node: str, status: str, **extra: Any) -> None:
    state.events.append({"run_id": state.run_id, "timestamp": datetime.now(timezone.utc).isoformat(),
                         "type": status, "node_id": node, **extra})


async def _node(state: ResearchState, name: str, operation: Callable[[], Any], validator: Callable[[Any], Any] | None = None) -> Any:
    state.current_node = name
    _event(state, name, "node_started")
    try:
        # Domain tools/agents are synchronous; offload them so the graph API stays async.
        result = await asyncio.to_thread(operation)
        if validator:
            result = validator(result)
        _event(state, name, "node_completed")
        return result
    except Exception as exc:
        state.errors.append(f"{name}: {type(exc).__name__}")
        state.warnings.append(f"Node {name} failed; dependent analysis may be incomplete.")
        _event(state, name, "node_failed", error_type=type(exc).__name__)
        return None


async def run_workflow(
    question: str,
    *,
    run_id: str | None = None,
    max_concurrency: int = 1,
    supplemental_econometrics: dict[str, Any] | None = None,
    document_evidence: list[dict[str, Any]] | None = None,
) -> ResearchState:
    """Run the fixed graph. `max_concurrency` is capped at one by design."""
    state = ResearchState(question=question[:MAX_QUESTION_LENGTH], **({"run_id": run_id} if run_id else {}))
    state.document_evidence = list(document_evidence or [])
    state.started_at = datetime.now(timezone.utc)
    if not question or len(question) > MAX_QUESTION_LENGTH:
        state.status = "FAILED"
        state.errors.append("question must contain 1 to 2000 characters")
        state.completed_at = datetime.now(timezone.utc)
        return state
    # Deterministic planning; no LLM call or model-produced facts.
    state.plan = await _node(state, "planner", lambda: planner.run_planner(question))
    if state.plan is None:
        state.status = "FAILED"
        state.completed_at = datetime.now(timezone.utc)
        return state

    series_ids = _validate_tools(state)
    # Registry-checked calls only. Each result retains source metadata from tool.
    data = await _node(state, "data", lambda: {
        "series": {sid: [ob.__dict__ for ob in load_series(sid)] for sid in series_ids},
        "required_series": series_ids,
        "missing_data": [sid for sid in series_ids if not load_series(sid)],
    }, lambda value: _require_dict(value))
    state.data = data
    state.retrieved_evidence = [ob for rows in (data or {}).get("series", {}).values() for ob in rows]

    state.growth = await _node(state, "growth", lambda: growth_agent.run_growth(question), lambda value: _require_model(AgentAnalysis, value))
    state.external = await _node(state, "external", lambda: external_agent.run_external(question), lambda value: _require_model(AgentAnalysis, value))
    state.inflation = await _node(state, "inflation", lambda: AgentAnalysis(
        summary="No dedicated inflation specialist is connected.", findings=[], evidence=[],
        uncertainties=[], missing_data=(data or {}).get("missing_data", []), recommended_next_steps=[]),
        lambda value: _require_model(AgentAnalysis, value))
    state.econometrics = await _node(state, "econometrics", lambda: _require_dict(econometrics_agent.run_econometrics(question)))
    if supplemental_econometrics:
        state.econometrics = {**(state.econometrics or {}), **supplemental_econometrics}
    evidence = []
    for analysis in (state.growth, state.external):
        if analysis:
            evidence.extend([item.model_dump() for item in analysis.evidence])
    state.policy = await _node(state, "policy", lambda: policy_agent.run_policy(question, evidence), lambda value: _require_model(PolicyAnalysis, value))
    state.critic = await _node(state, "critic", lambda: critic_agent.run_critic(
        state.plan.model_dump(), data or {}, state.growth.model_dump() if state.growth else {},
        state.external.model_dump() if state.external else {}, state.econometrics or {},
        state.policy.model_dump() if state.policy else {}, state.document_evidence or state.retrieved_evidence),
        lambda value: _require_model(CriticResult, value))
    empty_analysis = AgentAnalysis(summary="Unavailable after upstream node failure.", findings=[], evidence=[],
                                   uncertainties=["Upstream specialist unavailable."], missing_data=[],
                                   recommended_next_steps=[])
    empty_policy = PolicyAnalysis(stance="Unavailable after upstream node failure.", options=[], confidence=0.0,
                                 evidence=[], assumptions=[], warnings=["Upstream policy node unavailable."])
    state.final_report = await _node(state, "report", lambda: report_agent.run_report(
        state.plan.model_dump(), data or {}, state.growth or empty_analysis, state.external or empty_analysis,
        state.econometrics or {}, state.policy or empty_policy,
        state.critic.model_dump() if state.critic else {}, state.document_evidence),
        lambda value: _require_model(ReportResult, value))
    state.status = "COMPLETED" if not state.errors else "COMPLETED_WITH_ERRORS"
    state.current_node = None
    state.completed_at = datetime.now(timezone.utc)
    return state


def _require_dict(value: Any) -> dict:
    if not isinstance(value, dict):
        raise ValueError("expected a dictionary")
    return value


def _require_model(model: type, value: Any) -> Any:
    if isinstance(value, model):
        return value
    if isinstance(value, dict):
        return model.model_validate(value)
    raise ValueError(f"expected {model.__name__} or a schema-compatible dictionary")


async def build_workflow(question: str) -> ResearchState:
    """Compatibility entry point for callers expecting a built graph runner."""
    return await run_workflow(question)

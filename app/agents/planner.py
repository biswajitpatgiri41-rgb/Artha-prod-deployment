"""Deterministic research planner; plans contain no model-generated facts."""
from __future__ import annotations

from .schemas import ResearchPlan

# Explicit phrase-to-canonical-tool mapping. Unknown input never becomes a tool name.
_SERIES_TERMS = {
    "cpi_headline": ("cpi", "inflation"),
    "food_inflation": ("food",),
    "brent_crude": ("oil", "brent", "crude"),
    "inr_usd": ("inr", "rupee", "exchange rate", "fx"),
    "repo_rate": ("repo", "policy rate", "interest rate"),
    "iip": ("iip", "industrial production"),
    "cpi_yoy": ("year-on-year", "yoy"),
}

def run_planner(question: str) -> ResearchPlan:
    """Create a schema-validated plan from allowlisted keyword matches only."""
    if not isinstance(question, str) or not question.strip() or len(question) > 2000:
        raise ValueError("question must contain 1 to 2000 characters")
    normalized = question.casefold()
    indicators = [series for series, terms in _SERIES_TERMS.items()
                  if any(term in normalized for term in terms)]
    if not indicators:
        indicators = ["cpi_headline"]
    agents = ["growth", "external", "econometrics", "policy", "critic", "report"]
    return ResearchPlan(
        objective=question.strip(),
        tasks=["retrieve registered local observations", "summarize deterministic specialist outputs", "validate evidence and report"],
        required_indicators=indicators,
        required_agents=agents,
        requires_scenario=False,
        assumptions=["Only observations present in project data are used; unavailable values remain missing."],
        dependencies=["registered-series-tool"],
    )

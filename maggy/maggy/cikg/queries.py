"""CIKG query functions — gap analysis and market scoring."""

from __future__ import annotations

from .graph import KnowledgeGraphService
from .models import MarketScore


def find_gaps(
    graph: KnowledgeGraphService,
    feature_name: str,
) -> MarketScore:
    """Score a feature against the competitive landscape."""
    results = graph.find_gaps(feature_name)
    have_it = sum(1 for item in results if item["status"] == "has")
    gap = len(results) - have_it
    threat = _threat_level(have_it, len(results))
    return MarketScore(
        feature=feature_name,
        gap_count=gap,
        threat_level=threat,
        recommendation=_gap_recommendation(feature_name, have_it, len(results), threat),
    )


def compare_entities(
    graph: KnowledgeGraphService,
    id_a: str, id_b: str,
) -> dict:
    """Compare two entities by their features."""
    return graph.compare_entities(id_a, id_b)


def get_landscape(
    graph: KnowledgeGraphService,
) -> dict:
    """Return competitive landscape summary."""
    competitors = graph.list_nodes("competitor")
    features = graph.list_nodes("feature")
    techs = graph.list_nodes("technology")
    return {
        "competitors": len(competitors),
        "features_tracked": len(features),
        "technologies": len(techs),
        "top_competitors": [
            c.name for c in competitors[:10]
        ],
    }


def _gap_recommendation(
    feature_name: str,
    have_it: int,
    total: int,
    threat: str,
) -> str:
    if have_it == 0:
        return f"No competitor has '{feature_name}' — potential differentiator"
    suffix = {
        "high": "Table stakes — must have.",
        "medium": "Growing trend.",
        "low": "Differentiator opportunity.",
    }[threat]
    return f"{have_it}/{total} competitors have this. {suffix}"


def _threat_level(have_it: int, total: int) -> str:
    if total == 0:
        return "low"
    ratio = have_it / total
    if ratio > 0.7:
        return "high"
    if ratio > 0.3:
        return "medium"
    return "low"

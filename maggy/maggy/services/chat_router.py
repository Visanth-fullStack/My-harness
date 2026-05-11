"""Routed chat — blast-score routing for interactive messages.

Estimates complexity from message keywords, routes to the optimal
model via RoutingService, and builds CLI commands for any model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from maggy.routing import RoutingContext

HIGH_KEYWORDS = frozenset({
    "security", "auth", "authentication", "authorization",
    "oauth", "encrypt", "vulnerability", "architecture",
    "refactor", "redesign", "migrate", "migration",
    "database", "schema", "performance", "optimize",
    "deploy", "infrastructure", "cicd", "pipeline",
})
MID_KEYWORDS = frozenset({
    "feature", "implement", "build", "create", "api",
    "endpoint", "component", "service", "integration",
    "pagination", "filter", "search", "cache",
})
LOW_KEYWORDS = frozenset({
    "fix", "typo", "rename", "move", "style", "format",
    "lint", "comment", "readme", "docs", "log", "print",
    "bump", "version", "config", "env", "update",
})
TYPE_KEYWORDS: dict[str, frozenset[str]] = {
    "security": frozenset({
        "auth", "authentication", "authorization",
        "security", "permission", "token",
        "encrypt", "vulnerability", "oauth", "csrf",
    }),
    "docs": frozenset({
        "document", "documentation", "readme", "docs",
        "docstring", "comment", "spec", "jsdoc", "write",
    }),
    "tests": frozenset({
        "test", "spec", "coverage", "mock", "fixture",
        "assert", "pytest", "jest", "vitest",
    }),
    "frontend": frozenset({
        "component", "css", "style", "ui", "layout",
        "responsive", "tailwind", "react", "vue",
    }),
}
DEFAULT_BLAST = 5


def estimate_blast(message: str) -> int:
    """Estimate blast score (1-10) from message text."""
    if not message.strip():
        return DEFAULT_BLAST
    words = set(re.findall(r"[a-zA-Z]+", message.lower()))
    high = len(words & HIGH_KEYWORDS)
    mid = len(words & MID_KEYWORDS)
    low = len(words & LOW_KEYWORDS)
    if high >= 2:
        return min(9, 7 + high - 2)
    if high == 1:
        return 7
    if low >= 2 and mid == 0:
        return 2
    if low >= 1 and mid == 0:
        return 3
    if mid >= 2:
        return 6
    if mid >= 1:
        return 5
    return DEFAULT_BLAST


def estimate_type(message: str) -> str:
    """Estimate task type from message keywords."""
    words = set(re.findall(r"[a-zA-Z]+", message.lower()))
    best_type = "general"
    best_count = 0
    for ttype, keywords in TYPE_KEYWORDS.items():
        count = len(words & keywords)
        if count > best_count:
            best_count = count
            best_type = ttype
    return best_type


@dataclass
class RouteDecision:
    """Result of routing a chat message."""

    model: str
    reason: str
    blast: int
    task_type: str


class RoutedChat:
    """Routes chat messages through blast-score engine."""

    def __init__(self, routing, budget):
        self._routing = routing
        self._budget = budget

    def decide(
        self,
        message: str,
        blast_override: int | None = None,
        type_override: str | None = None,
    ) -> RouteDecision:
        """Get routing decision for a message."""
        blast = blast_override or estimate_blast(message)
        task_type = type_override or estimate_type(message)
        ctx = RoutingContext(
            blast_score=blast, task_type=task_type,
        )
        decision = self._routing.route(ctx)
        model_name = self._model_name(decision.primary)
        return RouteDecision(
            model=model_name,
            reason=decision.reason,
            blast=blast,
            task_type=task_type,
        )

    def _model_name(self, primary) -> str:
        if isinstance(primary, str):
            return primary
        return str(getattr(primary, "name", primary))

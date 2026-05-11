"""Tests for routed chat — multi-model routing in ChatManager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maggy.services.chat_router import estimate_blast, estimate_type


class TestBlastEstimation:
    """Blast score estimation from message keywords."""

    def test_low_blast_simple_fix(self):
        assert estimate_blast("fix the typo in README") <= 3

    def test_high_blast_security(self):
        assert estimate_blast("design auth system with OAuth") >= 7

    def test_high_blast_architecture(self):
        assert estimate_blast("refactor database schema") >= 5

    def test_medium_blast_feature(self):
        score = estimate_blast("add pagination to the API")
        assert 3 <= score <= 6

    def test_empty_returns_default(self):
        assert estimate_blast("") == 5


class TestTypeEstimation:
    """Task type estimation from message keywords."""

    def test_security_type(self):
        assert estimate_type("fix authentication bug") == "security"

    def test_docs_type(self):
        assert estimate_type("write documentation for API") == "docs"

    def test_test_type(self):
        assert estimate_type("add unit tests with mock fixtures") == "tests"

    def test_general_default(self):
        assert estimate_type("make it faster") == "general"


class TestRoutedEndpoint:
    """API endpoint /send-routed returns routing metadata."""

    @pytest.mark.asyncio
    async def test_send_routed_yields_routing_chunk(self):
        """First SSE chunk should be routing decision."""
        from maggy.services.chat_router import RoutedChat

        mock_routing = MagicMock()
        mock_routing.route.return_value = MagicMock(
            primary=MagicMock(name="claude"),
            reason="blast 8 → claude",
        )
        mock_budget = MagicMock()
        mock_budget.check.return_value = True

        rc = RoutedChat(mock_routing, mock_budget)
        # We only test the routing decision, not the full send
        decision = rc.decide("design auth system", None, None)
        assert decision is not None
        mock_routing.route.assert_called_once()

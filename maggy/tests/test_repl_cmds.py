"""Tests for REPL slash command handlers."""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import MagicMock

from maggy.cli_repl_cmds import (
    cmd_budget,
    cmd_claude_md,
    cmd_help,
    cmd_models,
    cmd_route,
    cmd_stats,
    cmd_use,
    dispatch,
)


@dataclass
class FakeState:
    working_dir: str = "/tmp/proj"
    session_id: str = "s1"
    allowed_models: list[str] = field(default_factory=list)


def _mock_client():
    c = MagicMock()
    c.budget_summary.return_value = {
        "spent_today_usd": 1.5,
        "daily_limit_usd": 10.0,
        "status": "ok",
    }
    c.budget_by_provider.return_value = [
        {"provider": "anthropic", "spent_usd": 1.2},
        {"provider": "openai", "spent_usd": 0.3},
    ]
    c.models_heatmap.return_value = [
        {"model": "claude", "task_type": "security",
         "avg_reward": 0.95, "samples": 10},
    ]
    c.routing_rules.return_value = {
        "mode": "dynamic",
        "task_type_overrides": {
            "security": {"model": "claude", "reason": "deep"},
        },
        "model_performance": {
            "claude": {"success_rate": 1.0, "strengths": ["security"]},
        },
    }
    c.config.return_value = {
        "codebases": [{"key": "proj", "path": "/tmp/proj"}],
        "routing": {"mode": "dynamic"},
        "budget": {"daily_limit_usd": 10.0},
    }
    return c


def test_dispatch_stats(capsys):
    """'/stats' dispatches to stats handler."""
    client = _mock_client()
    state = FakeState()
    handled = dispatch("/stats", client, state)
    assert handled is True


def test_dispatch_unknown():
    """Unknown commands return False."""
    handled = dispatch("/xyz123", MagicMock(), FakeState())
    assert handled is False


def test_cmd_stats(capsys):
    """Stats shows budget and model perf."""
    cmd_stats(_mock_client())
    out = capsys.readouterr().out
    assert "1.5" in out or "budget" in out.lower()


def test_cmd_budget(capsys):
    """Budget shows per-provider breakdown."""
    cmd_budget(_mock_client())
    out = capsys.readouterr().out
    assert "anthropic" in out or "1.2" in out


def test_cmd_route(capsys):
    """Route shows task type overrides."""
    cmd_route(_mock_client())
    out = capsys.readouterr().out
    assert "security" in out or "claude" in out


def test_cmd_models(capsys):
    """Models shows reward heatmap."""
    cmd_models(_mock_client())
    out = capsys.readouterr().out
    assert "claude" in out or "0.95" in out


def test_cmd_use_sets_models():
    """'/use claude,codex' sets allowed_models."""
    state = FakeState()
    cmd_use("claude,codex", state)
    assert state.allowed_models == ["claude", "codex"]


def test_cmd_use_reset():
    """'/use all' clears allowed_models."""
    state = FakeState(allowed_models=["claude"])
    cmd_use("all", state)
    assert state.allowed_models == []


def test_cmd_claude_md_missing(capsys):
    """Shows message when CLAUDE.md not found."""
    state = FakeState(working_dir="/nonexistent_xyz_dir")
    cmd_claude_md(state)
    out = capsys.readouterr().out
    assert "not found" in out.lower() or "no" in out.lower()


def test_cmd_help(capsys):
    """Help lists all commands."""
    cmd_help()
    out = capsys.readouterr().out
    assert "/stats" in out
    assert "/use" in out
    assert "/help" in out

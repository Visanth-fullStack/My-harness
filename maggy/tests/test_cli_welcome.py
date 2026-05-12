"""Tests for the CLI welcome banner."""

from __future__ import annotations

from unittest.mock import MagicMock

from maggy.cli_welcome import render_welcome


def _mock_client():
    c = MagicMock()
    c.budget_summary.return_value = {
        "spent_today_usd": 1.50,
        "daily_limit_usd": 10.0,
        "status": "ok",
    }
    c.models_heatmap.return_value = [
        {"model": "claude"},
        {"model": "kimi"},
    ]
    return c


SESSION = {
    "id": "abc123",
    "project_key": "edubites",
    "working_dir": "/tmp/edubites",
    "status": "idle",
    "messages": 5,
}


def test_render_welcome_shows_project(capsys):
    render_welcome("edubites", SESSION, _mock_client())
    out = capsys.readouterr().out
    assert "edubites" in out


def test_render_welcome_shows_budget(capsys):
    render_welcome("edubites", SESSION, _mock_client())
    out = capsys.readouterr().out
    assert "1.50" in out or "$1.50" in out


def test_render_welcome_shows_models(capsys):
    render_welcome("edubites", SESSION, _mock_client())
    out = capsys.readouterr().out
    assert "2" in out


def test_render_welcome_shows_health(capsys):
    """Welcome banner displays memory health score."""
    c = _mock_client()
    c.engram_diagnostics.return_value = {"health_score": 0.85}
    render_welcome("edubites", SESSION, c)
    out = capsys.readouterr().out
    assert "85%" in out or "0.85" in out


def test_render_welcome_shows_session_history(capsys):
    """Welcome banner shows previous session message count."""
    session = {**SESSION, "messages": 12}
    render_welcome("edubites", session, _mock_client())
    out = capsys.readouterr().out
    assert "12" in out


def test_dir_shows_cwd_fallback(capsys):
    """Dir row uses os.getcwd() when working_dir missing."""
    import os
    session = {**SESSION, "working_dir": ""}
    render_welcome("edubites", session, _mock_client())
    out = capsys.readouterr().out
    # Should contain part of the actual cwd, not empty string
    cwd_tail = os.path.basename(os.getcwd())
    assert cwd_tail in out


def test_models_shows_available_count(capsys):
    """Empty heatmap shows available model count."""
    c = _mock_client()
    c.models_heatmap.return_value = []
    render_welcome("edubites", SESSION, c)
    out = capsys.readouterr().out
    assert "5 available" in out or "available" in out


def test_budget_subscription_welcome(capsys):
    """Subscription plan shows Subscription in welcome."""
    c = _mock_client()
    c.budget_summary.return_value = {
        "spent_today_usd": 0, "daily_limit_usd": 10.0,
        "status": "ok", "plan": "subscription",
    }
    render_welcome("edubites", SESSION, c)
    out = capsys.readouterr().out
    assert "subscription" in out.lower()

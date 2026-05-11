"""Tests for maggy chat CLI — interactive REPL."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from maggy.cli import app

runner = CliRunner()

SESSION = {
    "id": "abc123",
    "project_key": "my-proj",
    "working_dir": "/tmp/my-proj",
    "status": "idle",
}

HISTORY = {
    "id": "abc123",
    "project_key": "my-proj",
    "messages": [
        {"role": "user", "content": "hello", "timestamp": "2026-01-01T00:00:00"},
        {"role": "assistant", "content": "hi", "timestamp": "2026-01-01T00:00:01"},
    ],
}


@patch("maggy.cli._client")
def test_chat_creates_session(mock_client):
    """Chat command creates a session and enters REPL."""
    mock_client.ensure_server.return_value = True
    mock_client.chat_create.return_value = SESSION
    with patch("maggy.cli_chat.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = ["/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0
    assert "my-proj" in result.output
    mock_client.chat_create.assert_called_once_with("my-proj")


@patch("maggy.cli._client")
def test_chat_routed_streams(mock_client):
    """Routed chat sends via send_routed and shows model."""
    mock_client.ensure_server.return_value = True
    mock_client.chat_create.return_value = SESSION
    mock_client.chat_send_routed.return_value = iter([
        {"type": "routing", "model": "kimi", "blast": 3, "task_type": "general", "reason": "low blast"},
        {"type": "text", "content": "Hello"},
        {"type": "done"},
    ])
    with patch("maggy.cli_chat.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = ["say hi", "/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0
    mock_client.chat_send_routed.assert_called_once_with(
        "abc123", "say hi", blast=None,
    )


@patch("maggy.cli._client")
def test_chat_direct_mode(mock_client):
    """--direct flag uses send_stream instead of routed."""
    mock_client.ensure_server.return_value = True
    mock_client.chat_create.return_value = SESSION
    mock_client.chat_send_stream.return_value = iter([
        {"type": "text", "content": "Hi"},
        {"type": "done"},
    ])
    with patch("maggy.cli_chat.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = ["say hi", "/quit"]
        result = runner.invoke(app, ["chat", "my-proj", "--direct"])
    assert result.exit_code == 0
    mock_client.chat_send_stream.assert_called_once_with(
        "abc123", "say hi",
    )


@patch("maggy.cli._client")
def test_chat_history_command(mock_client):
    mock_client.ensure_server.return_value = True
    mock_client.chat_create.return_value = SESSION
    mock_client.chat_history.return_value = HISTORY
    with patch("maggy.cli_chat.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = ["/history", "/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0
    mock_client.chat_history.assert_called_once_with("abc123")


@patch("maggy.cli._client")
def test_chat_blast_override(mock_client):
    """'/blast 8' sets override for next message."""
    mock_client.ensure_server.return_value = True
    mock_client.chat_create.return_value = SESSION
    mock_client.chat_send_routed.return_value = iter([
        {"type": "routing", "model": "claude", "blast": 8, "task_type": "general", "reason": "override"},
        {"type": "text", "content": "Done"},
        {"type": "done"},
    ])
    with patch("maggy.cli_chat.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = ["/blast 8", "do it", "/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0
    mock_client.chat_send_routed.assert_called_once_with(
        "abc123", "do it", blast=8,
    )


@patch("maggy.cli._client")
def test_chat_ctrl_c_exits(mock_client):
    mock_client.ensure_server.return_value = True
    mock_client.chat_create.return_value = SESSION
    with patch("maggy.cli_chat.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = KeyboardInterrupt
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0


@patch("maggy.cli._client")
def test_chat_empty_input_ignored(mock_client):
    mock_client.ensure_server.return_value = True
    mock_client.chat_create.return_value = SESSION
    with patch("maggy.cli_chat.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = ["", "  ", "/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0
    mock_client.chat_send_routed.assert_not_called()


@patch("maggy.cli._client")
def test_chat_error_displayed(mock_client):
    mock_client.ensure_server.return_value = True
    mock_client.chat_create.return_value = SESSION
    mock_client.chat_send_routed.return_value = iter([
        {"type": "error", "content": "CLI not found"},
        {"type": "done"},
    ])
    with patch("maggy.cli_chat.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = ["test", "/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0

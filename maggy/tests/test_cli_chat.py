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


def _sse_lines(*chunks: dict) -> list[str]:
    """Build SSE data lines from chunk dicts."""
    lines = [f"data: {json.dumps(c)}" for c in chunks]
    lines.append(f'data: {{"type": "done"}}')
    return lines


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
def test_chat_streams_response(mock_client):
    """Chat sends message and streams SSE response."""
    mock_client.ensure_server.return_value = True
    mock_client.chat_create.return_value = SESSION
    chunks = [
        {"type": "text", "content": "Hello "},
        {"type": "text", "content": "world"},
    ]
    mock_client.chat_send_stream.return_value = iter(
        chunks + [{"type": "done"}],
    )
    with patch("maggy.cli_chat.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = ["say hi", "/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0
    mock_client.chat_send_stream.assert_called_once_with(
        "abc123", "say hi",
    )


@patch("maggy.cli._client")
def test_chat_history_command(mock_client):
    """The /history slash command shows message history."""
    mock_client.ensure_server.return_value = True
    mock_client.chat_create.return_value = SESSION
    mock_client.chat_history.return_value = HISTORY
    with patch("maggy.cli_chat.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = ["/history", "/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0
    mock_client.chat_history.assert_called_once_with("abc123")


@patch("maggy.cli._client")
def test_chat_sessions_command(mock_client):
    """/sessions shows all chat sessions."""
    mock_client.ensure_server.return_value = True
    mock_client.chat_create.return_value = SESSION
    mock_client.chat_sessions.return_value = [
        {"id": "abc123", "project_key": "my-proj", "status": "idle", "messages": 2},
    ]
    with patch("maggy.cli_chat.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = ["/sessions", "/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0
    mock_client.chat_sessions.assert_called_once()


@patch("maggy.cli._client")
def test_chat_clear_command(mock_client):
    """/clear clears screen without error."""
    mock_client.ensure_server.return_value = True
    mock_client.chat_create.return_value = SESSION
    with patch("maggy.cli_chat.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = ["/clear", "/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0


@patch("maggy.cli._client")
def test_chat_ctrl_c_exits(mock_client):
    """Ctrl+C (KeyboardInterrupt) exits gracefully."""
    mock_client.ensure_server.return_value = True
    mock_client.chat_create.return_value = SESSION
    with patch("maggy.cli_chat.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = KeyboardInterrupt
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0


@patch("maggy.cli._client")
def test_chat_empty_input_ignored(mock_client):
    """Empty input is skipped without sending."""
    mock_client.ensure_server.return_value = True
    mock_client.chat_create.return_value = SESSION
    with patch("maggy.cli_chat.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = ["", "  ", "/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0
    mock_client.chat_send_stream.assert_not_called()


@patch("maggy.cli._client")
def test_chat_error_chunk_displayed(mock_client):
    """Error chunks from SSE are displayed."""
    mock_client.ensure_server.return_value = True
    mock_client.chat_create.return_value = SESSION
    mock_client.chat_send_stream.return_value = iter([
        {"type": "error", "content": "claude CLI not found"},
        {"type": "done"},
    ])
    with patch("maggy.cli_chat.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = ["test", "/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0

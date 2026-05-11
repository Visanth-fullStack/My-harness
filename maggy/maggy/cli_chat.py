"""Interactive chat REPL for Maggy CLI with model routing."""

from __future__ import annotations

import os

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.table import Table

console = Console()


def detect_project(client) -> str | None:
    """Auto-detect project from current working directory."""
    return client.detect_project(os.getcwd())


def run_chat(
    client, project: str,
    routed: bool = True,
) -> None:
    """Main chat REPL loop."""
    session = client.chat_create(project)
    sid = session.get("id", "?")
    wd = session.get("working_dir", "?")
    console.print(
        f"Connected to [bold]{project}[/bold] "
        f"(session {sid})",
    )
    console.print(f"Working dir: {wd}")
    mode = "routed" if routed else "direct"
    console.print(
        f"[dim]Mode: {mode} | "
        f"/blast N /history /sessions /quit[/dim]\n",
    )
    _repl_loop(client, sid, routed)
    console.print("[dim]Session saved. Bye.[/dim]")


def _repl_loop(
    client, session_id: str, routed: bool,
) -> None:
    """Prompt loop with blast override support."""
    blast_override: int | None = None
    while True:
        try:
            text = Prompt.ask("[bold cyan]maggy[/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            console.print()
            break
        stripped = text.strip()
        if not stripped:
            continue
        if stripped == "/quit":
            break
        if stripped == "/history":
            _show_history(client, session_id)
            continue
        if stripped == "/sessions":
            _show_sessions(client)
            continue
        if stripped == "/clear":
            console.clear()
            continue
        if stripped.startswith("/blast"):
            blast_override = _parse_blast(stripped)
            continue
        if routed:
            _stream_routed(
                client, session_id, stripped,
                blast_override,
            )
        else:
            _stream_response(client, session_id, stripped)
        blast_override = None


def _parse_blast(text: str) -> int | None:
    """Parse /blast N command."""
    parts = text.split()
    if len(parts) >= 2:
        try:
            val = int(parts[1])
            val = max(1, min(10, val))
            console.print(
                f"[dim]Blast override set to {val}[/dim]",
            )
            return val
        except ValueError:
            pass
    console.print("[dim]Usage: /blast N (1-10)[/dim]")
    return None


def _stream_routed(
    client, session_id: str, message: str,
    blast: int | None = None,
) -> None:
    """Stream via routed endpoint, show model info."""
    full_text = ""
    error_text = ""
    try:
        with Live(
            Markdown(""), console=console,
            refresh_per_second=8,
        ) as live:
            for chunk in client.chat_send_routed(
                session_id, message, blast=blast,
            ):
                ctype = chunk.get("type", "")
                if ctype == "routing":
                    model = chunk.get("model", "?")
                    blast_v = chunk.get("blast", "?")
                    reason = chunk.get("reason", "")
                    console.print(
                        f"[dim][{model}] blast={blast_v}"
                        f" {reason}[/dim]",
                    )
                elif ctype in ("text", "result"):
                    full_text += chunk.get("content", "")
                    live.update(Markdown(full_text))
                elif ctype == "error":
                    error_text = chunk.get("content", "")
                elif ctype == "done":
                    break
    except Exception as e:
        error_text = str(e)
    if error_text:
        console.print(f"[red]Error:[/red] {error_text}")


def _stream_response(
    client, session_id: str, message: str,
) -> None:
    """Stream plain (non-routed) response."""
    full_text = ""
    error_text = ""
    try:
        with Live(
            Markdown(""), console=console,
            refresh_per_second=8,
        ) as live:
            for chunk in client.chat_send_stream(
                session_id, message,
            ):
                ctype = chunk.get("type", "")
                if ctype in ("text", "result"):
                    full_text += chunk.get("content", "")
                    live.update(Markdown(full_text))
                elif ctype == "error":
                    error_text = chunk.get("content", "")
                elif ctype == "done":
                    break
    except Exception as e:
        error_text = str(e)
    if error_text:
        console.print(f"[red]Error:[/red] {error_text}")


def _show_history(client, session_id: str) -> None:
    """Display message history."""
    data = client.chat_history(session_id)
    messages = data.get("messages", [])
    if not messages:
        console.print("[dim]No messages yet.[/dim]")
        return
    for msg in messages:
        role = msg.get("role", "?")
        content = msg.get("content", "")
        if role == "user":
            console.print(f"\n[bold cyan]You:[/bold cyan] {content}")
        else:
            console.print("\n[bold green]Maggy:[/bold green]")
            console.print(Markdown(content))


def _show_sessions(client) -> None:
    """List all active sessions."""
    sessions = client.chat_sessions()
    if not sessions:
        console.print("[dim]No chat sessions.[/dim]")
        return
    t = Table(title="Chat Sessions")
    t.add_column("ID", width=12)
    t.add_column("Project")
    t.add_column("Status")
    t.add_column("Messages", justify="right")
    for s in sessions:
        t.add_row(
            s.get("id", "?"),
            s.get("project_key", "?"),
            s.get("status", "?"),
            str(s.get("messages", 0)),
        )
    console.print(t)

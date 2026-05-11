"""Interactive chat REPL for Maggy CLI."""

from __future__ import annotations

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.table import Table

console = Console()


def run_chat(client, project: str) -> None:
    """Main chat REPL loop."""
    session = client.chat_create(project)
    sid = session.get("id", "?")
    wd = session.get("working_dir", "?")
    console.print(
        f"Connected to [bold]{project}[/bold] "
        f"(session {sid})",
    )
    console.print(f"Working dir: {wd}")
    console.print(
        "[dim]Commands: /history /sessions "
        "/clear /quit[/dim]\n",
    )
    _repl_loop(client, sid)
    console.print("[dim]Session saved. Bye.[/dim]")


def _repl_loop(client, session_id: str) -> None:
    """Prompt loop — reads input, dispatches."""
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
        _stream_response(client, session_id, stripped)


def _stream_response(
    client, session_id: str, message: str,
) -> None:
    """Stream SSE chunks and render as Markdown."""
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
                content = chunk.get("content", "")
                if ctype in ("text", "result"):
                    full_text += content
                    live.update(Markdown(full_text))
                elif ctype == "error":
                    error_text = content
                elif ctype == "done":
                    break
    except Exception as e:
        error_text = str(e)
    if error_text:
        console.print(f"[red]Error:[/red] {error_text}")


def _show_history(client, session_id: str) -> None:
    """Display message history for current session."""
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
    """List all active chat sessions."""
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

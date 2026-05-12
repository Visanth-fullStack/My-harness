"""Interactive chat REPL for Maggy CLI with model routing."""
from __future__ import annotations

import os

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.spinner import Spinner
from rich.table import Table

from maggy.cli_repl_cmds import SessionState, dispatch
from maggy.cli_welcome import render_welcome
from maggy.services.session_detect import detect_all

console = Console()

EXIT_WORDS = frozenset({"exit", "bye", "quit", "/exit", "/bye"})
_QUOTA_MARKERS = ("rate_limit", "quota", "exceeded", "429")


def detect_project(client) -> str | None:
    """Auto-detect project from current working directory."""
    return client.detect_project(os.getcwd())


def run_chat(
    client, project: str, routed: bool = True,
) -> None:
    session, resumed = _find_or_create(client, project)
    sid = session.get("id", "?")
    wd = session.get("working_dir", "?")
    render_welcome(project, session, client)
    _show_resume_info(client, sid, wd)
    state = SessionState(session_id=sid, working_dir=wd)
    _repl_loop(client, state, routed)
    console.print("[dim]Session saved. Bye.[/dim]")


def _find_or_create(
    client, project: str,
) -> tuple[dict, bool]:
    """Find existing session or create new one."""
    for s in client.chat_sessions():
        if s.get("project_key") == project:
            return s, True
    return client.chat_create(project), False


def _show_resume_info(client, sid: str, wd: str) -> None:
    """Show detected CLI sessions and recent messages."""
    detected = detect_all(wd)
    if detected.sessions:
        parts = [f"{s.cli}({s.session_id[:8]})" for s in detected.sessions]
        console.print(f"[dim]Prior: {', '.join(parts)}[/dim]")
    msgs = client.chat_history(sid).get("messages", [])[-3:]
    if not msgs:
        return
    console.print("[dim]--- Recent ---[/dim]")
    for msg in msgs:
        role = msg.get("role", "?")
        text = msg.get("content", "")[:120]
        tag = "[cyan]You[/cyan]" if role == "user" else "[green]Maggy[/green]"
        console.print(f"  {tag}: {text}")


def _repl_loop(
    client, state: SessionState, routed: bool,
) -> None:
    """Prompt loop with blast override support."""
    blast_override: int | None = None
    while True:
        try:
            text = Prompt.ask("[bold cyan]>[/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            console.print()
            break
        stripped = text.strip()
        if not stripped:
            continue
        if stripped == "/quit" or stripped.lower() in EXIT_WORDS:
            break
        if stripped == "/history":
            _show_history(client, state.session_id)
            continue
        if stripped == "/sessions":
            _show_sessions(client)
            continue
        if stripped == "/clear":
            console.clear()
            continue
        if stripped.startswith("/monitor"):
            sub = stripped.split()[1] if len(stripped.split()) > 1 else "status"
            data = client.monitor_status() if sub == "status" else {}
            console.print(f"[dim]Monitors: {data.get('active', 0)} active[/dim]")
            continue
        if stripped.startswith("/blast"):
            blast_override = _parse_blast(stripped)
            continue
        if dispatch(stripped, client, state):
            continue
        if routed:
            chunks = client.chat_send_routed(
                state.session_id, stripped,
                blast=blast_override,
                allowed_models=state.allowed_models or None,
            )
        else:
            chunks = client.chat_send_stream(
                state.session_id, stripped,
            )
        _stream_chunks(chunks)
        blast_override = None


def _parse_blast(text: str) -> int | None:
    """Parse /blast N command."""
    parts = text.split()
    if len(parts) >= 2:
        try:
            val = max(1, min(10, int(parts[1])))
            console.print(f"[dim]Blast override: {val}[/dim]")
            return val
        except ValueError:
            pass
    console.print("[dim]Usage: /blast N (1-10)[/dim]")
    return None


def _stream_chunks(chunks) -> None:
    """Stream and display response chunks from any model."""
    full, err = "", ""
    try:
        with Live(
            Spinner("dots", text="Thinking..."),
            console=console, refresh_per_second=8,
        ) as live:
            for chunk in chunks:
                ct = chunk.get("type", "")
                if ct == "routing":
                    _show_routing(chunk)
                elif ct == "queued":
                    pos = chunk.get("position", "?")
                    live.update(Markdown(f"[dim]Queued (position {pos})[/dim]"))
                elif ct == "warning":
                    console.print(f"[yellow]{chunk.get('content', '')}[/yellow]")
                elif ct == "agent_status":
                    a = chunk.get("agent", "?")
                    s = chunk.get("status", "")
                    console.print(f"[dim]@{a}> {s}[/dim]")
                elif ct in ("text", "result"):
                    full += chunk.get("content", "")
                    live.update(Markdown(full))
                elif ct == "error":
                    err = chunk.get("content", "")
                elif ct == "done":
                    break
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted[/dim]")
    except Exception as e:
        err = str(e)
    if err:
        console.print(f"[red]Error:[/red] {err}")
        if any(m in err.lower() for m in _QUOTA_MARKERS):
            from maggy.services.account_guide import render_switch_guide
            render_switch_guide("anthropic")


def _show_routing(chunk: dict) -> None:
    console.print(f"[dim][{chunk.get('model', '?')}] blast={chunk.get('blast', '?')} {chunk.get('reason', '')}[/dim]")


def _show_history(client, session_id: str) -> None:
    msgs = client.chat_history(session_id).get("messages", [])
    if not msgs:
        console.print("[dim]No messages yet.[/dim]")
        return
    for msg in msgs:
        role, content = msg.get("role", "?"), msg.get("content", "")
        tag = "[bold cyan]You[/bold cyan]" if role == "user" else "[bold green]Maggy[/bold green]"
        console.print(f"\n{tag}: {content}" if role == "user" else f"\n{tag}:")
        if role != "user":
            console.print(Markdown(content))


def _show_sessions(client) -> None:
    sessions = client.chat_sessions()
    if not sessions:
        console.print("[dim]No chat sessions.[/dim]")
        return
    t = Table(title="Chat Sessions")
    for col in ("ID", "Project", "Status"):
        t.add_column(col)
    t.add_column("Messages", justify="right")
    for s in sessions:
        t.add_row(s.get("id", "?"), s.get("project_key", "?"), s.get("status", "?"), str(s.get("messages", 0)))
    console.print(t)

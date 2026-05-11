"""REPL slash command handlers for Maggy CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

console = Console()


@dataclass
class SessionState:
    """Mutable session-level state for REPL."""

    session_id: str = ""
    working_dir: str = ""
    allowed_models: list[str] = field(default_factory=list)


def dispatch(cmd: str, client, state: SessionState) -> bool:
    """Route a slash command. Returns True if handled."""
    parts = cmd.strip().split(None, 1)
    name = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    if name == "/stats":
        cmd_stats(client)
    elif name == "/budget":
        cmd_budget(client)
    elif name == "/route":
        cmd_route(client)
    elif name == "/models":
        cmd_models(client)
    elif name == "/use":
        cmd_use(args, state)
    elif name == "/config":
        cmd_config(client)
    elif name == "/claude-md":
        cmd_claude_md(state)
    elif name == "/help":
        cmd_help()
    else:
        return False
    return True


def cmd_stats(client) -> None:
    """Budget + model performance summary."""
    b = client.budget_summary()
    t = Table(title="Stats")
    t.add_column("Metric", style="bold")
    t.add_column("Value")
    spent = b.get("spent_today_usd", 0)
    limit = b.get("daily_limit_usd", 0)
    t.add_row("Spent", f"${spent:.2f} / ${limit:.2f}")
    t.add_row("Status", b.get("status", "?"))
    for p in client.budget_by_provider():
        t.add_row(
            f"  {p.get('provider', '?')}",
            f"${p.get('spent_usd', 0):.2f}",
        )
    for h in client.models_heatmap()[:8]:
        r = h.get("avg_reward", 0)
        c = "green" if r >= 0.8 else "yellow"
        t.add_row(
            f"  {h.get('model', '?')} ({h.get('task_type', '')})",
            f"[{c}]{r:.2f}[/{c}] ({h.get('samples', 0)})",
        )
    console.print(t)


def cmd_budget(client) -> None:
    """Detailed budget breakdown by provider."""
    b = client.budget_summary()
    spent = b.get("spent_today_usd", 0)
    limit = b.get("daily_limit_usd", 0)
    pct = (spent / limit * 100) if limit else 0
    bl = min(20, int(pct / 5))
    c = "red" if pct > 80 else "green"
    bar = f"[{c}]{'█' * bl}[/{c}]{'░' * (20 - bl)}"
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(style="bold")
    t.add_column()
    t.add_row("Spent", f"${spent:.2f} / ${limit:.2f}")
    t.add_row("Usage", f"{pct:.0f}%  {bar}")
    t.add_row("Status", b.get("status", "?"))
    for p in client.budget_by_provider():
        t.add_row(p.get("provider", "?"), f"${p.get('spent_usd', 0):.2f}")
    console.print(Panel(t, title="Budget", border_style="green"))


def cmd_route(client) -> None:
    """Show routing rules and model performance."""
    data = client.routing_rules()
    t = Table(title=f"Routing ({data.get('mode', '?')})")
    t.add_column("Task Type", style="bold")
    t.add_column("Model")
    t.add_column("Reason", style="dim")
    for tt, info in data.get("task_type_overrides", {}).items():
        t.add_row(tt, info.get("model", "?"), info.get("reason", ""))
    console.print(t)
    perf = data.get("model_performance", {})
    if not perf:
        return
    pt = Table(title="Model Performance")
    pt.add_column("Model", style="bold")
    pt.add_column("Strengths")
    pt.add_column("Rate", justify="right")
    for model, info in perf.items():
        strengths = ", ".join(info.get("strengths", []))
        pt.add_row(model, strengths, f"{info.get('success_rate', 0):.0%}")
    console.print(pt)


def cmd_models(client) -> None:
    """Model reward heatmap."""
    heatmap = client.models_heatmap()
    if not heatmap:
        console.print("[dim]No model data yet.[/dim]")
        return
    t = Table(title="Model Rewards")
    t.add_column("Model")
    t.add_column("Task Type")
    t.add_column("Blast Tier")
    t.add_column("Reward", justify="right")
    t.add_column("N", justify="right")
    for h in heatmap:
        r = h.get("avg_reward", 0)
        c = "green" if r >= 0.8 else "yellow" if r >= 0.5 else "red"
        t.add_row(
            h.get("model", "?"), h.get("task_type", "?"),
            h.get("blast_tier", "?"),
            f"[{c}]{r:.2f}[/{c}]", str(h.get("samples", 0)),
        )
    console.print(t)


def cmd_use(args: str, state: SessionState) -> None:
    """Set allowed models for this session."""
    if not args or args.strip().lower() == "all":
        state.allowed_models = []
        console.print("[dim]Routing: all models enabled[/dim]")
        return
    models = [m.strip() for m in args.split(",") if m.strip()]
    state.allowed_models = models
    console.print(f"[dim]Routing restricted to: {', '.join(models)}[/dim]")


def cmd_config(client) -> None:
    """Show configuration summary."""
    cfg = client.config()
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(style="bold")
    t.add_column()
    codebases = cfg.get("codebases", [])
    t.add_row("Codebases", str(len(codebases)))
    for cb in codebases[:5]:
        t.add_row(f"  {cb.get('key', '?')}", cb.get("path", ""))
    routing = cfg.get("routing", {})
    t.add_row("Routing mode", routing.get("mode", "dynamic"))
    t.add_row("Daily limit", f"${cfg.get('budget', {}).get('daily_limit_usd', 0):.2f}")
    console.print(Panel(t, title="Config", border_style="blue"))


def cmd_claude_md(state: SessionState) -> None:
    """Show project's CLAUDE.md."""
    wd = Path(state.working_dir)
    for name in ("CLAUDE.md", ".claude/CLAUDE.md"):
        path = wd / name
        if path.exists():
            console.print(Markdown(path.read_text()))
            return
    console.print("[dim]CLAUDE.md not found in project.[/dim]")


def cmd_help() -> None:
    """List all REPL commands."""
    console.print("[bold]Commands:[/bold]")
    for c in (
        "/stats      Budget + model performance",
        "/budget     Detailed budget breakdown",
        "/route      Routing rules and overrides",
        "/models     Model reward heatmap",
        "/use M1,M2  Restrict to specific models",
        "/use all    Remove model restriction",
        "/config     Configuration summary",
        "/claude-md  Show project CLAUDE.md",
        "/blast N    Override blast score (1-10)",
        "/history    Message history",
        "/sessions   List chat sessions",
        "/clear      Clear screen",
        "/quit       Exit",
        "/help       This help",
    ):
        console.print(f"  {c}")

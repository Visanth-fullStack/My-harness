"""Hook dispatch handlers for Mnemos CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from maggy.mnemos.constants import JUST_COMPACTED_MARKER, MNEMOS_DIR


def cmd_hook(args: argparse.Namespace) -> None:
    """Internal hook dispatch — called by bash wrappers."""
    from maggy.mnemos.db import MnemosDB

    stdin = sys.stdin.read()
    data = json.loads(stdin) if stdin.strip() else {}

    cwd = Path(data.get("cwd", "."))
    mnemos_dir = cwd / MNEMOS_DIR
    if not mnemos_dir.is_dir():
        return

    db = MnemosDB(mnemos_dir)
    event = args.event

    handlers = {
        "pre_tool_use": _hook_pre_tool_use,
        "session_start": _hook_session_start,
        "pre_compact": _hook_pre_compact,
        "post_compact": _hook_post_compact,
    }
    handler = handlers.get(event)
    if handler:
        handler(data, mnemos_dir, db)


def _hook_pre_tool_use(
    data: dict, mnemos_dir: Path, db: object,
) -> None:
    from maggy.mnemos.consolidation import run_micro_consolidation
    from maggy.mnemos.fatigue import compute_fatigue, save_fatigue
    from maggy.mnemos.signals import (
        read_signals,
        signal_from_hook_data,
        append_signal,
    )

    # Log the signal
    sig = signal_from_hook_data(data)
    append_signal(mnemos_dir, sig)

    tp = data.get("transcript_path", "")
    if not tp:
        return

    signals = read_signals(mnemos_dir)
    fs = compute_fatigue(Path(tp), signals)
    save_fatigue(mnemos_dir, fs)

    # Micro-consolidation at COMPRESS range
    run_micro_consolidation(db, fs.score)

    if not fs.needs_checkpoint:
        return
    from maggy.mnemos.checkpoint import write_checkpoint

    cp = write_checkpoint(
        mnemos_dir, db, task_id="auto",
        fatigue=fs.score,
    )
    ctx = (
        f"MNEMOS ALERT: Fatigue {fs.score:.2f} "
        f"({fs.state}). Checkpoint {cp.id} written."
    )
    emit_hook_output(ctx)


def _hook_session_start(
    data: dict, mnemos_dir: Path, db: object,
) -> None:
    from maggy.mnemos.checkpoint import format_for_context, load_latest

    cp = load_latest(mnemos_dir)
    if cp is None:
        return
    emit_hook_output(format_for_context(cp))


def _hook_pre_compact(
    data: dict, mnemos_dir: Path, db: object,
) -> None:
    from maggy.mnemos.checkpoint import (
        format_for_context,
        write_checkpoint,
    )
    from maggy.mnemos.rem import run_rem_cycle, should_trigger_rem

    # Trigger REM before compact
    if should_trigger_rem(0.83):
        run_rem_cycle(db, mnemos_dir)

    cp = write_checkpoint(
        mnemos_dir, db, task_id="auto",
        fatigue=0.83, emergency=True, force=True,
    )
    marker = mnemos_dir / JUST_COMPACTED_MARKER
    marker.write_text(cp.id)
    ctx = (
        "MNEMOS PRE-COMPACT: Emergency checkpoint saved. "
        "PRESERVE the following in your summary:\n"
        + format_for_context(cp)
    )
    emit_hook_output(ctx)


def _hook_post_compact(
    data: dict, mnemos_dir: Path, db: object,
) -> None:
    from maggy.mnemos.checkpoint import format_for_context, load_latest

    marker = mnemos_dir / JUST_COMPACTED_MARKER
    if not marker.exists():
        return
    marker.unlink()
    cp = load_latest(mnemos_dir)
    if cp is None:
        return
    ctx = (
        "MNEMOS POST-COMPACT: Restoring checkpoint.\n"
        + format_for_context(cp)
    )
    emit_hook_output(ctx)


def emit_hook_output(context: str) -> None:
    """Output JSON for Claude Code hook system."""
    output = {
        "hookSpecificOutput": {
            "additionalContext": context,
        },
    }
    print(json.dumps(output))

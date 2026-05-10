"""JSONL-backed signal logging for Mnemos."""

from __future__ import annotations

import json
from pathlib import Path


class SignalLog:
    """Append and read Mnemos signal history."""

    def __init__(self, path: Path):
        self._path = path

    def append(self, signal: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(signal) + "\n")

    def recent(self, n: int) -> list[dict]:
        if n <= 0 or not self._path.exists():
            return []
        from collections import deque
        with self._path.open(encoding="utf-8") as handle:
            lines = deque(handle, maxlen=n)
        return [json.loads(line) for line in lines]

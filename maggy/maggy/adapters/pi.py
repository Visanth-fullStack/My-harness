"""Unified adapter for CLI prompts and Pi RPC control."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from typing import AsyncIterator

logger = logging.getLogger(__name__)


@dataclass
class ModelEntry:
    name: str
    provider: str
    model_id: str
    tier: str
    cost_per_1k: float = 0.0
    daily_limit_usd: float = 50.0
    cli_command: str = "claude"
    context_window: int = 200_000


DEFAULT_MODELS: list[ModelEntry] = [
    ModelEntry("kimi", "moonshot", "kimi-k2", "cheap", 0.001, 10.0, "kimi", 128_000),
    ModelEntry("deepseek", "deepseek", "deepseek-v3", "cheap", 0.002, 10.0, "deepseek", 128_000),
    ModelEntry("gpt", "openai", "gpt-4o", "medium", 0.01, 20.0, "codex", 128_000),
    ModelEntry("claude", "anthropic", "claude-sonnet-4", "premium", 0.03, 50.0, "claude", 200_000),
    ModelEntry("codex", "openai", "codex", "validator", 0.02, 30.0, "codex", 200_000),
]

QUOTA_MARKERS = frozenset(
    {"rate limit", "quota", "429", "too many requests", "capacity", "overloaded"}
)

@dataclass
class RunResult:
    model: str
    success: bool
    output: str = ""
    error: str = ""
    cost_usd: float = 0.0
    turns: int = 0
    quota_hit: bool = False


class PiAdapter:
    def __init__(
        self,
        models: list[ModelEntry] | None = None,
        rpc_command: str = "pi",
    ):
        entries = models or DEFAULT_MODELS
        self._models = {entry.name: entry for entry in entries}
        self._fallback_order = [entry.name for entry in sorted(entries, key=lambda m: m.cost_per_1k)]
        self._rpc_command = rpc_command
        self._rpc_process: subprocess.Popen[str] | None = None
        self._streaming = False

    def get_model(self, name: str) -> ModelEntry | None:
        return self._models.get(name)

    def list_models(self) -> list[ModelEntry]:
        return list(self._models.values())

    def fallback_chain(self, start: str) -> list[str]:
        try:
            idx = self._fallback_order.index(start)
        except ValueError:
            return self._fallback_order
        return self._fallback_order[idx + 1 :]

    async def send_prompt(
        self,
        model_name: str,
        prompt: str,
        working_dir: str,
        max_turns: int = 20,
        timeout: int = 600,
    ) -> RunResult:
        model = self._models.get(model_name)
        if not model:
            return RunResult(model=model_name, success=False, error=f"Unknown model: {model_name}")
        try:
            proc = await self._spawn_prompt(model, prompt, max_turns, working_dir)
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return self._prompt_result(model_name, proc.returncode or 0, stdout or b"")
        except asyncio.TimeoutError:
            return RunResult(model=model_name, success=False, error="Timed out")
        except FileNotFoundError:
            return RunResult(
                model=model_name, success=False, error=f"CLI '{model.cli_command}' not found"
            )

    async def send_with_fallback(
        self,
        model_name: str,
        prompt: str,
        working_dir: str,
        max_turns: int = 20,
    ) -> RunResult:
        result = await self.send_prompt(model_name, prompt, working_dir, max_turns)
        if result.success:
            return result
        for fallback in self.fallback_chain(model_name):
            logger.info("Falling back from %s to %s", model_name, fallback)
            result = await self.send_prompt(fallback, prompt, working_dir, max_turns)
            if result.success:
                return result
        return result

    def send_rpc(self, command: dict[str, object]) -> dict[str, object]:
        proc = self._ensure_rpc_process()
        stdin = self._require_stream(proc.stdin, "stdin")
        stdout = self._require_stream(proc.stdout, "stdout")
        if self._streaming:
            raise RuntimeError("Cannot send RPC while streaming")
        stdin.write(f"{json.dumps(command, separators=(',', ':'))}\n")
        stdin.flush()
        line = stdout.readline()
        return json.loads(line or "{}")

    def switch_model(self, provider: str, model: str) -> bool:
        payload = {"command": "set_model", "provider": provider, "model": model}
        return bool(self.send_rpc(payload).get("ok"))

    async def stream_events(self) -> AsyncIterator[dict[str, object]]:
        if self._streaming:
            raise RuntimeError("Already streaming events")
        stdout = self._require_stream(self._ensure_rpc_process().stdout, "stdout")
        self._streaming = True
        try:
            while True:
                line = await asyncio.to_thread(stdout.readline)
                if not line:
                    break
                yield json.loads(line)
        finally:
            self._streaming = False

    def _build_command(self, model: ModelEntry, prompt: str, max_turns: int) -> list[str]:
        cmd = [model.cli_command, "-p", prompt]
        if model.cli_command == "claude":
            cmd += [
                "--output-format",
                "text",
                "--max-turns",
                str(max_turns),
                "--dangerously-skip-permissions",
            ]
        return cmd

    def _detect_quota(self, text: str) -> bool:
        return any(marker in text.lower() for marker in QUOTA_MARKERS)

    def _detect_pi(self) -> bool:
        return shutil.which(self._rpc_command) is not None

    async def _spawn_prompt(
        self,
        model: ModelEntry,
        prompt: str,
        max_turns: int,
        working_dir: str,
    ) -> asyncio.subprocess.Process:
        return await asyncio.create_subprocess_exec(
            *self._build_command(model, prompt, max_turns),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=working_dir,
        )

    def _prompt_result(self, model_name: str, code: int, stdout: bytes) -> RunResult:
        text = stdout.decode("utf-8", errors="replace")
        quota = self._detect_quota(text)
        if code != 0:
            return RunResult(
                model=model_name, success=False, output=text, error=f"Exit code {code}", quota_hit=quota
            )
        return RunResult(model=model_name, success=True, output=text, quota_hit=quota)

    def _ensure_rpc_process(self) -> subprocess.Popen[str]:
        proc = self._rpc_process
        if proc and getattr(proc, "poll", lambda: None)() is None:
            return proc
        self._rpc_process = subprocess.Popen(
            [self._rpc_command], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        return self._rpc_process

    def _require_stream(self, stream: object, name: str):
        if stream is None:
            raise RuntimeError(f"Pi RPC {name} is unavailable")
        return stream

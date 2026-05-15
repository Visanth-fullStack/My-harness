"""Tests for JSONL signal logger."""

from datetime import datetime, timezone

from maggy.mnemos.signals import (
    ToolSignal,
    append_signal,
    count_signals_by_tool,
    extract_file_paths,
    read_signals,
    read_signals_since,
    signal_from_hook_data,
)


def _sig(tool: str = "Read", path: str = "a.py") -> ToolSignal:
    return ToolSignal(
        timestamp=datetime.now(timezone.utc).isoformat(),
        tool_name=tool,
        file_path=path,
    )


class TestAppendAndRead:
    def test_roundtrip(self, tmp_mnemos_dir):
        s = _sig()
        append_signal(tmp_mnemos_dir, s)
        result = read_signals(tmp_mnemos_dir)
        assert len(result) == 1
        assert result[0].tool_name == "Read"

    def test_read_empty(self, tmp_mnemos_dir):
        assert read_signals(tmp_mnemos_dir) == []

    def test_multiple_signals(self, tmp_mnemos_dir):
        for i in range(5):
            append_signal(tmp_mnemos_dir, _sig(path=f"f{i}.py"))
        assert len(read_signals(tmp_mnemos_dir)) == 5


class TestReadSince:
    def test_filters_old(self, tmp_mnemos_dir):
        s = _sig()
        append_signal(tmp_mnemos_dir, s)
        future = datetime(2099, 1, 1, tzinfo=timezone.utc)
        assert read_signals_since(tmp_mnemos_dir, future) == []


class TestAggregations:
    def test_count_by_tool(self):
        signals = [_sig("Read"), _sig("Read"), _sig("Write")]
        counts = count_signals_by_tool(signals)
        assert counts["Read"] == 2
        assert counts["Write"] == 1

    def test_extract_paths(self):
        signals = [_sig(path="a.py"), _sig(path="a.py"), _sig(path="b.py")]
        paths = extract_file_paths(signals)
        assert paths == ["a.py", "b.py"]


class TestFromHookData:
    def test_parses_hook_data(self):
        data = {"tool_name": "Edit", "file_path": "x.py"}
        sig = signal_from_hook_data(data)
        assert sig.tool_name == "Edit"
        assert sig.file_path == "x.py"

    def test_defaults(self):
        sig = signal_from_hook_data({})
        assert sig.tool_name == "unknown"

"""Tests for execution strategy selection."""

from __future__ import annotations

from maggy.services.executor_helpers import select_strategy


class TestSelectStrategy:
    def test_high_blast_returns_parallel(self):
        assert select_strategy(blast=7, file_count=2) == "parallel"
        assert select_strategy(blast=10, file_count=1) == "parallel"

    def test_many_files_returns_parallel(self):
        assert select_strategy(blast=3, file_count=5) == "parallel"
        assert select_strategy(blast=2, file_count=8) == "parallel"

    def test_user_override_returns_parallel(self):
        assert select_strategy(blast=1, file_count=1, user_requested=True) == "parallel"

    def test_default_returns_sequential(self):
        assert select_strategy(blast=3, file_count=2) == "sequential"
        assert select_strategy(blast=6, file_count=4) == "sequential"

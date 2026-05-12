"""Tests for blast-score estimation and task-type detection."""

from __future__ import annotations

from maggy.services.chat_router import (
    DEFAULT_BLAST,
    estimate_blast,
    estimate_type,
)


def test_blast_hi_scores_low():
    """Trivial greeting should score 1, not 5."""
    assert estimate_blast("hi") == 1


def test_blast_exit_scores_low():
    """Exit-like messages should score 1."""
    assert estimate_blast("exit") == 1


def test_blast_empty_returns_default():
    """Empty string uses DEFAULT_BLAST."""
    assert estimate_blast("") == DEFAULT_BLAST


def test_blast_security_audit_scores_high():
    """Multiple high-tier keywords → blast >= 7."""
    score = estimate_blast("security audit migration")
    assert score >= 7


def test_blast_fix_typo_scores_low():
    """Low-tier keywords → blast <= 3."""
    score = estimate_blast("fix typo in readme")
    assert score <= 3


def test_type_security_detected():
    """Security keywords map to security type."""
    assert estimate_type("fix auth vulnerability") == "security"


def test_type_general_default():
    """No keyword matches → general."""
    assert estimate_type("hello world") == "general"


def test_type_search_detected():
    """Search queries map to search type."""
    assert estimate_type("find the utils module") == "search"


def test_type_search_grep():
    """grep-like queries map to search type."""
    assert estimate_type("grep for config files") == "search"


def test_blast_search_scores_low():
    """Search queries should score low blast (cheap model)."""
    score = estimate_blast("find the utils module")
    assert score <= 3

"""Tests for InteractionLogger and calculate_style_metrics — Phase 4 Cycle 4.5."""

import pytest

from backend.memory.recent.connection import SQLiteConnectionManager
from backend.memory.recent.schema import SchemaManager
from backend.memory.recent.interaction_logger import (
    InteractionLogger,
    calculate_style_metrics,
)


@pytest.fixture
def conn_mgr(tmp_path):
    mgr = SQLiteConnectionManager(db_path=tmp_path / "test.db")
    SchemaManager(mgr).initialize()
    yield mgr
    mgr.close()


@pytest.fixture
def logger(conn_mgr):
    return InteractionLogger(conn_mgr)


# ── InteractionLogger ───────────────────────────────────────────────────────


class TestInteractionLogger:
    def test_log_interaction_returns_true(self, logger):
        result = logger.log_interaction(
            routing_decision={
                "effective_model": "gemini-pro",
                "tier": "high",
                "router_reason": "complexity",
            },
            latency_ms=150,
            tokens_in=100,
            tokens_out=50,
        )
        assert result is True

    def test_style_metrics_calculated(self, logger, conn_mgr):
        logger.log_interaction(
            routing_decision={
                "effective_model": "gemini-pro",
                "tier": "high",
                "router_reason": "test",
            },
            response_text="I think this is good. Maybe we should try.",
        )
        with conn_mgr.get_connection() as conn:
            row = conn.execute(
                "SELECT hedge_ratio, avg_sentence_len FROM interaction_logs LIMIT 1"
            ).fetchone()
            assert row[0] is not None  # hedge_ratio recorded
            assert row[0] > 0  # both sentences have hedges


# ── calculate_style_metrics (pure function) ─────────────────────────────────


class TestCalculateStyleMetrics:
    def test_empty_response(self):
        result = calculate_style_metrics("")
        assert result == {"hedge_ratio": 0.0, "avg_sentence_len": 0.0}

    def test_hedge_detection_korean(self):
        result = calculate_style_metrics("아마도 그럴 것 같습니다. 확실한 사실입니다.")
        assert result["hedge_ratio"] > 0

    def test_hedge_detection_english(self):
        result = calculate_style_metrics(
            "I think this works. This is correct. Maybe not."
        )
        assert result["hedge_ratio"] > 0
        # 3 sentences, 2 with hedges
        assert abs(result["hedge_ratio"] - 0.667) < 0.01

    def test_no_hedges(self):
        result = calculate_style_metrics(
            "This is a fact. Another fact here. Clear statement."
        )
        assert result["hedge_ratio"] == 0.0
        assert result["avg_sentence_len"] > 0

    def test_short_response(self):
        result = calculate_style_metrics("Hi")
        assert result == {"hedge_ratio": 0.0, "avg_sentence_len": 0.0}

"""Interaction logging and response style analysis."""

import json
import re
import sqlite3
from typing import Optional, Dict, List

from backend.core.logging import get_logger
from backend.memory.recent.connection import SQLiteConnectionManager

_log = get_logger("memory.recent.interaction")

# Hedge phrases for style metric calculation
_HEDGE_PHRASES = [
    "아마도",
    "것 같아",
    "것 같습니다",
    "인 것 같아",
    "i think",
    "i'm not sure",
    "maybe",
    "perhaps",
    "probably",
    "확실하지 않지만",
    "추측이지만",
]


def calculate_style_metrics(response: str) -> dict:
    """Calculate hedge ratio and average sentence length.

    Pure function — no side effects or I/O.

    Args:
        response: The full response text.

    Returns:
        Dict with hedge_ratio (float) and avg_sentence_len (float).
    """
    if not response or len(response) < 10:
        return {"hedge_ratio": 0.0, "avg_sentence_len": 0.0}

    sentences = re.split(r"[.!?。]", response)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return {"hedge_ratio": 0.0, "avg_sentence_len": 0.0}

    # PERF-041: Pre-compile hedge pattern for efficiency (now done at module level)
    # This optimization is minor given _HEDGE_PHRASES check is already efficient
    hedge_count = sum(
        1
        for sentence in sentences
        if any(hedge in sentence.lower() for hedge in _HEDGE_PHRASES)
    )

    return {
        "hedge_ratio": round(hedge_count / len(sentences), 3),
        "avg_sentence_len": round(len(response) / len(sentences), 1),
    }


class InteractionLogger:
    """Records model routing decisions and response metrics.

    Args:
        conn_mgr: SQLiteConnectionManager instance.
    """

    def __init__(self, conn_mgr: SQLiteConnectionManager):
        self._conn_mgr = conn_mgr

    def log_interaction(
        self,
        routing_decision: dict,
        conversation_id: Optional[str] = None,
        turn_id: Optional[int] = None,
        latency_ms: Optional[int] = None,
        ttft_ms: Optional[int] = None,
        tokens_in: Optional[int] = None,
        tokens_out: Optional[int] = None,
        tool_calls: Optional[list] = None,
        refusal_detected: bool = False,
        response_text: Optional[str] = None,
    ) -> bool:
        """Record a single interaction log entry."""
        try:
            style_metrics = {}
            if response_text:
                style_metrics = calculate_style_metrics(response_text)

            with self._conn_mgr.get_connection() as conn:
                conn.execute(
                    """INSERT INTO interaction_logs (
                           conversation_id, turn_id,
                           effective_model, tier, router_reason,
                           routing_features_json, manual_override,
                           latency_ms, ttft_ms, tokens_in, tokens_out,
                           tool_calls_json, refusal_detected,
                           response_chars, hedge_ratio, avg_sentence_len
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        conversation_id,
                        turn_id,
                        routing_decision.get("effective_model", "unknown"),
                        routing_decision.get("tier", "unknown"),
                        routing_decision.get("router_reason", "unknown"),
                        json.dumps(
                            routing_decision.get("routing_features", {}),
                            ensure_ascii=False,
                        ),
                        1 if routing_decision.get("manual_override", False) else 0,
                        latency_ms,
                        ttft_ms,
                        tokens_in,
                        tokens_out,
                        json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
                        1 if refusal_detected else 0,
                        len(response_text) if response_text else None,
                        style_metrics.get("hedge_ratio"),
                        style_metrics.get("avg_sentence_len"),
                    ),
                )
                conn.commit()

                _log.debug(
                    "Interaction logged",
                    tier=routing_decision.get("tier"),
                    router_reason=routing_decision.get("router_reason"),
                    latency_ms=latency_ms,
                )
                return True
        except Exception as e:
            _log.error("Log interaction failed", error=str(e))
            return False

    def get_recent_logs(self, limit: int = 20) -> List[Dict]:
        """Retrieve the most recent interaction logs."""
        try:
            with self._conn_mgr.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM interaction_logs ORDER BY ts DESC LIMIT ?",
                    (limit,),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            _log.error("Get interaction logs failed", error=str(e))
            return []

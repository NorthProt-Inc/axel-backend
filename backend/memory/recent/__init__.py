"""Session archive package — Facade over connection, schema, repository, and logger."""

from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import SQLITE_MEMORY_PATH
from backend.core.logging import get_logger

from backend.memory.recent.connection import SQLiteConnectionManager
from backend.memory.recent.interaction_logger import InteractionLogger, calculate_style_metrics as calculate_style_metrics
from backend.memory.recent.repository import SessionRepository
from backend.memory.recent.schema import SchemaManager
from backend.memory.recent.summarizer import SessionSummarizer

_log = get_logger("memory.recent")


class SessionArchive:
    """Facade that delegates to internal components.

    Preserves the original public API so all external callers
    (``backend.api.memory``, ``backend.memory.unified``, etc.)
    continue to work without changes.

    Args:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: str = None):
        self.db_path = Path(db_path) if db_path else SQLITE_MEMORY_PATH
        self._conn_mgr = SQLiteConnectionManager(self.db_path)
        SchemaManager(self._conn_mgr).initialize()
        self._repo = SessionRepository(self._conn_mgr)
        self._logger = InteractionLogger(self._conn_mgr)
        self._summarizer = SessionSummarizer(self._repo)

    # ── Backward-compat helper ───────────────────────────────────────────

    @contextmanager
    def _get_connection(self):
        with self._conn_mgr.get_connection() as conn:
            yield conn

    # ── Message operations ───────────────────────────────────────────────

    def save_message_immediate(
        self,
        session_id: str,
        role: str,
        content: str,
        timestamp: str,
        emotional_context: str = "neutral",
    ) -> bool:
        return self._repo.save_message_immediate(
            session_id, role, content, timestamp, emotional_context
        )

    def save_session(
        self,
        session_id: str,
        summary: str,
        key_topics: List[str],
        emotional_tone: str,
        turn_count: int,
        started_at: datetime,
        ended_at: datetime,
        messages: List[Dict] = None,
    ) -> bool:
        return self._repo.save_session(
            session_id, summary, key_topics, emotional_tone,
            turn_count, started_at, ended_at, messages,
        )

    def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        return self._repo.get_session_messages(session_id)

    def get_session_detail(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._repo.get_session_detail(session_id)

    def search_by_topic(self, topic: str, limit: int = 5) -> List[Dict]:
        return self._repo.search_by_topic(topic, limit)

    def get_sessions_by_date(
        self,
        from_date: str,
        to_date: str = None,
        limit: int = 10,
        max_tokens: int = 3000,
    ) -> str:
        return self._repo.get_sessions_by_date(from_date, to_date, limit, max_tokens)

    def get_recent_summaries(self, limit: int = 5, max_tokens: int = 2000) -> str:
        return self._repo.get_recent_summaries(limit, max_tokens)

    def get_time_since_last_session(self) -> Optional[timedelta]:
        return self._repo.get_time_since_last_session()

    def get_stats(self) -> Dict[str, Any]:
        return self._repo.get_stats()

    def get_interaction_stats(self) -> Dict[str, Any]:
        return self._repo.get_interaction_stats()

    # ── Interaction logging ──────────────────────────────────────────────

    def log_interaction(
        self,
        routing_decision: dict,
        conversation_id: str = None,
        turn_id: int = None,
        latency_ms: int = None,
        ttft_ms: int = None,
        tokens_in: int = None,
        tokens_out: int = None,
        tool_calls: list = None,
        refusal_detected: bool = False,
        response_text: str = None,
    ) -> bool:
        return self._logger.log_interaction(
            routing_decision, conversation_id, turn_id,
            latency_ms, ttft_ms, tokens_in, tokens_out,
            tool_calls, refusal_detected, response_text,
        )

    def get_recent_interaction_logs(self, limit: int = 20) -> List[Dict]:
        return self._logger.get_recent_logs(limit)

    # ── Summarization ────────────────────────────────────────────────────

    async def summarize_expired(self, llm_client=None) -> Dict[str, int]:
        return await self._summarizer.summarize_expired(llm_client)

    # ── Lifecycle ────────────────────────────────────────────────────────

    def cleanup_expired(self) -> int:
        _log.debug("cleanup_expired called but disabled (use summarize_expired)")
        return 0

    def close(self, silent: bool = False):
        self._conn_mgr.close()
        if not silent:
            try:
                _log.info("Database connection closed")
            except Exception:
                pass

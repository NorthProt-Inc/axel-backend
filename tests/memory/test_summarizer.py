"""Tests for SessionSummarizer — Phase 5 TDD cycles."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from backend.memory.recent.connection import SQLiteConnectionManager
from backend.memory.recent.schema import SchemaManager
from backend.memory.recent.repository import SessionRepository
from backend.memory.recent.summarizer import SessionSummarizer

VANCOUVER_TZ = ZoneInfo("America/Vancouver")


@pytest.fixture
def conn_mgr(tmp_path):
    mgr = SQLiteConnectionManager(db_path=tmp_path / "test.db")
    SchemaManager(mgr).initialize()
    yield mgr
    mgr.close()


@pytest.fixture
def repo(conn_mgr):
    return SessionRepository(conn_mgr)


@pytest.fixture
def summarizer(repo):
    return SessionSummarizer(repo)


@pytest.fixture
def mock_llm():
    client = AsyncMock()
    client.generate = AsyncMock(return_value="테스트 요약입니다.")
    return client


# ── Cycle 5.1: generate_summary ─────────────────────────────────────────────


class TestGenerateSummary:
    @pytest.mark.asyncio
    async def test_generates_summary_from_messages(self, summarizer, mock_llm):
        messages = [
            {"role": "user", "content": "Python에 대해 알려줘"},
            {"role": "assistant", "content": "Python은 범용 프로그래밍 언어입니다."},
        ]
        result = await summarizer.generate_summary(messages, llm_client=mock_llm)
        assert result == "테스트 요약입니다."
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_for_empty(self, summarizer, mock_llm):
        result = await summarizer.generate_summary([], llm_client=mock_llm)
        assert result is None
        mock_llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_on_llm_failure(self, summarizer):
        client = AsyncMock()
        client.generate = AsyncMock(side_effect=RuntimeError("API error"))
        messages = [{"role": "user", "content": "test"}]
        result = await summarizer.generate_summary(messages, llm_client=client)
        assert result is None


# ── Cycle 5.2: summarize_expired integration ────────────────────────────────


class TestSummarizeExpired:
    def _seed_expired_session(self, repo):
        """Create an expired session with messages."""
        now = datetime.now(VANCOUVER_TZ)
        past = now - timedelta(days=10)
        expired = past - timedelta(days=1)

        repo.save_session(
            session_id="sess-expired",
            summary="",
            key_topics=["test"],
            emotional_tone="neutral",
            turn_count=2,
            started_at=past,
            ended_at=past,
            messages=[
                {"role": "user", "content": "Hello", "timestamp": past.isoformat()},
                {"role": "assistant", "content": "Hi!", "timestamp": past.isoformat()},
            ],
        )
        # Force expires_at to the past
        with repo._conn_mgr.get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET expires_at = ?, summary = NULL WHERE session_id = ?",
                (expired.isoformat(), "sess-expired"),
            )
            conn.commit()

    @pytest.mark.asyncio
    async def test_processes_expired_sessions(self, summarizer, repo, mock_llm):
        self._seed_expired_session(repo)

        result = await summarizer.summarize_expired(llm_client=mock_llm)
        assert result["sessions_processed"] == 1
        assert result["messages_archived"] == 2

        # Verify messages moved to archive
        with repo._conn_mgr.get_connection() as conn:
            archived = conn.execute(
                "SELECT COUNT(*) FROM archived_messages WHERE session_id = 'sess-expired'"
            ).fetchone()[0]
            assert archived == 2

            remaining = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id = 'sess-expired'"
            ).fetchone()[0]
            assert remaining == 0

    @pytest.mark.asyncio
    async def test_no_expired_sessions_returns_zero(self, summarizer, mock_llm):
        result = await summarizer.summarize_expired(llm_client=mock_llm)
        assert result["sessions_processed"] == 0
        assert result["messages_archived"] == 0

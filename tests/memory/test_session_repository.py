"""Tests for SessionRepository — Phase 4 Cycles 4.2-4.4."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from backend.memory.recent.connection import SQLiteConnectionManager
from backend.memory.recent.schema import SchemaManager
from backend.memory.recent.repository import SessionRepository

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


# ── Cycle 4.2: save_message_immediate ────────────────────────────────────────


class TestSaveMessageImmediate:
    def test_saves_message(self, repo, conn_mgr):
        result = repo.save_message_immediate(
            "sess-001", "user", "Hello", datetime.now(VANCOUVER_TZ).isoformat()
        )
        assert result is True

        with conn_mgr.get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            assert count == 1

    def test_turn_id_auto_increments(self, repo):
        ts = datetime.now(VANCOUVER_TZ).isoformat()
        repo.save_message_immediate("sess-001", "user", "msg1", ts)
        repo.save_message_immediate("sess-001", "assistant", "msg2", ts)

        msgs = repo.get_session_messages("sess-001")
        assert [m["turn_id"] for m in msgs] == [0, 1]

    def test_returns_false_on_error(self, conn_mgr):
        # Use a repo with uninitialized DB (no tables)
        bare_mgr = SQLiteConnectionManager(db_path=conn_mgr.db_path.parent / "bare.db")
        repo = SessionRepository(bare_mgr)
        result = repo.save_message_immediate("x", "user", "hello", "2025-01-01")
        assert result is False
        bare_mgr.close()


# ── Cycle 4.3: save_session ──────────────────────────────────────────────────


class TestSaveSession:
    def test_saves_session_and_messages_atomically(self, repo, conn_mgr):
        now = datetime.now(VANCOUVER_TZ)
        messages = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        result = repo.save_session(
            session_id="sess-atom",
            summary="",
            key_topics=["greeting"],
            emotional_tone="positive",
            turn_count=2,
            started_at=now,
            ended_at=now,
            messages=messages,
        )
        assert result is True

        with conn_mgr.get_connection() as conn:
            session = conn.execute(
                "SELECT * FROM sessions WHERE session_id = 'sess-atom'"
            ).fetchone()
            assert session is not None

            msg_count = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id = 'sess-atom'"
            ).fetchone()[0]
            assert msg_count == 2


# ── Cycle 4.4: Query methods ────────────────────────────────────────────────


class TestQueryMethods:
    def _seed(self, repo):
        now = datetime.now(VANCOUVER_TZ)
        repo.save_session(
            session_id="sess-q1",
            summary="",
            key_topics=["python"],
            emotional_tone="neutral",
            turn_count=2,
            started_at=now - timedelta(hours=1),
            ended_at=now,
            messages=[
                {"role": "user", "content": "Tell me about Python"},
                {"role": "assistant", "content": "Python is great!"},
            ],
        )

    def test_get_sessions_by_date(self, repo):
        self._seed(repo)
        today = datetime.now(VANCOUVER_TZ).strftime("%Y-%m-%d")
        result = repo.get_sessions_by_date(today)
        assert "Python" in result or "python" in result.lower()

    def test_get_stats(self, repo):
        self._seed(repo)
        stats = repo.get_stats()
        assert stats["total_sessions"] >= 1
        assert stats["total_messages"] >= 2

    def test_get_time_since_last_session(self, repo):
        self._seed(repo)
        delta = repo.get_time_since_last_session()
        assert delta is not None
        assert delta.total_seconds() >= 0

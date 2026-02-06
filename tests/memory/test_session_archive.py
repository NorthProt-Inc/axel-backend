"""Tests for SessionArchive — integration and backward compatibility."""

import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from backend.memory.recent import SessionArchive
from backend.memory.recent.connection import SQLiteConnectionManager

VANCOUVER_TZ = ZoneInfo("America/Vancouver")


@pytest.fixture
def archive(tmp_path):
    a = SessionArchive(db_path=str(tmp_path / "test.db"))
    yield a
    a.close()


def _seed_messages(archive: SessionArchive, session_id: str, count: int = 3):
    """Insert test messages directly into the DB."""
    now = datetime.now(VANCOUVER_TZ)
    with archive._get_connection() as conn:
        for i in range(count):
            conn.execute(
                """INSERT INTO messages
                   (session_id, turn_id, role, content, timestamp, emotional_context)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    i,
                    "user" if i % 2 == 0 else "assistant",
                    f"message {i}",
                    (now + timedelta(seconds=i)).isoformat(),
                    "neutral",
                ),
            )
        conn.commit()


def _seed_interaction_logs(archive: SessionArchive, count: int = 5):
    """Insert test interaction logs."""
    with archive._get_connection() as conn:
        for i in range(count):
            conn.execute(
                """INSERT INTO interaction_logs
                   (effective_model, tier, router_reason, latency_ms,
                    tokens_in, tokens_out, refusal_detected)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    "gemini-pro" if i % 2 == 0 else "gemini-flash",
                    "high" if i % 2 == 0 else "low",
                    "complexity" if i % 3 == 0 else "default",
                    100 + i * 10,
                    50 + i,
                    30 + i,
                    0,
                ),
            )
        conn.commit()


# ── Cycle 1.6: SessionArchive delegates to ConnectionManager ────────────────


class TestSessionArchiveConnectionDelegate:
    def test_session_archive_creates_connection_manager(self, tmp_path):
        a = SessionArchive(db_path=str(tmp_path / "test.db"))
        assert isinstance(a._conn_mgr, SQLiteConnectionManager)
        a.close()

    def test_backward_compat_get_connection_still_works(self, tmp_path):
        a = SessionArchive(db_path=str(tmp_path / "test.db"))
        with a._get_connection() as conn:
            assert isinstance(conn, sqlite3.Connection)
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'"
            )
            assert cursor.fetchone() is not None
        a.close()

    def test_import_backward_compat(self):
        from backend.memory.recent import SessionArchive as SA
        assert SA is SessionArchive


# ── Cycle 2.1: get_session_messages ─────────────────────────────────────────


class TestGetSessionMessages:
    def test_returns_messages_for_existing_session(self, archive):
        _seed_messages(archive, "sess-001", count=3)
        msgs = archive.get_session_messages("sess-001")
        assert len(msgs) == 3
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "message 0"

    def test_returns_empty_for_unknown(self, archive):
        msgs = archive.get_session_messages("nonexistent")
        assert msgs == []

    def test_messages_ordered_by_turn_id(self, archive):
        _seed_messages(archive, "sess-002", count=5)
        msgs = archive.get_session_messages("sess-002")
        turn_ids = [m["turn_id"] for m in msgs]
        assert turn_ids == sorted(turn_ids)


# ── Cycle 2.2: get_interaction_stats ────────────────────────────────────────


class TestGetInteractionStats:
    def test_returns_stats_dict_structure(self, archive):
        _seed_interaction_logs(archive, count=5)
        stats = archive.get_interaction_stats()
        assert "by_model" in stats
        assert "by_tier" in stats
        assert "by_router_reason" in stats
        assert "last_24h" in stats

    def test_returns_correct_model_stats(self, archive):
        _seed_interaction_logs(archive, count=5)
        stats = archive.get_interaction_stats()
        models = {row["effective_model"] for row in stats["by_model"]}
        assert "gemini-pro" in models
        assert "gemini-flash" in models

    def test_empty_database_returns_empty_stats(self, archive):
        stats = archive.get_interaction_stats()
        assert stats["by_model"] == []
        assert stats["by_tier"] == []
        assert stats["last_24h"]["total_calls"] == 0


# ── Cycle 2.3: get_session_detail messages fallback ────────────────────────


class TestGetSessionDetailFallback:
    def test_returns_messages_from_messages_table(self, archive):
        """When messages_json is empty, get_session_detail should fall back."""
        # Insert a session with no messages_json
        with archive._get_connection() as conn:
            conn.execute(
                """INSERT INTO sessions
                   (session_id, key_topics, emotional_tone, turn_count,
                    started_at, ended_at, expires_at, messages_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, NULL)""",
                (
                    "sess-fallback",
                    '["test"]',
                    "neutral",
                    3,
                    datetime.now(VANCOUVER_TZ).isoformat(),
                    datetime.now(VANCOUVER_TZ).isoformat(),
                    (datetime.now(VANCOUVER_TZ) + timedelta(days=7)).isoformat(),
                ),
            )
            conn.commit()
        _seed_messages(archive, "sess-fallback", count=3)

        detail = archive.get_session_detail("sess-fallback")
        assert detail is not None
        assert len(detail["messages"]) == 3


# ── Cycle 4.6: All public methods still work ────────────────────────────────


class TestFacadePublicAPI:
    def test_all_public_methods_still_work(self, archive):
        """Verify all public methods are callable on the Facade."""
        expected_methods = [
            "save_message_immediate",
            "save_session",
            "get_session_messages",
            "get_session_detail",
            "search_by_topic",
            "get_sessions_by_date",
            "get_recent_summaries",
            "get_time_since_last_session",
            "get_stats",
            "get_interaction_stats",
            "log_interaction",
            "get_recent_interaction_logs",
            "summarize_expired",
            "cleanup_expired",
            "close",
        ]
        for method_name in expected_methods:
            assert callable(getattr(archive, method_name)), f"{method_name} not callable"

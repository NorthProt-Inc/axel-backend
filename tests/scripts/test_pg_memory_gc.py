"""Tests for scripts/pg_memory_gc.py — all phases mock DB connections."""

from unittest.mock import MagicMock, patch, call
import pytest

# Patch psycopg2 before importing the module
_mock_psycopg2 = MagicMock()
_mock_psycopg2.connect.return_value = MagicMock()


@pytest.fixture(autouse=True)
def _patch_env(monkeypatch):
    """Ensure DATABASE_URL is always set for tests."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")


@pytest.fixture
def mock_conn():
    """Return a mock psycopg2 connection with cursor context manager."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


# ── Unit tests for utilities ─────────────────────────────────────────────────


class TestRemoveEmoji:
    def test_strips_emoji(self):
        from scripts.pg_memory_gc import remove_emoji

        assert remove_emoji("hello 😀 world 🎉") == "hello  world "

    def test_preserves_plain_text(self):
        from scripts.pg_memory_gc import remove_emoji

        assert remove_emoji("no emoji here") == "no emoji here"

    def test_empty_string(self):
        from scripts.pg_memory_gc import remove_emoji

        assert remove_emoji("") == ""

    def test_korean_with_emoji(self):
        from scripts.pg_memory_gc import remove_emoji

        result = remove_emoji("안녕하세요 👋 반갑습니다")
        assert "안녕하세요" in result
        assert "반갑습니다" in result
        assert "👋" not in result


class TestContentHash:
    def test_same_content_same_hash(self):
        from scripts.pg_memory_gc import _content_hash

        assert _content_hash("hello world") == _content_hash("hello world")

    def test_case_insensitive(self):
        from scripts.pg_memory_gc import _content_hash

        assert _content_hash("Hello World") == _content_hash("hello world")

    def test_strips_whitespace(self):
        from scripts.pg_memory_gc import _content_hash

        assert _content_hash("  hello  ") == _content_hash("hello")

    def test_different_content_different_hash(self):
        from scripts.pg_memory_gc import _content_hash

        assert _content_hash("hello") != _content_hash("world")


# ── Phase 1: Emoji strip ────────────────────────────────────────────────────


class TestPhase1EmojiStrip:
    def test_updates_messages_with_emoji(self, mock_conn):
        from scripts.pg_memory_gc import phase1_emoji_strip

        conn, cursor = mock_conn
        # First call: messages with emoji, Second: memories with emoji
        cursor.fetchall.side_effect = [
            [(1, "hello 😀 world")],  # messages
            [],  # memories
        ]

        result = phase1_emoji_strip(conn, dry_run=False)

        assert result["messages_updated"] == 1
        assert result["memories_updated"] == 0
        conn.commit.assert_called_once()

    def test_updates_memories_with_emoji(self, mock_conn):
        from scripts.pg_memory_gc import phase1_emoji_strip

        conn, cursor = mock_conn
        cursor.fetchall.side_effect = [
            [],  # messages
            [("uuid-1", "memory 🎉 data")],  # memories
        ]

        result = phase1_emoji_strip(conn, dry_run=False)

        assert result["messages_updated"] == 0
        assert result["memories_updated"] == 1

    def test_dry_run_no_commit(self, mock_conn):
        from scripts.pg_memory_gc import phase1_emoji_strip

        conn, cursor = mock_conn
        cursor.fetchall.side_effect = [
            [(1, "hello 😀")],
            [(2, "memory 🎉")],
        ]

        result = phase1_emoji_strip(conn, dry_run=True)

        assert result["messages_updated"] == 1
        assert result["memories_updated"] == 1
        conn.commit.assert_not_called()

    def test_no_emoji_no_updates(self, mock_conn):
        from scripts.pg_memory_gc import phase1_emoji_strip

        conn, cursor = mock_conn
        cursor.fetchall.side_effect = [[], []]

        result = phase1_emoji_strip(conn, dry_run=False)

        assert result["messages_updated"] == 0
        assert result["memories_updated"] == 0


# ── Phase 2: LLM summarize ──────────────────────────────────────────────────


class TestPhase2LLMSummarize:
    def test_no_long_messages(self, mock_conn):
        from scripts.pg_memory_gc import phase2_llm_summarize

        conn, cursor = mock_conn
        cursor.fetchall.return_value = []

        result = phase2_llm_summarize(conn, dry_run=False)

        assert result["candidates"] == 0

    def test_dry_run_reports_candidates(self, mock_conn):
        from scripts.pg_memory_gc import phase2_llm_summarize

        conn, cursor = mock_conn
        cursor.fetchall.return_value = [(1, "x" * 3000), (2, "y" * 2500)]

        result = phase2_llm_summarize(conn, dry_run=True)

        assert result["candidates"] == 2
        assert result["updated"] == 0

    @patch("scripts.pg_memory_gc.KeyRotator")
    def test_summarize_with_rotator(self, MockRotator, mock_conn):
        from scripts.pg_memory_gc import phase2_llm_summarize

        conn, cursor = mock_conn
        cursor.fetchall.return_value = [(1, "x" * 3000)]

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "summarized content"
        mock_client.models.generate_content.return_value = mock_response

        rotator_instance = MagicMock()
        rotator_instance.get_client.return_value = mock_client
        rotator_instance.get_stats.return_value = {"key_0": 1}
        MockRotator.return_value = rotator_instance

        result = phase2_llm_summarize(conn, dry_run=False)

        assert result["candidates"] == 1
        assert result["updated"] == 1


# ── Phase 3: Hash dedup ─────────────────────────────────────────────────────


class TestPhase3HashDedup:
    def test_no_duplicates(self, mock_conn):
        from scripts.pg_memory_gc import phase3_hash_dedup

        conn, cursor = mock_conn
        cursor.fetchall.return_value = [
            ("uuid-1", "unique content A", 0.8),
            ("uuid-2", "unique content B", 0.7),
        ]

        result = phase3_hash_dedup(conn, dry_run=False)

        assert result["duplicates"] == 0

    def test_deletes_lower_importance_duplicate(self, mock_conn):
        from scripts.pg_memory_gc import phase3_hash_dedup

        conn, cursor = mock_conn
        cursor.fetchall.return_value = [
            ("uuid-1", "same content here", 0.9),
            ("uuid-2", "same content here", 0.3),
        ]

        result = phase3_hash_dedup(conn, dry_run=False)

        assert result["duplicates"] == 1
        conn.commit.assert_called()

        # Verify the correct UUID was deleted (lower importance)
        delete_call = cursor.execute.call_args_list[-1]
        assert "uuid-2" in delete_call[0][1][0]

    def test_dry_run_no_delete(self, mock_conn):
        from scripts.pg_memory_gc import phase3_hash_dedup

        conn, cursor = mock_conn
        cursor.fetchall.return_value = [
            ("uuid-1", "same content", 0.9),
            ("uuid-2", "same content", 0.3),
        ]

        result = phase3_hash_dedup(conn, dry_run=True)

        assert result["duplicates"] == 1
        conn.commit.assert_not_called()


# ── Phase 4: Decay cleanup ──────────────────────────────────────────────────


class TestPhase4DecayCleanup:
    def test_no_candidates(self, mock_conn):
        from scripts.pg_memory_gc import phase4_decay_cleanup

        conn, cursor = mock_conn
        cursor.fetchone.return_value = (0,)

        result = phase4_decay_cleanup(conn, dry_run=False)

        assert result["deleted"] == 0

    def test_deletes_decayed_memories(self, mock_conn):
        from scripts.pg_memory_gc import phase4_decay_cleanup

        conn, cursor = mock_conn
        cursor.fetchone.return_value = (5,)
        cursor.fetchall.return_value = [("uuid-1",), ("uuid-2",), ("uuid-3",), ("uuid-4",), ("uuid-5",)]

        result = phase4_decay_cleanup(conn, dry_run=False)

        assert result["deleted"] == 5
        conn.commit.assert_called()

    def test_dry_run_reports_count(self, mock_conn):
        from scripts.pg_memory_gc import phase4_decay_cleanup

        conn, cursor = mock_conn
        cursor.fetchone.return_value = (3,)

        result = phase4_decay_cleanup(conn, dry_run=True)

        assert result["deleted"] == 3
        conn.commit.assert_not_called()


# ── Phase 5: Archive cleanup ────────────────────────────────────────────────


class TestPhase5ArchiveCleanup:
    def test_no_old_archives(self, mock_conn):
        from scripts.pg_memory_gc import phase5_archive_cleanup

        conn, cursor = mock_conn
        cursor.fetchone.return_value = (0,)

        result = phase5_archive_cleanup(conn, dry_run=False)

        assert result["deleted"] == 0

    def test_deletes_old_archives(self, mock_conn):
        from scripts.pg_memory_gc import phase5_archive_cleanup

        conn, cursor = mock_conn
        cursor.fetchone.return_value = (10,)
        cursor.fetchall.return_value = [(i,) for i in range(10)]

        result = phase5_archive_cleanup(conn, dry_run=False)

        assert result["deleted"] == 10
        conn.commit.assert_called()


# ── Phase 6: Meta cleanup ───────────────────────────────────────────────────


class TestPhase6MetaCleanup:
    def test_no_old_patterns(self, mock_conn):
        from scripts.pg_memory_gc import phase6_meta_cleanup

        conn, cursor = mock_conn
        cursor.fetchone.return_value = (0,)

        result = phase6_meta_cleanup(conn, dry_run=False)

        assert result["deleted"] == 0

    def test_deletes_old_patterns(self, mock_conn):
        from scripts.pg_memory_gc import phase6_meta_cleanup

        conn, cursor = mock_conn
        cursor.fetchone.return_value = (7,)
        cursor.fetchall.return_value = [(i,) for i in range(7)]

        result = phase6_meta_cleanup(conn, dry_run=False)

        assert result["deleted"] == 7


# ── Phase 7: KG cleanup ─────────────────────────────────────────────────────


class TestPhase7KGCleanup:
    def test_no_stale_entities(self, mock_conn):
        from scripts.pg_memory_gc import phase7_kg_cleanup

        conn, cursor = mock_conn
        cursor.fetchone.side_effect = [(0,), (0,), (0,)]

        result = phase7_kg_cleanup(conn, dry_run=False)

        assert result["entities_deleted"] == 0
        assert result["relations_weak"] == 0
        assert result["relations_orphan"] == 0

    def test_deletes_stale_entities_and_weak_relations(self, mock_conn):
        from scripts.pg_memory_gc import phase7_kg_cleanup

        conn, cursor = mock_conn
        cursor.fetchone.side_effect = [(3,), (2,), (1,)]
        cursor.fetchall.side_effect = [
            [("e1",), ("e2",), ("e3",)],  # entity deletes
            [("r1",), ("r2",)],  # weak relation deletes
            [("r3",)],  # orphan relation deletes
        ]

        result = phase7_kg_cleanup(conn, dry_run=False)

        assert result["entities_deleted"] == 3
        assert result["relations_weak"] == 2
        assert result["relations_orphan"] == 1
        conn.commit.assert_called()

    def test_dry_run_kg(self, mock_conn):
        from scripts.pg_memory_gc import phase7_kg_cleanup

        conn, cursor = mock_conn
        cursor.fetchone.side_effect = [(5,), (3,), (2,)]

        result = phase7_kg_cleanup(conn, dry_run=True)

        assert result["entities_deleted"] == 5
        assert result["relations_weak"] == 3
        assert result["relations_orphan"] == 2
        conn.commit.assert_not_called()


# ── Phase 8: VACUUM ─────────────────────────────────────────────────────────


class TestPhase8Vacuum:
    @patch("scripts.pg_memory_gc._connect")
    def test_vacuum_runs(self, mock_connect):
        from scripts.pg_memory_gc import phase8_vacuum

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        result = phase8_vacuum(dry_run=False)

        assert result["status"] == "done"
        mock_connect.assert_called_with(autocommit=True)
        # Should vacuum all 6 tables
        assert mock_cursor.execute.call_count == 6
        mock_conn.close.assert_called_once()

    def test_vacuum_dry_run(self):
        from scripts.pg_memory_gc import phase8_vacuum

        result = phase8_vacuum(dry_run=True)

        assert result["status"] == "skipped"


# ── CLI ──────────────────────────────────────────────────────────────────────


class TestCLI:
    @patch("scripts.pg_memory_gc.cmd_check")
    def test_check_command(self, mock_check):
        from scripts.pg_memory_gc import main

        main(["check"])
        mock_check.assert_called_once()

    @patch("scripts.pg_memory_gc.cmd_full")
    def test_full_command(self, mock_full):
        from scripts.pg_memory_gc import main

        main(["full"])
        mock_full.assert_called_once_with(dry_run=False)

    @patch("scripts.pg_memory_gc.cmd_full")
    def test_full_dry_run(self, mock_full):
        from scripts.pg_memory_gc import main

        main(["full", "--dry-run"])
        mock_full.assert_called_once_with(dry_run=True)

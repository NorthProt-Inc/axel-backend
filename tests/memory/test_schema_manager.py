"""Tests for SchemaManager — Phase 4 Cycle 4.1 + Phase 6 Cycle 6.1."""

import pytest

from backend.memory.recent.connection import SQLiteConnectionManager
from backend.memory.recent.schema import CURRENT_SCHEMA_VERSION, SchemaManager


@pytest.fixture
def conn_mgr(tmp_path):
    mgr = SQLiteConnectionManager(db_path=tmp_path / "test.db")
    yield mgr
    mgr.close()


class TestSchemaManager:
    def test_creates_sessions_table(self, conn_mgr):
        SchemaManager(conn_mgr).initialize()
        with conn_mgr.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'"
            )
            assert cursor.fetchone() is not None

    def test_creates_messages_table(self, conn_mgr):
        SchemaManager(conn_mgr).initialize()
        with conn_mgr.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
            )
            assert cursor.fetchone() is not None

    def test_creates_interaction_logs_table(self, conn_mgr):
        SchemaManager(conn_mgr).initialize()
        with conn_mgr.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='interaction_logs'"
            )
            assert cursor.fetchone() is not None

    def test_creates_archived_messages_table(self, conn_mgr):
        SchemaManager(conn_mgr).initialize()
        with conn_mgr.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='archived_messages'"
            )
            assert cursor.fetchone() is not None

    def test_idempotent_initialization(self, conn_mgr):
        schema = SchemaManager(conn_mgr)
        schema.initialize()
        schema.initialize()  # should not raise

    def test_creates_expected_indexes(self, conn_mgr):
        SchemaManager(conn_mgr).initialize()
        with conn_mgr.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
            indexes = {row[0] for row in cursor.fetchall()}

        expected = {
            "idx_messages_session",
            "idx_messages_timestamp",
            "idx_sessions_expires",
            "idx_interaction_logs_ts",
            "idx_interaction_logs_tier",
            "idx_interaction_logs_created",
            "idx_interaction_logs_router",
            "idx_archived_session",
        }
        assert expected.issubset(indexes)


# ── Cycle 6.1: Version-based migration ──────────────────────────────────────


class TestSchemaMigration:
    def test_tracks_schema_version(self, conn_mgr):
        SchemaManager(conn_mgr).initialize()
        with conn_mgr.get_connection() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            assert version == CURRENT_SCHEMA_VERSION

    def test_migration_runs_only_once(self, conn_mgr):
        schema = SchemaManager(conn_mgr)
        schema.initialize()

        # Insert data to verify it's not wiped on re-init
        with conn_mgr.get_connection() as conn:
            conn.execute(
                """INSERT INTO sessions
                   (session_id, key_topics, emotional_tone, turn_count,
                    started_at, ended_at, expires_at)
                   VALUES ('test', '[]', 'neutral', 0,
                           '2025-01-01', '2025-01-01', '2025-01-08')"""
            )
            conn.commit()

        schema.initialize()  # should skip migration

        with conn_mgr.get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            assert count == 1  # data preserved

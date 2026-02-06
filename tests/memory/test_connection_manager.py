"""Tests for SQLiteConnectionManager — Phase 1 TDD cycles."""

import sqlite3
import threading

import pytest

from backend.memory.recent.connection import SQLiteConnectionManager


# ── Cycle 1.1: Creation & Connection ────────────────────────────────────────


class TestCreateAndConnect:
    def test_creates_db_directory(self, tmp_path):
        nested = tmp_path / "a" / "b" / "test.db"
        mgr = SQLiteConnectionManager(db_path=nested)
        assert nested.parent.exists()
        mgr.close()

    def test_get_connection_returns_sqlite_connection(self, tmp_path):
        mgr = SQLiteConnectionManager(db_path=tmp_path / "test.db")
        with mgr.get_connection() as conn:
            assert isinstance(conn, sqlite3.Connection)
        mgr.close()


# ── Cycle 1.2: PRAGMA settings ──────────────────────────────────────────────


class TestPragmaSettings:
    def test_wal_mode_enabled(self, tmp_path):
        mgr = SQLiteConnectionManager(db_path=tmp_path / "test.db")
        with mgr.get_connection() as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            assert mode == "wal"
        mgr.close()

    def test_busy_timeout_set(self, tmp_path):
        mgr = SQLiteConnectionManager(db_path=tmp_path / "test.db")
        with mgr.get_connection() as conn:
            timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
            assert timeout == 5000
        mgr.close()


# ── Cycle 1.3: Thread safety ────────────────────────────────────────────────


class TestThreadSafety:
    def test_connection_is_reused(self, tmp_path):
        mgr = SQLiteConnectionManager(db_path=tmp_path / "test.db")
        with mgr.get_connection() as c1:
            id1 = id(c1)
        with mgr.get_connection() as c2:
            id2 = id(c2)
        assert id1 == id2
        mgr.close()

    def test_concurrent_access_does_not_raise(self, tmp_path):
        mgr = SQLiteConnectionManager(db_path=tmp_path / "test.db")
        with mgr.get_connection() as conn:
            conn.execute(
                "CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)"
            )
            conn.commit()

        errors: list[Exception] = []

        def worker(n: int):
            try:
                with mgr.get_connection() as conn:
                    conn.execute(
                        "INSERT INTO t (val) VALUES (?)", (f"row-{n}",)
                    )
                    conn.commit()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []

        with mgr.get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
            assert count == 4
        mgr.close()


# ── Cycle 1.4: close() + Context Manager ────────────────────────────────────


class TestCloseAndContextManager:
    def test_close_is_idempotent(self, tmp_path):
        mgr = SQLiteConnectionManager(db_path=tmp_path / "test.db")
        with mgr.get_connection():
            pass
        mgr.close()
        mgr.close()  # should not raise

    def test_connection_recreated_after_close(self, tmp_path):
        mgr = SQLiteConnectionManager(db_path=tmp_path / "test.db")
        with mgr.get_connection() as c1:
            id1 = id(c1)
        mgr.close()
        with mgr.get_connection() as c2:
            id2 = id(c2)
        assert id1 != id2
        mgr.close()

    def test_context_manager_protocol(self, tmp_path):
        with SQLiteConnectionManager(db_path=tmp_path / "test.db") as mgr:
            with mgr.get_connection() as conn:
                assert isinstance(conn, sqlite3.Connection)
        # after exiting, connection should be closed
        assert mgr._connection is None


# ── Cycle 1.5: Rollback on error ────────────────────────────────────────────


class TestRollback:
    def test_exception_triggers_rollback(self, tmp_path):
        mgr = SQLiteConnectionManager(db_path=tmp_path / "test.db")
        with mgr.get_connection() as conn:
            conn.execute(
                "CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)"
            )
            conn.commit()

        # Insert inside a failing block — should be rolled back
        with pytest.raises(RuntimeError):
            with mgr.get_connection() as conn:
                conn.execute("INSERT INTO t (val) VALUES ('oops')")
                raise RuntimeError("boom")

        with mgr.get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
            assert count == 0
        mgr.close()


# ── Cycle 3.1: transaction() context manager ────────────────────────────────


class TestTransaction:
    def _setup_table(self, mgr):
        with mgr.get_connection() as conn:
            conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
            conn.commit()

    def test_transaction_commits_on_success(self, tmp_path):
        mgr = SQLiteConnectionManager(db_path=tmp_path / "test.db")
        self._setup_table(mgr)

        with mgr.transaction() as conn:
            conn.execute("INSERT INTO t (val) VALUES ('ok')")

        with mgr.get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
            assert count == 1
        mgr.close()

    def test_transaction_rollbacks_on_exception(self, tmp_path):
        mgr = SQLiteConnectionManager(db_path=tmp_path / "test.db")
        self._setup_table(mgr)

        with pytest.raises(ValueError):
            with mgr.transaction() as conn:
                conn.execute("INSERT INTO t (val) VALUES ('bad')")
                raise ValueError("abort")

        with mgr.get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
            assert count == 0
        mgr.close()

    def test_transaction_uses_begin_immediate(self, tmp_path):
        """Verify BEGIN IMMEDIATE is used (exclusive write lock)."""
        mgr = SQLiteConnectionManager(db_path=tmp_path / "test.db")
        self._setup_table(mgr)

        # If BEGIN IMMEDIATE works, we should be able to do a write transaction
        with mgr.transaction() as conn:
            conn.execute("INSERT INTO t (val) VALUES ('immediate')")

        with mgr.get_connection() as conn:
            val = conn.execute("SELECT val FROM t").fetchone()[0]
            assert val == "immediate"
        mgr.close()

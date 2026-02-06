"""SQLite connection manager with thread safety and lifecycle management."""

import atexit
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from backend.core.logging import get_logger

_log = get_logger("memory.recent.connection")


class SQLiteConnectionManager:
    """Manages a single SQLite connection with thread-safe access.

    Uses atexit for cleanup instead of __del__ to avoid interpreter
    shutdown issues. Provides context manager protocol for scoped usage.

    Args:
        db_path: Path to SQLite database file.
    """

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()
        atexit.register(self._atexit_close)

    @contextmanager
    def get_connection(self):
        """Yield a SQLite connection, creating one if needed.

        The connection is reused across calls. On exception,
        a rollback is attempted before re-raising.

        Yields:
            sqlite3.Connection
        """
        with self._lock:
            if self._connection is None:
                self._connection = sqlite3.connect(
                    self.db_path,
                    check_same_thread=False,
                    timeout=10.0,
                )
                self._connection.execute("PRAGMA journal_mode=WAL")
                self._connection.execute("PRAGMA busy_timeout=5000")
                self._connection.execute("PRAGMA synchronous=NORMAL")

            try:
                yield self._connection
            except Exception as e:
                try:
                    self._connection.rollback()
                except Exception as rb_err:
                    _log.error(
                        "Rollback also failed",
                        original=str(e),
                        rollback=str(rb_err),
                    )
                raise

    @contextmanager
    def transaction(self):
        """Execute a block inside BEGIN IMMEDIATE … COMMIT/ROLLBACK.

        Yields:
            sqlite3.Connection with an active transaction.
        """
        with self.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def close(self):
        """Close the connection. Idempotent — safe to call multiple times."""
        with self._lock:
            if self._connection is not None:
                try:
                    self._connection.close()
                except Exception:
                    pass
                self._connection = None

    def _atexit_close(self):
        """Cleanup handler registered with atexit."""
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

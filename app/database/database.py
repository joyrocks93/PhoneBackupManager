"""
database.py
SQLite database for backup sessions, backed-up files, and history.
"""

import sqlite3
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DB_DIR = Path.home() / ".phone_backup_manager"
_DB_PATH = _DB_DIR / "backup_history.db"

_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS backup_sessions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id           TEXT    NOT NULL,
    device_name         TEXT    NOT NULL,
    backup_folder       TEXT    NOT NULL,
    org_mode            TEXT    NOT NULL DEFAULT 'preserve',
    started_at          TEXT    NOT NULL,
    finished_at         TEXT,
    status              TEXT    NOT NULL DEFAULT 'running',  -- running|completed|cancelled|failed
    total_files         INTEGER NOT NULL DEFAULT 0,
    files_copied        INTEGER NOT NULL DEFAULT 0,
    files_skipped       INTEGER NOT NULL DEFAULT 0,
    files_failed        INTEGER NOT NULL DEFAULT 0,
    total_bytes         INTEGER NOT NULL DEFAULT 0,
    bytes_copied        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS backed_up_files (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          INTEGER NOT NULL REFERENCES backup_sessions(id) ON DELETE CASCADE,
    device_id           TEXT    NOT NULL,
    source_path         TEXT    NOT NULL,
    dest_path           TEXT    NOT NULL,
    filename            TEXT    NOT NULL,
    file_size           INTEGER NOT NULL DEFAULT 0,
    modified_date       TEXT,
    backed_up_at        TEXT    NOT NULL,
    sha256_hash         TEXT,
    status              TEXT    NOT NULL DEFAULT 'copied'    -- copied|skipped|failed
);

CREATE INDEX IF NOT EXISTS idx_files_device_path ON backed_up_files(device_id, source_path);
CREATE INDEX IF NOT EXISTS idx_files_session      ON backed_up_files(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_device    ON backup_sessions(device_id);
"""


class Database:
    """Thread-safe SQLite wrapper."""

    def __init__(self, db_path: Path = _DB_PATH):
        self._db_path = db_path
        self._local = threading.local()
        _DB_DIR.mkdir(parents=True, exist_ok=True)
        # Apply schema on first connection
        conn = self._conn()
        conn.executescript(_SCHEMA)
        conn.commit()

    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
                timeout=30,
            )
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    # ── Sessions ───────────────────────────────────────────────────────────

    def create_session(
        self,
        device_id: str,
        device_name: str,
        backup_folder: str,
        org_mode: str = "preserve",
    ) -> int:
        conn = self._conn()
        cur = conn.execute(
            """INSERT INTO backup_sessions
               (device_id, device_name, backup_folder, org_mode, started_at, status)
               VALUES (?,?,?,?,?,?)""",
            (device_id, device_name, backup_folder, org_mode,
             datetime.now().isoformat(), "running"),
        )
        conn.commit()
        return cur.lastrowid  # type: ignore

    def update_session(self, session_id: int, **kwargs):
        if not kwargs:
            return
        cols = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [session_id]
        conn = self._conn()
        conn.execute(f"UPDATE backup_sessions SET {cols} WHERE id=?", vals)
        conn.commit()

    def finish_session(self, session_id: int, status: str = "completed"):
        self.update_session(
            session_id,
            finished_at=datetime.now().isoformat(),
            status=status,
        )

    def get_session(self, session_id: int) -> Optional[sqlite3.Row]:
        return self._conn().execute(
            "SELECT * FROM backup_sessions WHERE id=?", (session_id,)
        ).fetchone()

    def get_sessions(self, limit: int = 100) -> list:
        return self._conn().execute(
            "SELECT * FROM backup_sessions ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

    def increment_session_counters(
        self,
        session_id: int,
        *,
        copied: int = 0,
        skipped: int = 0,
        failed: int = 0,
        bytes_copied: int = 0,
    ):
        conn = self._conn()
        conn.execute(
            """UPDATE backup_sessions SET
               files_copied  = files_copied  + ?,
               files_skipped = files_skipped + ?,
               files_failed  = files_failed  + ?,
               bytes_copied  = bytes_copied  + ?
               WHERE id=?""",
            (copied, skipped, failed, bytes_copied, session_id),
        )
        conn.commit()

    # ── File records ───────────────────────────────────────────────────────

    def record_file(
        self,
        session_id: int,
        device_id: str,
        source_path: str,
        dest_path: str,
        filename: str,
        file_size: int,
        modified_date: Optional[str],
        status: str = "copied",
        sha256_hash: Optional[str] = None,
    ):
        conn = self._conn()
        conn.execute(
            """INSERT INTO backed_up_files
               (session_id, device_id, source_path, dest_path, filename,
                file_size, modified_date, backed_up_at, sha256_hash, status)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (session_id, device_id, source_path, dest_path, filename,
             file_size, modified_date, datetime.now().isoformat(),
             sha256_hash, status),
        )
        conn.commit()

    def is_file_backed_up(
        self,
        device_id: str,
        source_path: str,
        file_size: int,
        modified_date: Optional[str] = None,
    ) -> bool:
        """Check if a file from this device has already been backed up."""
        row = self._conn().execute(
            """SELECT id FROM backed_up_files
               WHERE device_id=? AND source_path=?
               AND file_size=? AND status='copied'
               LIMIT 1""",
            (device_id, source_path, file_size),
        ).fetchone()
        return row is not None

    def get_backed_up_paths(self, device_id: str, session_id: Optional[int] = None) -> set[str]:
        """Return set of already-backed-up source paths for a device."""
        if session_id:
            rows = self._conn().execute(
                "SELECT source_path FROM backed_up_files WHERE device_id=? AND session_id=? AND status='copied'",
                (device_id, session_id),
            ).fetchall()
        else:
            rows = self._conn().execute(
                "SELECT source_path FROM backed_up_files WHERE device_id=? AND status='copied'",
                (device_id,),
            ).fetchall()
        return {r["source_path"] for r in rows}

    def get_file_hash(self, device_id: str, source_path: str) -> Optional[str]:
        row = self._conn().execute(
            "SELECT sha256_hash FROM backed_up_files WHERE device_id=? AND source_path=? AND status='copied' ORDER BY backed_up_at DESC LIMIT 1",
            (device_id, source_path),
        ).fetchone()
        return row["sha256_hash"] if row else None

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


# Module-level singleton
_db_instance: Database | None = None


def get_db() -> Database:
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance

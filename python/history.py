# SPDX-License-Identifier: MPL-2.0
"""Detection log in SQLite, for "seen N times" counts and the daily summary.

Times are stored as local timestamps (the board's timezone), so "today" and the
hour of day match what the dashboard shows.

Each detection has a source: "local" for birds this unit heard (or, in receiver
mode, the birds it plays for another unit), and "cloud" for another BirdBox's birds
received while this one also listens (listen mode "both"). Every query takes the
source, so cards and summaries for the two never mix.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path

DB_FILE = Path(__file__).resolve().parent.parent / "data" / "birdbox.db"

_lock = threading.Lock()
_db: sqlite3.Connection | None = None


def _conn() -> sqlite3.Connection:
    global _db
    if _db is None:
        DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        _db = sqlite3.connect(DB_FILE, check_same_thread=False)
        _db.execute(
            "CREATE TABLE IF NOT EXISTS detections ("
            " ts REAL NOT NULL, day TEXT NOT NULL, hour INTEGER NOT NULL,"
            " scientific TEXT NOT NULL, common TEXT NOT NULL, confidence REAL NOT NULL)"
        )
        columns = {row[1] for row in _db.execute("PRAGMA table_info(detections)")}
        if "source" not in columns:     # logs from before v3
            _db.execute("ALTER TABLE detections ADD COLUMN source TEXT NOT NULL DEFAULT 'local'")
        _db.execute("CREATE INDEX IF NOT EXISTS detections_day ON detections(day)")
        _db.execute("CREATE INDEX IF NOT EXISTS detections_species ON detections(scientific)")
        _db.commit()
    return _db


def record(when: datetime, scientific: str, common: str, confidence: float, source: str = "local") -> None:
    with _lock:
        db = _conn()
        db.execute(
            "INSERT INTO detections (ts, day, hour, scientific, common, confidence, source)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (when.timestamp(), when.strftime("%Y-%m-%d"), when.hour, scientific, common, confidence, source),
        )
        db.commit()


def last(source: str = "local") -> dict | None:
    """The most recent detection."""
    with _lock:
        row = _conn().execute(
            "SELECT ts, scientific, common, confidence FROM detections WHERE source = ? ORDER BY ts DESC LIMIT 1",
            (source,),
        ).fetchone()
    if row is None:
        return None
    return {"when": datetime.fromtimestamp(row[0]), "scientific": row[1], "common": row[2], "confidence": row[3]}


def counts(scientific: str, day: str | None = None, source: str = "local") -> tuple[int, int]:
    """(times heard on `day`, times heard ever) for one species."""
    day = day or datetime.now().strftime("%Y-%m-%d")
    with _lock:
        db = _conn()
        today = db.execute(
            "SELECT COUNT(*) FROM detections WHERE scientific = ? AND day = ? AND source = ?", (scientific, day, source)
        ).fetchone()[0]
        total = db.execute("SELECT COUNT(*) FROM detections WHERE scientific = ? AND source = ?",
                           (scientific, source)).fetchone()[0]
    return today, total


def day_summary(day: str | None = None, top: int = 5, source: str = "local") -> dict:
    """Totals and top species for one day."""
    day = day or datetime.now().strftime("%Y-%m-%d")
    with _lock:
        db = _conn()
        total, species = db.execute(
            "SELECT COUNT(*), COUNT(DISTINCT scientific) FROM detections WHERE day = ? AND source = ?", (day, source)
        ).fetchone()
        leaders = db.execute(
            "SELECT common, scientific, COUNT(*) AS n FROM detections WHERE day = ? AND source = ?"
            " GROUP BY scientific ORDER BY n DESC, MAX(ts) DESC LIMIT ?",
            (day, source, top),
        ).fetchall()
    return {"day": day, "total": total, "species": species,
            "top": [{"common": c, "scientific": s, "count": n} for c, s, n in leaders]}


def hourly_last_24h(now: datetime | None = None, source: str = "local") -> list[tuple[int, int]]:
    """Detections per clock hour over the last 24 hours, oldest first: [(hour, count)]."""
    now = now or datetime.now()
    end = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    start = end - timedelta(hours=24)
    with _lock:
        rows = _conn().execute(
            "SELECT ts FROM detections WHERE ts >= ? AND ts < ? AND source = ?",
            (start.timestamp(), end.timestamp(), source)
        ).fetchall()
    buckets = [0] * 24
    for (ts,) in rows:
        buckets[int((ts - start.timestamp()) // 3600)] += 1
    return [((start + timedelta(hours=k)).hour, buckets[k]) for k in range(24)]


def recent(limit: int = 20, source: str = "local") -> list[dict]:
    with _lock:
        rows = _conn().execute(
            "SELECT ts, common, confidence FROM detections WHERE source = ? ORDER BY ts DESC LIMIT ?", (source, limit)
        ).fetchall()
    return [{"when": datetime.fromtimestamp(t), "common": c, "confidence": conf} for t, c, conf in rows]


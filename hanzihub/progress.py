"""Per-character learning state for the 📖 Read page.

A tiny SQLite store (in the project ``cache/`` dir — it does NOT touch the old
``atcre.db``) holding, per character: a familiarity ``status`` (unknown / weak /
known), success/error tallies, and a spaced-repetition schedule (interval doubles
on a correct recall, resets on a miss). The SRS algorithm is ported from atcre.
Connections are opened per call so it's safe under Streamlit's rerun threads.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from . import paths

_DB = Path(paths.ROOT) / "cache" / "progress.db"
_DAY = 86400.0


def _conn() -> sqlite3.Connection:
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(_DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS user_chars (
        char          TEXT PRIMARY KEY,
        status        TEXT    DEFAULT 'unknown',   -- unknown | weak | known
        error_count   INTEGER DEFAULT 0,
        success_count INTEGER DEFAULT 0,
        last_seen     REAL    DEFAULT 0,
        next_review   REAL    DEFAULT 0,
        interval_days REAL    DEFAULT 1)""")
    return c


def get(char: str) -> dict | None:
    c = _conn()
    r = c.execute("SELECT * FROM user_chars WHERE char=?", (char,)).fetchone()
    c.close()
    return dict(r) if r else None


def status_map(chars) -> dict[str, str]:
    """``{char: status}`` for the given chars; ones never seen are absent."""
    chars = [c for c in dict.fromkeys(chars)]
    if not chars:
        return {}
    c = _conn()
    rows = c.execute(
        f"SELECT char, status FROM user_chars WHERE char IN ({','.join('?' * len(chars))})",
        tuple(chars)).fetchall()
    c.close()
    return {r["char"]: r["status"] for r in rows}


def mark(char: str, correct: bool) -> None:
    """Record a quiz/review outcome and reschedule (interval ×2 on success, →1
    day on a miss). Promotes to 'known' once clearly recalled (≥3 successes and
    more right than wrong)."""
    now = time.time()
    ex = get(char)
    c = _conn()
    # A correct recall schedules the interval into the future; a miss stays due
    # now so it comes straight back around this session (Anki-style "again").
    if ex is None:
        c.execute("INSERT INTO user_chars(char,status,error_count,success_count,"
                  "last_seen,next_review,interval_days) VALUES(?,?,?,?,?,?,?)",
                  (char, "known" if correct else "weak", 0 if correct else 1,
                   1 if correct else 0, now, now + _DAY if correct else now, 1))
    else:
        ec = ex["error_count"] + (0 if correct else 1)
        sc = ex["success_count"] + (1 if correct else 0)
        interval = ex["interval_days"] * 2 if correct else 1
        status = "known" if (sc > ec and sc >= 3) else "weak"
        c.execute("UPDATE user_chars SET status=?,error_count=?,success_count=?,"
                  "last_seen=?,next_review=?,interval_days=? WHERE char=?",
                  (status, ec, sc, now, now + interval * _DAY if correct else now,
                   interval, char))
    c.commit()
    c.close()


def record_clicked(char: str) -> None:
    """A look-up while reading → the reader didn't know it: mark weak, due soon."""
    now = time.time()
    ex = get(char)
    c = _conn()
    if ex is None:
        c.execute("INSERT INTO user_chars(char,status,error_count,success_count,"
                  "last_seen,next_review,interval_days) VALUES(?,?,?,?,?,?,?)",
                  (char, "weak", 1, 0, now, now, 1))       # due now
    elif ex["status"] != "known":
        c.execute("UPDATE user_chars SET status='weak', error_count=error_count+1, "
                  "last_seen=?, next_review=? WHERE char=?", (now, now, char))
    else:
        c.execute("UPDATE user_chars SET last_seen=? WHERE char=?", (now, char))
    c.commit()
    c.close()


def set_status(char: str, status: str) -> None:
    """Directly set a character's status (the reader's 'I know this' toggle)."""
    now = time.time()
    c = _conn()
    c.execute("INSERT INTO user_chars(char,status,last_seen,next_review,interval_days) "
              "VALUES(?,?,?,?,?) ON CONFLICT(char) DO UPDATE SET status=excluded.status, "
              "last_seen=excluded.last_seen",
              (char, status, now, now + _DAY, 1))
    c.commit()
    c.close()


def review_queue(limit: int = 40) -> list[dict]:
    """Characters whose next-review time has passed, soonest first."""
    now = time.time()
    c = _conn()
    rows = c.execute("SELECT * FROM user_chars WHERE next_review<=? "
                     "ORDER BY next_review ASC LIMIT ?", (now, limit)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def all_chars() -> list[dict]:
    c = _conn()
    rows = c.execute("SELECT * FROM user_chars ORDER BY last_seen DESC").fetchall()
    c.close()
    return [dict(r) for r in rows]


def stats() -> dict:
    out = {"known": 0, "weak": 0, "unknown": 0, "total": 0, "due": len(review_queue(9999))}
    for r in all_chars():
        out["total"] += 1
        out[r["status"]] = out.get(r["status"], 0) + 1
    return out

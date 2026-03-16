"""SQLite database layer — lightweight persistence for reviews and feedback."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from agentforge.config import DB_PATH


def _get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Create a connection with row factory enabled."""
    path = db_path or DB_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: str | None = None) -> None:
    """Create tables if they don't exist."""
    conn = _get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS reviews (
            id          TEXT PRIMARY KEY,
            request     TEXT NOT NULL,
            result      TEXT,
            status      TEXT NOT NULL DEFAULT 'pending',
            created_at  TEXT NOT NULL,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id          TEXT PRIMARY KEY,
            review_id   TEXT NOT NULL,
            finding_id  TEXT NOT NULL,
            accepted    INTEGER NOT NULL,
            comment     TEXT,
            created_at  TEXT NOT NULL,
            FOREIGN KEY (review_id) REFERENCES reviews(id)
        );
    """)
    conn.commit()
    conn.close()


def create_review(request_json: str, db_path: str | None = None) -> str:
    """Insert a new pending review. Returns the review ID."""
    review_id = str(uuid.uuid4())
    conn = _get_connection(db_path)
    conn.execute(
        "INSERT INTO reviews (id, request, status, created_at) VALUES (?, ?, 'pending', ?)",
        (review_id, request_json, datetime.now(UTC).isoformat()),
    )
    conn.commit()
    conn.close()
    return review_id


def start_review(review_id: str, db_path: str | None = None) -> None:
    """Mark a review as actively running."""
    conn = _get_connection(db_path)
    conn.execute(
        "UPDATE reviews SET status = 'running' WHERE id = ?",
        (review_id,),
    )
    conn.commit()
    conn.close()


def complete_review(review_id: str, result_json: str, db_path: str | None = None) -> None:
    """Mark a review as completed and store the result."""
    conn = _get_connection(db_path)
    conn.execute(
        "UPDATE reviews SET result = ?, status = 'completed', completed_at = ? WHERE id = ?",
        (result_json, datetime.now(UTC).isoformat(), review_id),
    )
    conn.commit()
    conn.close()


def fail_review(review_id: str, error: str, db_path: str | None = None) -> None:
    """Mark a review as failed."""
    conn = _get_connection(db_path)
    conn.execute(
        "UPDATE reviews SET result = ?, status = 'failed', completed_at = ? WHERE id = ?",
        (json.dumps({"error": error}), datetime.now(UTC).isoformat(), review_id),
    )
    conn.commit()
    conn.close()


def get_review(review_id: str, db_path: str | None = None) -> dict | None:
    """Fetch a review by ID."""
    conn = _get_connection(db_path)
    row = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def list_reviews(limit: int = 50, db_path: str | None = None) -> list[dict]:
    """List recent reviews, newest first."""
    conn = _get_connection(db_path)
    rows = conn.execute(
        "SELECT id, status, created_at, completed_at FROM reviews ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_feedback(
    review_id: str,
    finding_id: str,
    accepted: bool,
    comment: str | None = None,
    db_path: str | None = None,
) -> str:
    """Store feedback on a finding. Returns the feedback ID."""
    feedback_id = str(uuid.uuid4())
    conn = _get_connection(db_path)
    conn.execute(
        "INSERT INTO feedback (id, review_id, finding_id, accepted, comment, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (feedback_id, review_id, finding_id, int(accepted), comment, datetime.now(UTC).isoformat()),
    )
    conn.commit()
    conn.close()
    return feedback_id


def get_feedback_stats(db_path: str | None = None) -> dict:
    """Aggregate feedback statistics."""
    conn = _get_connection(db_path)
    rows = conn.execute("""
        SELECT
            COUNT(*) as total,
            SUM(accepted) as accepted,
            COUNT(*) - SUM(accepted) as rejected
        FROM feedback
    """).fetchone()
    conn.close()
    if rows is None or rows["total"] == 0:
        return {"total": 0, "accepted": 0, "rejected": 0, "acceptance_rate": 0.0}
    return {
        "total": rows["total"],
        "accepted": rows["accepted"],
        "rejected": rows["rejected"],
        "acceptance_rate": round(rows["accepted"] / rows["total"] * 100, 1),
    }

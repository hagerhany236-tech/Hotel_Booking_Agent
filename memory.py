"""
memory.py
Long-term preference store using SQLite.

Schema
------
Table: guest_preferences
    guest_name  TEXT PRIMARY KEY
    preferences TEXT  (JSON array of strings)
    updated_at  TEXT  (ISO timestamp)
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "preferences.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS guest_preferences (
            guest_name  TEXT PRIMARY KEY,
            preferences TEXT NOT NULL DEFAULT '[]',
            updated_at  TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def save_preferences(guest_name: str, preferences: list[str]) -> None:
    """Upsert the preference list for a guest."""
    if not preferences:
        return
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO guest_preferences (guest_name, preferences, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(guest_name) DO UPDATE SET
                preferences = excluded.preferences,
                updated_at  = excluded.updated_at
            """,
            (guest_name.strip(), json.dumps(preferences), now),
        )


def load_preferences(guest_name: str) -> list[str]:
    """Return stored preferences for a guest (empty list if none)."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT preferences FROM guest_preferences WHERE guest_name = ?",
            (guest_name.strip(),),
        ).fetchone()
    if row is None:
        return []
    return json.loads(row[0])


def build_preference_prompt(guest_name: str) -> str:
    """
    Return a system-prompt snippet injecting stored preferences,
    or an empty string if no preferences are on record.
    """
    prefs = load_preferences(guest_name)
    if not prefs:
        return ""
    lines = "\n".join(f"  - {p}" for p in prefs)
    return (
        f"\nReturning guest preferences for {guest_name}:\n"
        f"{lines}\n"
        "Please proactively apply these preferences when making suggestions.\n"
    )

"""
Database helper — optional SQLite-backed data store.

This file is included in every scaffolded project but does nothing unless
you call init_db(). If your agent doesn't need a database, ignore this file.

Usage:
    from db import init_db, get_record, insert_record, update_record, list_records

    init_db()  # creates data.db with a "records" table (call once at startup)

    insert_record("E-1042", {"name": "Rhea", "email": "rhea@company.com", "role": "Engineer"})
    record = get_record("E-1042")
    update_record("E-1042", {"role": "Senior Engineer"})
    all_records = list_records()

Swapping to another database:
    Replace sqlite3 with your driver (psycopg2, mysql.connector, pymongo, etc.).
    The functions stay the same — your tools don't need to change.
"""

import json
import sqlite3

DB_PATH = "data.db"


def init_db():
    """Create the records table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS records (
            record_id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def get_record(record_id: str) -> dict | None:
    """Get a record by ID. Returns None if not found."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT data FROM records WHERE record_id = ?", (record_id,)
    ).fetchone()
    conn.close()
    if row:
        return {"record_id": record_id, **json.loads(row[0])}
    return None


def insert_record(record_id: str, data: dict):
    """Insert a new record. Raises on duplicate ID."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO records (record_id, data) VALUES (?, ?)",
        (record_id, json.dumps(data)),
    )
    conn.commit()
    conn.close()


def upsert_record(record_id: str, data: dict):
    """Insert or update a record."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO records (record_id, data) VALUES (?, ?) "
        "ON CONFLICT(record_id) DO UPDATE SET data = excluded.data",
        (record_id, json.dumps(data)),
    )
    conn.commit()
    conn.close()


def update_record(record_id: str, updates: dict) -> bool:
    """Merge updates into an existing record. Returns False if not found."""
    existing = get_record(record_id)
    if not existing:
        return False
    existing.pop("record_id", None)
    existing.update(updates)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE records SET data = ? WHERE record_id = ?",
        (json.dumps(existing), record_id),
    )
    conn.commit()
    conn.close()
    return True


def delete_record(record_id: str) -> bool:
    """Delete a record. Returns False if not found."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("DELETE FROM records WHERE record_id = ?", (record_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def list_records() -> list[dict]:
    """Return all records."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT record_id, data FROM records").fetchall()
    conn.close()
    return [{"record_id": r[0], **json.loads(r[1])} for r in rows]

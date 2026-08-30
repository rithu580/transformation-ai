"""
database.py
-----------
Handles all persistence. SQLite is used because it's free, needs zero setup,
and is more than enough for a programme of dozens/hundreds of initiatives.

Schema:
  initiatives   -> the transformation initiatives themselves
  relationships -> the dependencies/conflicts discovered BETWEEN initiatives
                   (this table is what makes the app "connected intelligence"
                   instead of just a list of records)
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "transformation.db"


def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Creates tables if they do not already exist. Safe to call every run —
    this is how we guarantee data persists across restarts (a mandatory rule)."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS initiatives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL,
            requires TEXT,      -- JSON list of things this initiative needs
            provides TEXT,      -- JSON list of things this initiative produces
            owner TEXT,
            timeline TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            initiative_a_id INTEGER NOT NULL,
            initiative_b_id INTEGER NOT NULL,
            relationship_type TEXT NOT NULL,   -- 'depends_on' | 'conflict' | 'shares_resource'
            shared_item TEXT,                  -- the specific requirement/resource that triggered this
            explanation TEXT,                  -- human-readable reasoning (traceability)
            risk_level TEXT,                   -- 'Low' | 'Medium' | 'High'
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (initiative_a_id) REFERENCES initiatives(id),
            FOREIGN KEY (initiative_b_id) REFERENCES initiatives(id)
        )
    """)

    conn.commit()
    conn.close()


def add_initiative(name, description, requires, provides, owner="", timeline=""):
    """Add an initiative. If the name already exists, return the existing ID."""
    
    conn = get_connection()
    cur = conn.cursor()

    try:
        # Check whether this initiative already exists
        cur.execute(
            "SELECT id FROM initiatives WHERE name = ?",
            (name.strip(),)
        )

        existing = cur.fetchone()

        if existing:
            return existing[0]

        # Insert only if the initiative does not already exist
        cur.execute(
            """
            INSERT INTO initiatives
                (name, description, requires, provides, owner, timeline)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                description,
                json.dumps(requires),
                json.dumps(provides),
                owner,
                timeline
            )
        )

        conn.commit()
        return cur.lastrowid

    finally:
        conn.close()


def get_all_initiatives():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM initiatives ORDER BY id").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["requires"] = json.loads(d["requires"] or "[]")
        d["provides"] = json.loads(d["provides"] or "[]")
        result.append(d)
    return result


def get_initiative_by_id(initiative_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM initiatives WHERE id = ?", (initiative_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["requires"] = json.loads(d["requires"] or "[]")
    d["provides"] = json.loads(d["provides"] or "[]")
    return d


def clear_relationships_for(initiative_id):
    """Wipe old relationships for one initiative before re-analysing it
    (so re-running analysis doesn't create duplicates)."""
    conn = get_connection()
    conn.execute("""
        DELETE FROM relationships
        WHERE initiative_a_id = ? OR initiative_b_id = ?
    """, (initiative_id, initiative_id))
    conn.commit()
    conn.close()


def add_relationship(a_id, b_id, rel_type, shared_item, explanation, risk_level="Low"):
    conn = get_connection()
    conn.execute("""
        INSERT INTO relationships
        (initiative_a_id, initiative_b_id, relationship_type, shared_item, explanation, risk_level)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (a_id, b_id, rel_type, shared_item, explanation, risk_level))
    conn.commit()
    conn.close()


def get_all_relationships():
    conn = get_connection()
    rows = conn.execute("""
        SELECT r.*, 
               ia.name AS a_name, 
               ib.name AS b_name
        FROM relationships r
        JOIN initiatives ia ON r.initiative_a_id = ia.id
        JOIN initiatives ib ON r.initiative_b_id = ib.id
        ORDER BY r.id
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_initiative(initiative_id):
    conn = get_connection()
    conn.execute("DELETE FROM relationships WHERE initiative_a_id = ? OR initiative_b_id = ?",
                 (initiative_id, initiative_id))
    conn.execute("DELETE FROM initiatives WHERE id = ?", (initiative_id,))
    conn.commit()
    conn.close()

"""SQLite access. One connection per request; the schema is created on startup."""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name          TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin', 'editor')),
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    slug       TEXT NOT NULL UNIQUE,
    body       TEXT NOT NULL DEFAULT '',
    status     TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
    locked     INTEGER NOT NULL DEFAULT 0,
    author_id  INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS posts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    slug       TEXT NOT NULL UNIQUE,
    body       TEXT NOT NULL DEFAULT '',
    status     TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
    post_type  TEXT NOT NULL CHECK (post_type IN ('event', 'team_update')),
    author_id  INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS listings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    email        TEXT NOT NULL,
    class_year   INTEGER,
    consent_date TEXT,
    recorded_by  INTEGER NOT NULL REFERENCES users(id),
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: Path | str) -> None:
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        # Databases made before T05 have no Locked flag on pages.
        columns = [r["name"] for r in conn.execute("PRAGMA table_info(pages)")]
        if "locked" not in columns:
            conn.execute("ALTER TABLE pages ADD COLUMN locked INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    finally:
        conn.close()

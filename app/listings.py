"""Listings (alumni who opted in): data access. Routes call these; they never touch HTTP.

ADR-003: the export reads names only. `consented_names` is the only query the
publisher uses, and it never selects the email column.
"""
from __future__ import annotations

import sqlite3

from app.pages import _now

_SELECT = ("SELECT listings.*, users.name AS recorder_name FROM listings "
           "JOIN users ON users.id = listings.recorded_by")


def list_listings(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(f"{_SELECT} ORDER BY listings.name COLLATE NOCASE").fetchall()


def get(conn: sqlite3.Connection, listing_id: int) -> sqlite3.Row | None:
    return conn.execute(f"{_SELECT} WHERE listings.id = ?", (listing_id,)).fetchone()


def consented_names(conn: sqlite3.Connection) -> list[str]:
    """Names of consented Listings, alphabetical. Never reads the email."""
    rows = conn.execute("SELECT name FROM listings WHERE consent_date IS NOT NULL "
                        "ORDER BY name COLLATE NOCASE, id").fetchall()
    return [r["name"] for r in rows]


def create(conn: sqlite3.Connection, *, name: str, email: str, class_year: int | None,
           consent_date: str | None, recorded_by: int) -> int:
    now = _now()
    cur = conn.execute(
        "INSERT INTO listings (name, email, class_year, consent_date, recorded_by,"
        " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, email, class_year, consent_date, recorded_by, now, now))
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def update(conn: sqlite3.Connection, listing_id: int, *, name: str, email: str,
           class_year: int | None, consent_date: str | None) -> None:
    conn.execute("UPDATE listings SET name = ?, email = ?, class_year = ?,"
                 " consent_date = ?, updated_at = ? WHERE id = ?",
                 (name, email, class_year, consent_date, _now(), listing_id))
    conn.commit()


def delete(conn: sqlite3.Connection, listing_id: int) -> None:
    conn.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
    conn.commit()

"""Pages: data access and slugs. Routes call these; they never touch HTTP."""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from datetime import datetime, timezone

STATUSES = ("draft", "published")

_SELECT = ("SELECT pages.*, users.name AS author_name FROM pages "
           "JOIN users ON users.id = pages.author_id")


class SlugTaken(Exception):
    pass


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def list_pages(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(f"{_SELECT} ORDER BY pages.updated_at DESC, pages.id DESC").fetchall()


def list_published(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(f"{_SELECT} WHERE pages.status = 'published'").fetchall()


def get(conn: sqlite3.Connection, page_id: int) -> sqlite3.Row | None:
    return conn.execute(f"{_SELECT} WHERE pages.id = ?", (page_id,)).fetchone()


def create(conn: sqlite3.Connection, *, title: str, slug: str, body: str,
           status: str, author_id: int) -> int:
    now = _now()
    try:
        cur = conn.execute(
            "INSERT INTO pages (title, slug, body, status, author_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, slug, body, status, author_id, now, now))
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise SlugTaken(slug) from exc
    assert cur.lastrowid is not None
    return cur.lastrowid


def update(conn: sqlite3.Connection, page_id: int, *, title: str, slug: str,
           body: str, status: str) -> None:
    try:
        conn.execute(
            "UPDATE pages SET title = ?, slug = ?, body = ?, status = ?, updated_at = ?"
            " WHERE id = ?", (title, slug, body, status, _now(), page_id))
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise SlugTaken(slug) from exc


def set_status(conn: sqlite3.Connection, page_id: int, status: str) -> None:
    conn.execute("UPDATE pages SET status = ?, updated_at = ? WHERE id = ?",
                 (status, _now(), page_id))
    conn.commit()


def delete(conn: sqlite3.Connection, page_id: int) -> None:
    conn.execute("DELETE FROM pages WHERE id = ?", (page_id,))
    conn.commit()

"""Posts (Events and Team Updates): data access. Routes call these; they never touch HTTP."""
from __future__ import annotations

import sqlite3

from app.pages import STATUSES, SlugTaken, _now, slugify  # noqa: F401  (re-exported)

POST_TYPES = {"event": "Event", "team_update": "Team Update"}
DEFAULT_TYPE = "event"

_SELECT = ("SELECT posts.*, users.name AS author_name FROM posts "
           "JOIN users ON users.id = posts.author_id")
_NEWEST_FIRST = "ORDER BY posts.created_at DESC, posts.id DESC"


def list_posts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(f"{_SELECT} ORDER BY posts.updated_at DESC, posts.id DESC").fetchall()


def list_published(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Published posts, newest first."""
    return conn.execute(
        f"{_SELECT} WHERE posts.status = 'published' {_NEWEST_FIRST}").fetchall()


def get(conn: sqlite3.Connection, post_id: int) -> sqlite3.Row | None:
    return conn.execute(f"{_SELECT} WHERE posts.id = ?", (post_id,)).fetchone()


def create(conn: sqlite3.Connection, *, title: str, slug: str, body: str, status: str,
           post_type: str, author_id: int) -> int:
    now = _now()
    try:
        cur = conn.execute(
            "INSERT INTO posts (title, slug, body, status, post_type, author_id,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (title, slug, body, status, post_type, author_id, now, now))
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise SlugTaken(slug) from exc
    assert cur.lastrowid is not None
    return cur.lastrowid


def update(conn: sqlite3.Connection, post_id: int, *, title: str, slug: str, body: str,
           status: str, post_type: str) -> None:
    try:
        conn.execute(
            "UPDATE posts SET title = ?, slug = ?, body = ?, status = ?, post_type = ?,"
            " updated_at = ? WHERE id = ?",
            (title, slug, body, status, post_type, _now(), post_id))
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise SlugTaken(slug) from exc


def set_status(conn: sqlite3.Connection, post_id: int, status: str) -> None:
    conn.execute("UPDATE posts SET status = ?, updated_at = ? WHERE id = ?",
                 (status, _now(), post_id))
    conn.commit()


def delete(conn: sqlite3.Connection, post_id: int) -> None:
    conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    conn.commit()

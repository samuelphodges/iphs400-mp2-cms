"""Users and passwords. Passwords are stored only as argon2 hashes."""
from __future__ import annotations

import sqlite3

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

ROLES = ("admin", "editor")

_hasher = PasswordHasher()
# Verified against when the email is unknown, so an unknown account and a wrong
# password take about the same time.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_user(conn: sqlite3.Connection, *, email: str, name: str,
                password: str, role: str) -> int:
    if role not in ROLES:
        raise ValueError(f"unknown role: {role}")
    cur = conn.execute(
        "INSERT INTO users (email, name, password_hash, role) VALUES (?, ?, ?, ?)",
        (email.strip(), name, hash_password(password), role),
    )
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def get_by_email(conn: sqlite3.Connection, email: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM users WHERE email = ?", (email.strip(),)
    ).fetchone()


def get_by_id(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def authenticate(conn: sqlite3.Connection, email: str, password: str
                 ) -> tuple[sqlite3.Row | None, str | None]:
    """Return (user, None) on success, or (None, reason).

    reason is "invalid" for an unknown email or wrong password (the caller must
    show one message for both), or "inactive" when the password was right but
    the account is deactivated.
    """
    user = get_by_email(conn, email)
    if user is None:
        verify_password(_DUMMY_HASH, password)
        return None, "invalid"
    if not verify_password(user["password_hash"], password):
        return None, "invalid"
    if not user["active"]:
        return None, "inactive"
    return user, None


def list_users(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM users ORDER BY name COLLATE NOCASE, id").fetchall()


def set_role(conn: sqlite3.Connection, user_id: int, role: str) -> None:
    if role not in ROLES:
        raise ValueError(f"unknown role: {role}")
    conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    conn.commit()


def set_active(conn: sqlite3.Connection, user_id: int, active: bool) -> None:
    conn.execute("UPDATE users SET active = ? WHERE id = ?", (int(active), user_id))
    conn.commit()

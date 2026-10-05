"""Shared web plumbing: templates, sessions, the login check and CSRF."""
from __future__ import annotations

import hmac
import secrets
import sqlite3
from typing import Iterator

from fastapi import Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates

from app import db, settings, users

templates = Jinja2Templates(directory=str(settings.TEMPLATES))


class LoginRequired(Exception):
    """Raised for an anonymous visitor; the app turns it into a redirect."""


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    conn = db.connect(request.app.state.database_path)
    try:
        yield conn
    finally:
        conn.close()


def current_user(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    """The signed-in, active user, or LoginRequired. Guards every admin route."""
    user_id = request.session.get("user_id")
    user = users.get_by_id(conn, user_id) if user_id else None
    if user is None or not user["active"]:
        request.session.clear()
        raise LoginRequired()
    return user


def csrf_token(request: Request) -> str:
    token = request.session.get("csrf")
    if not token:
        token = request.session["csrf"] = secrets.token_urlsafe(32)
    return token


async def verify_csrf(request: Request) -> None:
    """Dependency for every state-changing form: reject a missing/bad token."""
    form = await request.form()
    sent = form.get("csrf_token")
    expected = request.session.get("csrf")
    if (not isinstance(sent, str) or not expected
            or not hmac.compare_digest(sent, expected)):
        raise HTTPException(status_code=403, detail="Missing or invalid CSRF token.")


def flash(request: Request, text: str, kind: str = "ok") -> None:
    """Queue a message to show on the next page (success "ok" or "error")."""
    request.session["flash"] = {"kind": kind, "text": text}


def render(request: Request, name: str, context: dict | None = None,
           status_code: int = 200, user=None):
    ctx = {"title": settings.SITE_TITLE, "csrf_token": csrf_token(request),
           "user": user, "flash": request.session.pop("flash", None)}
    ctx.update(context or {})
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)

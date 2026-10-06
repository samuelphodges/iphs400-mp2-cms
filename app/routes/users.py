"""Admin: manage users. Admin only; users are deactivated, never deleted."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app import users
from app.web import flash, get_db, render, require_admin, verify_csrf

# Router-level, so it runs before any per-route CSRF check: anonymous -> login
# redirect, editor -> refusal page, whatever the request carries.
router = APIRouter(prefix="/admin/users", dependencies=[Depends(require_admin)])
csrf_required = [Depends(verify_csrf)]

BAD_ROLE = "Choose admin or editor as the role."
SELF_DEACTIVATE = "You cannot deactivate your own account."
SELF_DEMOTE = "You cannot change your own role: the site must always have an admin."


def _user_or_404(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row:
    target = users.get_by_id(conn, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="No such user.")
    return target


def _screen(request: Request, conn: sqlite3.Connection, user, form: dict | None = None,
            status_code: int = 200, error: str | None = None):
    if error:
        flash(request, error, "error")
    return render(request, "admin/users.html",
                  {"title": "Users", "users": users.list_users(conn), "roles": users.ROLES,
                   "form": form or {"name": "", "email": "", "role": "editor"}},
                  status_code=status_code, user=user)


def _back() -> RedirectResponse:
    return RedirectResponse("/admin/users", status_code=303)


@router.get("")
def user_list(request: Request, user=Depends(require_admin),
              conn: sqlite3.Connection = Depends(get_db)):
    return _screen(request, conn, user)


@router.post("", dependencies=csrf_required)
def create_user(request: Request, name: str = Form(""), email: str = Form(""),
                password: str = Form(""), role: str = Form("editor"),
                user=Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    form = {"name": name.strip(), "email": email.strip(), "role": role}
    error = None
    if not form["name"]:
        error = "A user needs a name."
    elif "@" not in form["email"] or " " in form["email"]:
        error = "Enter a valid email address."
    elif not password.strip():
        error = "A user needs a password."
    elif role not in users.ROLES:
        error = BAD_ROLE
    if error:
        return _screen(request, conn, user, form, 422, error)
    try:
        users.create_user(conn, email=form["email"], name=form["name"],
                          password=password, role=role)
    except sqlite3.IntegrityError:
        return _screen(request, conn, user, form, 409,
                       f"The email {form['email']} already belongs to a user.")
    flash(request, f"User {form['name']} created.")
    return _back()


@router.post("/{user_id}/role", dependencies=csrf_required)
def change_role(request: Request, user_id: int, role: str = Form(""),
                user=Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    target = _user_or_404(conn, user_id)
    if role not in users.ROLES:
        return _screen(request, conn, user, status_code=422,
                       error=BAD_ROLE)
    if target["id"] == user["id"] and role != "admin":
        return _screen(request, conn, user, status_code=409, error=SELF_DEMOTE)
    users.set_role(conn, user_id, role)
    flash(request, f"{target['name']} is now {role}.")
    return _back()


@router.post("/{user_id}/deactivate", dependencies=csrf_required)
def deactivate(request: Request, user_id: int, user=Depends(require_admin),
               conn: sqlite3.Connection = Depends(get_db)):
    target = _user_or_404(conn, user_id)
    if target["id"] == user["id"]:
        return _screen(request, conn, user, status_code=409, error=SELF_DEACTIVATE)
    users.set_active(conn, user_id, False)
    flash(request, f"{target['name']} is deactivated and can no longer log in.")
    return _back()


@router.post("/{user_id}/reactivate", dependencies=csrf_required)
def reactivate(request: Request, user_id: int, user=Depends(require_admin),
               conn: sqlite3.Connection = Depends(get_db)):
    target = _user_or_404(conn, user_id)
    users.set_active(conn, user_id, True)
    flash(request, f"{target['name']} is active again.")
    return _back()

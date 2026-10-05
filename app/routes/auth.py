"""Login and logout."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app import users
from app.web import get_db, render, verify_csrf

router = APIRouter()

INVALID = "That email and password do not match. Please try again."
INACTIVE = "This account has been deactivated. Ask the Head Coach to reactivate it."


@router.get("/login")
def login_form(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/admin", status_code=303)
    return render(request, "admin/login.html", {"title": "Sign in"})


@router.post("/login", dependencies=[Depends(verify_csrf)])
def login(request: Request, email: str = Form(""), password: str = Form(""),
          conn: sqlite3.Connection = Depends(get_db)):
    user, reason = users.authenticate(conn, email, password)
    if user is None:
        message = INACTIVE if reason == "inactive" else INVALID
        return render(request, "admin/login.html",
                      {"title": "Sign in", "error": message, "email": email},
                      status_code=401)
    # A fresh session on login (new CSRF token too) prevents session fixation.
    request.session.clear()
    request.session["user_id"] = user["id"]
    request.session["role"] = user["role"]
    return RedirectResponse("/admin", status_code=303)


@router.post("/logout", dependencies=[Depends(verify_csrf)])
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)

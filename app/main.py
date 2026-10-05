"""The FastAPI application.

The admin console answers under /admin (behind login) and the public site
preview answers at /. Routes live in their own modules under app/routes and are
included here. Keep this file small.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from app import db, settings
from app.routes import auth
from app.web import LoginRequired, current_user, render, templates


def create_app(database_path: Path | str | None = None) -> FastAPI:
    app = FastAPI(title="IPHS 400 MP2 CMS")
    app.state.database_path = database_path or settings.DATABASE_PATH
    db.init_db(app.state.database_path)

    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY,
                       session_cookie="cms_session", same_site="lax",
                       https_only=False, max_age=60 * 60 * 12)

    @app.exception_handler(LoginRequired)
    def _login_required(request: Request, exc: LoginRequired):
        return RedirectResponse("/login", status_code=303)

    app.include_router(auth.router)

    @app.get("/admin")
    def admin_home(request: Request, user=Depends(current_user)):
        return render(request, "admin/hello.html", {"title": "Admin"}, user=user)

    @app.get("/")
    def public_home(request: Request):
        return templates.TemplateResponse(
            request, "public/home.html",
            {"title": settings.SITE_TITLE, "items": []},
        )

    return app


app = create_app()

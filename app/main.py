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

from app import db, settings, users
from app.routes import auth, content, listings, pages, posts, users as users_routes
from app.web import LoginRequired, Refused, current_user, render, templates


def _refusal(request: Request, user=None, message: str = Refused().message):
    return render(request, "admin/refused.html", {"title": "Not allowed", "message": message},
                  status_code=403, user=user or _session_user(request))


def _session_user(request: Request):
    conn = db.connect(request.app.state.database_path)
    try:
        user_id = request.session.get("user_id")
        return users.get_by_id(conn, user_id) if user_id else None
    finally:
        conn.close()


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

    @app.exception_handler(Refused)
    def _refused(request: Request, exc: Refused):
        return _refusal(request, message=exc.message)

    app.include_router(auth.router)
    app.include_router(pages.router)
    app.include_router(posts.router)
    app.include_router(content.router)
    app.include_router(listings.router)
    app.include_router(users_routes.router)

    @app.get("/admin")
    def admin_home(request: Request, user=Depends(current_user)):
        return render(request, "admin/hello.html", {"title": "Admin"}, user=user)

    @app.get("/admin/refused")
    def refused_page(request: Request, user=Depends(current_user)):
        return _refusal(request, user)

    @app.get("/")
    def public_home(request: Request):
        return templates.TemplateResponse(
            request, "public/home.html",
            {"title": settings.SITE_TITLE, "items": []},
        )

    return app


app = create_app()

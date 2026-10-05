"""Admin: write, preview and manage posts (Events and Team Updates)."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app import posts
from app.markdown import render_markdown
from app.web import current_user, flash, get_db, render, verify_csrf

# Every route here needs a signed-in user; every POST also needs a CSRF token.
router = APIRouter(prefix="/admin/posts", dependencies=[Depends(current_user)])
csrf_required = [Depends(verify_csrf)]


def _post_or_404(conn: sqlite3.Connection, post_id: int) -> sqlite3.Row:
    post = posts.get(conn, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="No such post.")
    return post


def _back_to_editor(post_id: int) -> RedirectResponse:
    return RedirectResponse(f"/admin/posts/{post_id}/edit", status_code=303)


def _editor(request: Request, user, form: dict, post: sqlite3.Row | None = None,
            status_code: int = 200, preview: str | None = None, error: str | None = None):
    if error:
        flash(request, error, "error")
    return render(request, "admin/post_edit.html",
                  {"title": "Edit post" if post else "New post", "form": form,
                   "post": post, "preview": preview, "post_types": posts.POST_TYPES},
                  status_code=status_code, user=user)


def _slug_taken(fields: dict) -> str:
    return f"The slug “{fields['slug']}” is already used by another post."


def _clean(title: str, slug: str, body: str, status: str,
           post_type: str) -> tuple[dict, str | None]:
    """Normalise the submitted fields; return (fields, error)."""
    title = title.strip()
    fields = {"title": title, "slug": posts.slugify(slug or title), "body": body,
              "status": status if status in posts.STATUSES else "draft",
              "post_type": post_type}
    if not title:
        return fields, "A post needs a title."
    if post_type not in posts.POST_TYPES:
        return fields, "Choose a Post Type: Event or Team Update."
    if not fields["slug"]:
        return fields, "The slug needs at least one letter or number."
    return fields, None


@router.get("/new")
def new_post(request: Request, user=Depends(current_user)):
    return _editor(request, user, {"title": "", "slug": "", "body": "", "status": "draft",
                                   "post_type": posts.DEFAULT_TYPE})


@router.post("/preview", dependencies=csrf_required)
def preview(request: Request, title: str = Form(""), slug: str = Form(""),
            body: str = Form(""), status: str = Form("draft"),
            post_type: str = Form(""), post_id: str = Form(""),
            user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    post = posts.get(conn, int(post_id)) if post_id.isdigit() else None
    form = {"title": title, "slug": slug, "body": body, "status": status,
            "post_type": post_type or posts.DEFAULT_TYPE}
    return _editor(request, user, form, post, preview=render_markdown(body))


@router.post("", dependencies=csrf_required)
def create_post(request: Request, title: str = Form(""), slug: str = Form(""),
                body: str = Form(""), status: str = Form("draft"),
                post_type: str = Form(""),
                user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    fields, error = _clean(title, slug, body, status, post_type)
    if error:
        return _editor(request, user, fields, status_code=422, error=error)
    try:
        post_id = posts.create(conn, author_id=user["id"], **fields)
    except posts.SlugTaken:
        return _editor(request, user, fields, status_code=409, error=_slug_taken(fields))
    flash(request, f"Post “{fields['title']}” saved.")
    return _back_to_editor(post_id)


@router.get("/{post_id}/edit")
def edit_post(post_id: int, request: Request, user=Depends(current_user),
              conn: sqlite3.Connection = Depends(get_db)):
    post = _post_or_404(conn, post_id)
    return _editor(request, user, dict(post), post)


@router.post("/{post_id}", dependencies=csrf_required)
def save_post(post_id: int, request: Request, title: str = Form(""),
              slug: str = Form(""), body: str = Form(""), status: str = Form("draft"),
              post_type: str = Form(""),
              user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    post = _post_or_404(conn, post_id)
    fields, error = _clean(title, slug, body, status, post_type)
    if error:
        return _editor(request, user, fields, post, status_code=422, error=error)
    try:
        posts.update(conn, post_id, **fields)
    except posts.SlugTaken:
        return _editor(request, user, fields, post, status_code=409,
                       error=_slug_taken(fields))
    flash(request, f"Post “{fields['title']}” saved.")
    return _back_to_editor(post_id)


@router.post("/{post_id}/publish", dependencies=csrf_required)
def publish_post(post_id: int, request: Request, conn: sqlite3.Connection = Depends(get_db)):
    post = _post_or_404(conn, post_id)
    posts.set_status(conn, post_id, "published")
    flash(request, f"Post “{post['title']}” published.")
    return RedirectResponse("/admin/content", status_code=303)


@router.post("/{post_id}/unpublish", dependencies=csrf_required)
def unpublish_post(post_id: int, request: Request, conn: sqlite3.Connection = Depends(get_db)):
    post = _post_or_404(conn, post_id)
    posts.set_status(conn, post_id, "draft")
    flash(request, f"Post “{post['title']}” unpublished.")
    return RedirectResponse("/admin/content", status_code=303)


@router.post("/{post_id}/delete", dependencies=csrf_required)
def delete_post(post_id: int, request: Request, conn: sqlite3.Connection = Depends(get_db)):
    post = _post_or_404(conn, post_id)
    posts.delete(conn, post_id)
    flash(request, f"Post “{post['title']}” deleted.")
    return RedirectResponse("/admin/content", status_code=303)

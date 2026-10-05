"""Admin: write, preview and manage pages."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app import pages
from app.markdown import render_markdown
from app.web import current_user, flash, get_db, render, verify_csrf

# Every route here needs a signed-in user; every POST also needs a CSRF token.
router = APIRouter(prefix="/admin/pages", dependencies=[Depends(current_user)])
csrf_required = [Depends(verify_csrf)]


def _page_or_404(conn: sqlite3.Connection, page_id: int) -> sqlite3.Row:
    page = pages.get(conn, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="No such page.")
    return page


def _back_to_editor(page_id: int) -> RedirectResponse:
    return RedirectResponse(f"/admin/pages/{page_id}/edit", status_code=303)


def _editor(request: Request, user, form: dict, page: sqlite3.Row | None = None,
            status_code: int = 200, preview: str | None = None, error: str | None = None):
    if error:
        flash(request, error, "error")
    return render(request, "admin/page_edit.html",
                  {"title": "Edit page" if page else "New page", "form": form,
                   "page": page, "preview": preview}, status_code=status_code, user=user)


def _slug_taken(fields: dict) -> str:
    return f"The slug “{fields['slug']}” is already used by another page."


def _clean(title: str, slug: str, body: str, status: str) -> tuple[dict, str | None]:
    """Normalise the submitted fields; return (fields, error)."""
    title = title.strip()
    fields = {"title": title, "slug": pages.slugify(slug or title), "body": body,
              "status": status if status in pages.STATUSES else "draft"}
    if not title:
        return fields, "A page needs a title."
    if not fields["slug"]:
        return fields, "The slug needs at least one letter or number."
    return fields, None


@router.get("")
def page_list(request: Request, user=Depends(current_user),
              conn: sqlite3.Connection = Depends(get_db)):
    return render(request, "admin/page_list.html",
                  {"title": "Pages", "pages": pages.list_pages(conn)}, user=user)


@router.get("/new")
def new_page(request: Request, user=Depends(current_user)):
    return _editor(request, user, {"title": "", "slug": "", "body": "", "status": "draft"})


@router.post("/preview", dependencies=csrf_required)
def preview(request: Request, title: str = Form(""), slug: str = Form(""),
            body: str = Form(""), status: str = Form("draft"), page_id: str = Form(""),
            user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    page = pages.get(conn, int(page_id)) if page_id.isdigit() else None
    form = {"title": title, "slug": slug, "body": body, "status": status}
    return _editor(request, user, form, page, preview=render_markdown(body))


@router.post("", dependencies=csrf_required)
def create_page(request: Request, title: str = Form(""), slug: str = Form(""),
                body: str = Form(""), status: str = Form("draft"),
                user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    fields, error = _clean(title, slug, body, status)
    if error:
        return _editor(request, user, fields, status_code=422, error=error)
    try:
        page_id = pages.create(conn, author_id=user["id"], **fields)
    except pages.SlugTaken:
        return _editor(request, user, fields, status_code=409,
                       error=_slug_taken(fields))
    flash(request, f"Page “{fields['title']}” saved.")
    return _back_to_editor(page_id)


@router.get("/{page_id}/edit")
def edit_page(page_id: int, request: Request, user=Depends(current_user),
              conn: sqlite3.Connection = Depends(get_db)):
    page = _page_or_404(conn, page_id)
    return _editor(request, user, dict(page), page)


@router.post("/{page_id}", dependencies=csrf_required)
def save_page(page_id: int, request: Request, title: str = Form(""),
              slug: str = Form(""), body: str = Form(""), status: str = Form("draft"),
              user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    page = _page_or_404(conn, page_id)
    fields, error = _clean(title, slug, body, status)
    if error:
        return _editor(request, user, fields, page, status_code=422, error=error)
    try:
        pages.update(conn, page_id, **fields)
    except pages.SlugTaken:
        return _editor(request, user, fields, page, status_code=409,
                       error=_slug_taken(fields))
    flash(request, f"Page “{fields['title']}” saved.")
    return _back_to_editor(page_id)


@router.post("/{page_id}/publish", dependencies=csrf_required)
def publish_page(page_id: int, request: Request, conn: sqlite3.Connection = Depends(get_db)):
    page = _page_or_404(conn, page_id)
    pages.set_status(conn, page_id, "published")
    flash(request, f"Page “{page['title']}” published.")
    return RedirectResponse("/admin/pages", status_code=303)


@router.post("/{page_id}/unpublish", dependencies=csrf_required)
def unpublish_page(page_id: int, request: Request, conn: sqlite3.Connection = Depends(get_db)):
    page = _page_or_404(conn, page_id)
    pages.set_status(conn, page_id, "draft")
    flash(request, f"Page “{page['title']}” unpublished.")
    return RedirectResponse("/admin/pages", status_code=303)


@router.post("/{page_id}/delete", dependencies=csrf_required)
def delete_page(page_id: int, request: Request, conn: sqlite3.Connection = Depends(get_db)):
    page = _page_or_404(conn, page_id)
    pages.delete(conn, page_id)
    flash(request, f"Page “{page['title']}” deleted.")
    return RedirectResponse("/admin/pages", status_code=303)

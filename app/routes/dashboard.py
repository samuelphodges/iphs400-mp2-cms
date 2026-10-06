"""Admin: the dashboard, a count of what is on the site."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request

from app import listings, pages, posts
from app.web import current_user, get_db, render

router = APIRouter()


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    all_pages, all_posts = pages.list_pages(conn), posts.list_posts(conn)
    drafts = [i for i in (*all_pages, *all_posts) if i["status"] == "draft"]
    return {"posts": len(all_posts), "pages": len(all_pages), "drafts": len(drafts),
            "listings": len(listings.list_listings(conn))}


@router.get("/admin")
def dashboard(request: Request, user=Depends(current_user),
              conn: sqlite3.Connection = Depends(get_db)):
    return render(request, "admin/dashboard.html",
                  {"title": "Dashboard", "counts": counts(conn)}, user=user)

"""Admin: one list of pages and posts together, filtered by status and type."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request

from app import pages, posts
from app.web import current_user, get_db, render

router = APIRouter(prefix="/admin/content", dependencies=[Depends(current_user)])

# The "type" filter: Page, or one of the Post Types.
TYPES = {"page": "Page", **posts.POST_TYPES}


def _items(conn: sqlite3.Connection, status: str, type_: str) -> list[dict]:
    items = [{"kind": "page", "type": "page", "type_label": "Page", **dict(p)}
             for p in pages.list_pages(conn)]
    items += [{"kind": "post", "type": p["post_type"],
               "type_label": posts.POST_TYPES[p["post_type"]], **dict(p)}
              for p in posts.list_posts(conn)]
    items = [i for i in items
             if (not status or i["status"] == status) and (not type_ or i["type"] == type_)]
    return sorted(items, key=lambda i: (i["updated_at"], i["id"]), reverse=True)


@router.get("")
def content_list(request: Request, status: str = "", type: str = "",
                 user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    status = status if status in pages.STATUSES else ""
    type_ = type if type in TYPES else ""
    return render(request, "admin/content_list.html",
                  {"title": "Content", "items": _items(conn, status, type_),
                   "status": status, "type": type_, "statuses": pages.STATUSES,
                   "types": TYPES}, user=user)

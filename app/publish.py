"""Render the public site into site/ as plain HTML.

T00 publishes a placeholder home page. As you build content types, extend
render_site() to write one file per published item. Two rules the rubric checks:

  1. Only PUBLISHED content is written here. A draft that reaches site/ is a bug.
  2. Every href and src is RELATIVE ("style.css", "posts/x.html"), never
     root-absolute ("/style.css"), because Pages serves this from a subfolder.
"""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app import db, pages, settings
from app.markdown import render_markdown

HOME_SLUG = "home"

CSS = """/* Minimal starter styles — make them yours. */
:root { color-scheme: light dark; }
body { font: 16px/1.6 system-ui, sans-serif; margin: 0 auto; max-width: 42rem; padding: 1rem; }
header a { font-weight: 700; text-decoration: none; }
nav ul { list-style: none; margin: .5rem 0 0; padding: 0; display: flex; flex-wrap: wrap; gap: .25rem 1rem; }
main { margin-block: 2rem; }
"""


def environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(settings.TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )


def _filename(slug: str) -> str:
    if slug == HOME_SLUG:
        return "index.html"
    # "index" would overwrite the Home page.
    return "index-page.html" if slug == "index" else f"{slug}.html"


def _navigation(published: list[sqlite3.Row]) -> list[dict[str, str]]:
    """Home first, then the other published pages alphabetically by title."""
    ordered = sorted(published, key=lambda p: (p["slug"] != HOME_SLUG, p["title"].lower()))
    return [{"title": p["title"], "href": _filename(p["slug"])} for p in ordered]


def render_site(out: Path | None = None,
                database_path: Path | str | None = None) -> Path:
    out = out or settings.SITE
    database_path = database_path or settings.DATABASE_PATH
    db.init_db(database_path)
    conn = db.connect(database_path)
    try:
        published = pages.list_published(conn)
    finally:
        conn.close()

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    env = environment()
    nav = _navigation(published)
    (out / "style.css").write_text(CSS)
    link_targets = {"index.html", "style.css"} | {n["href"] for n in nav}

    for page in published:
        (out / _filename(page["slug"])).write_text(
            env.get_template("public/page.html").render(
                title=page["title"], site_title=settings.SITE_TITLE, nav=nav,
                body=render_markdown(page["body"], link_targets=link_targets),
                css_path="style.css", home_path="index.html"))

    if not any(p["slug"] == HOME_SLUG for p in published):
        (out / "index.html").write_text(
            env.get_template("public/home.html").render(
                title=settings.SITE_TITLE, site_title=settings.SITE_TITLE, items=[],
                nav=nav, css_path="style.css", home_path="index.html"))
    return out

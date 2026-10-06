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
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app import db, listings, pages, posts, settings
from app.markdown import render_markdown

HOME_SLUG = "home"
EVENTS_SLUG = "alumni-events"
NETWORK_SLUG = "alumni-network"
SECTION_SLUGS = ("team-schedule", EVENTS_SLUG, NETWORK_SLUG)
HOME_COUNT = 3  # Team Updates and Events shown on Home

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


def _post_filenames(published: list[sqlite3.Row], taken: set[str]) -> dict[int, str]:
    """One file per post. A page's file always wins a clash; the post is renamed."""
    names: dict[int, str] = {}
    for post in published:
        name = f"post-{post['slug']}.html"
        while name in taken:
            name = name.removesuffix(".html") + "-post.html"
        taken.add(name)
        names[post["id"]] = name
    return names


def _summary(post: sqlite3.Row, names: dict[int, str]) -> dict[str, str]:
    return {"title": post["title"], "href": names[post["id"]], "date": post["created_at"][:10]}


def render_site(out: Path | None = None,
                database_path: Path | str | None = None) -> Path:
    out = out or settings.SITE
    database_path = database_path or settings.DATABASE_PATH
    db.init_db(database_path)
    conn = db.connect(database_path)
    try:
        published = pages.list_published(conn)
        published_posts = posts.list_published(conn)  # newest first
        alumni_names = listings.consented_names(conn)  # names only (ADR-003)
    finally:
        conn.close()

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    env = environment()
    nav = _navigation(published)
    (out / "style.css").write_text(CSS)
    page_files = {_filename(p["slug"]) for p in published} | {"index.html", "style.css"}
    post_files = _post_filenames(published_posts, set(page_files))
    link_targets = page_files | set(post_files.values())
    by_slug = {p["slug"]: p for p in published}

    events = [_summary(p, post_files) for p in published_posts if p["post_type"] == "event"]
    updates = [_summary(p, post_files) for p in published_posts
               if p["post_type"] == "team_update"]
    home_sections = {
        "updates": updates[:HOME_COUNT], "events": events[:HOME_COUNT],
        "section_links": [{"title": by_slug[s]["title"], "href": _filename(s)}
                          for s in SECTION_SLUGS if s in by_slug]}
    sections_for: dict[str, dict[str, Any]] = {HOME_SLUG: home_sections, EVENTS_SLUG: {"events": events},
                    NETWORK_SLUG: {"alumni": alumni_names,
                                   "contact_email": settings.CONTACT_EMAIL}}

    common = dict(site_title=settings.SITE_TITLE, nav=nav, css_path="style.css",
                  home_path="index.html")
    for page in published:
        (out / _filename(page["slug"])).write_text(
            env.get_template("public/page.html").render(
                title=page["title"],
                body=render_markdown(page["body"], link_targets=link_targets),
                **sections_for.get(page["slug"], {}), **common))

    if HOME_SLUG not in by_slug:
        (out / "index.html").write_text(
            env.get_template("public/home.html").render(
                title=settings.SITE_TITLE, **home_sections, **common))

    for post in published_posts:
        (out / post_files[post["id"]]).write_text(
            env.get_template("public/post.html").render(
                title=post["title"], type_label=posts.POST_TYPES[post["post_type"]],
                date=post["created_at"][:10],
                body=render_markdown(post["body"], link_targets=link_targets), **common))
    return out

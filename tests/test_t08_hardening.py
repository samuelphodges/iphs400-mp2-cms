"""T08: dashboard, hardening and demo data. Each test names the criterion it covers."""
import re
import runpy
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urlparse

from fastapi.testclient import TestClient

from app import db, listings, pages, posts, settings
from app.main import create_app
from app.publish import render_site


def _count(html: str, label: str) -> int:
    match = re.search(rf'data-count="{label}">(\d+)<', html)
    assert match, f"dashboard has no {label} count"
    return int(match.group(1))


def _add_post(database_path, title, status="published", post_type="event"):
    conn = db.connect(database_path)
    try:
        posts.create(conn, title=title, slug=posts.slugify(title), body="Body",
                     status=status, post_type=post_type, author_id=1)
    finally:
        conn.close()


def test_dashboard_shows_counts_that_change_with_content(client_as, database_path):
    """Counts of posts, pages, drafts and listings, and they change with content."""
    c = client_as("admin")
    before = c.get("/admin").text
    assert [_count(before, k) for k in ("posts", "pages", "drafts", "listings")] == [0, 0, 0, 0]

    _add_post(database_path, "Reunion")
    _add_post(database_path, "Banquet", status="draft")
    conn = db.connect(database_path)
    pages.create(conn, title="About", slug="about", body="x", status="draft", author_id=1)
    listings.create(conn, name="Sam", email="s@example.test", class_year=None,
                    consent_date="2026-09-01", recorded_by=1)
    conn.close()

    after = c.get("/admin").text
    assert _count(after, "posts") == 2
    assert _count(after, "pages") == 1
    assert _count(after, "drafts") == 2  # one draft post and one draft page
    assert _count(after, "listings") == 1


def test_admin_navigation_links_and_hides_users_from_editors(client_as):
    """Persistent navigation: Dashboard, Content, Listings, Users (admin only)."""
    admin = client_as("admin").get("/admin/listings").text
    for href in ("/admin", "/admin/content", "/admin/listings", "/admin/users"):
        assert f'href="{href}"' in admin
    assert ">Dashboard</a>" in admin
    editor = client_as("editor").get("/admin/content").text
    for href in ("/admin", "/admin/content", "/admin/listings"):
        assert f'href="{href}"' in editor
    assert 'href="/admin/users"' not in editor


def _post_routes(app):
    """Every POST path, read from the app's own OpenAPI schema so new routes are covered."""
    return [path for path, ops in app.openapi()["paths"].items() if "post" in ops]


def _fill(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "1", path)


def test_every_post_route_rejects_a_missing_csrf_token(database_path, client_as):
    """Replay every state-changing POST without a token; each is rejected."""
    app = create_app(database_path)
    routes = _post_routes(app)
    assert len(routes) >= 20, "route enumeration found too few POST routes"
    for role in ("admin", "editor"):
        c = client_as(role)
        for route in routes:
            response = c.post(_fill(route), data={}, follow_redirects=False)
            assert response.status_code == 403, f"{role} POST {route} -> {response.status_code}"
    anonymous = TestClient(app)
    for route in routes:
        response = anonymous.post(_fill(route), data={}, follow_redirects=False)
        # Admin routes send an anonymous visitor to login first; the two public
        # forms must reject on the CSRF token itself.
        expected = 403 if route in ("/login", "/logout") else 303
        assert response.status_code == expected, f"anon POST {route}"


def test_every_post_route_rejects_a_wrong_csrf_token(client_as, database_path):
    """A token that is present but wrong is rejected too."""
    c = client_as("admin")
    for route in _post_routes(create_app(database_path)):
        response = c.post(_fill(route), data={"csrf_token": "forged"},
                          follow_redirects=False)
        assert response.status_code == 403, route


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in ("href", "src") and value is not None:
                self.refs.append((name, value))


def _seeded_site(database_path, tmp_path):
    conn = db.connect(database_path)
    for title, locked in (("Home", False), ("Team Schedule", True), ("Alumni Events", False),
                          ("Alumni Network", False), ("About", False)):
        page_id = pages.create(conn, title=title, slug=pages.slugify(title),
                               body="See [the schedule](team-schedule.html).",
                               status="published", author_id=1)
        pages.set_locked(conn, page_id, locked)
    listings.create(conn, name="Sam Rivera", email="sam@alumni.example.test",
                    class_year=2008, consent_date="2026-09-01", recorded_by=1)
    conn.close()
    for i in range(4):
        _add_post(database_path, f"Event {i}")
        _add_post(database_path, f"Update {i}", post_type="team_update")
    return render_site(tmp_path / "site", database_path=database_path)


def test_exported_site_has_no_absolute_paths_and_every_link_resolves(database_path, tmp_path):
    """Crawl site/: no href="/ or src="/, and every internal link resolves."""
    out = _seeded_site(database_path, tmp_path)
    files = sorted(out.rglob("*.html"))
    assert len(files) >= 13
    for html_file in files:
        text = html_file.read_text()
        assert 'href="/' not in text and 'src="/' not in text, html_file.name
        parser = _Links()
        parser.feed(text)
        assert parser.refs, html_file.name
        for _, ref in parser.refs:
            parsed = urlparse(ref)
            if parsed.scheme or ref.startswith("#"):
                continue  # external, mailto: or same-page anchor
            target = (html_file.parent / urldefrag(parsed.path)[0]).resolve()
            assert target.is_file(), f"{html_file.name}: broken link {ref}"
    assert "sam@alumni.example.test" not in "".join(p.read_text() for p in files)


def test_seed_script_runs_clean_from_env_example_values(monkeypatch, tmp_path):
    """The seed script needs nothing but .env.example values and creates the demo."""
    env = dict(line.split("=", 1) for line in Path(".env.example").read_text().splitlines()
               if line and not line.startswith("#"))
    db_path = tmp_path / "seed.db"
    monkeypatch.setattr(settings, "DATABASE_PATH", db_path)
    monkeypatch.setenv("CMS_ADMIN_PASSWORD", env["CMS_ADMIN_PASSWORD"])
    monkeypatch.setenv("CMS_EDITOR_PASSWORD", env["CMS_EDITOR_PASSWORD"])
    seed = runpy.run_path("scripts/seed_demo.py")
    assert seed["main"]() == 0
    assert seed["main"]() == 0  # idempotent: a second run is also clean

    conn = db.connect(db_path)
    try:
        roles = {r["email"]: r["role"] for r in conn.execute("SELECT email, role FROM users")}
        assert roles == {"admin@example.test": "admin", "editor@example.test": "editor"}
        slugs = {p["slug"]: p["locked"] for p in pages.list_pages(conn)}
        assert set(slugs) == {"home", "team-schedule", "alumni-events",
                              "alumni-network", "about"}
        assert [s for s, locked in slugs.items() if locked] == ["team-schedule"]
        types = {p["post_type"] for p in posts.list_posts(conn)}
        assert types == {"event", "team_update"}
        assert listings.list_listings(conn)
    finally:
        conn.close()
    # ...and the seeded site really does export.
    out = render_site(tmp_path / "site", database_path=db_path)
    assert (out / "index.html").exists()


def test_public_and_admin_css_guard_against_horizontal_overflow_at_390px():
    """No browser is available in the test run, so assert the CSS rules that stop overflow.

    Public pages and the admin layout both set the viewport meta, wrap long words,
    and scroll wide tables, code and images inside their own box.
    """
    from app.publish import CSS

    admin = Path("templates/admin/layout.html").read_text()
    for css in (CSS, admin):
        assert "overflow-wrap" in css
    assert "max-width: 100%" in CSS
    assert "overflow-x: auto" in CSS and "overflow-x: auto" in admin
    for tpl in ("templates/base.html", "templates/admin/layout.html"):
        assert 'name="viewport" content="width=device-width, initial-scale=1"' in Path(tpl).read_text()

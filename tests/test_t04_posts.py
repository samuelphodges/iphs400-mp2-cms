"""T04: Events and Team Updates. Each test names the criterion it covers."""
import re

import pytest
from fastapi.testclient import TestClient

from app import db, pages
from app.main import create_app
from app.publish import render_site
from tests.conftest import _csrf_from


def _token(c) -> str:
    return _csrf_from(c.get("/admin/posts/new"))


def _create(c, title="Reunion", body="Body", status="draft", post_type="event",
            slug="", csrf=True):
    data = {"title": title, "slug": slug, "body": body, "status": status}
    if post_type is not None:
        data["post_type"] = post_type
    if csrf:
        data["csrf_token"] = _token(c)
    return c.post("/admin/posts", data=data, follow_redirects=False)


def _post_id(response) -> int:
    match = re.search(r"/admin/posts/(\d+)/edit", response.headers["location"])
    assert match, response.headers
    return int(match.group(1))


@pytest.mark.parametrize("role", ["admin", "editor"])
def test_editor_can_create_post_with_generated_slug(client_as, role):
    """Create a post with a generated slug, author and timestamps; success message."""
    c = client_as(role)
    response = _create(c, title="Spring Reunion & BBQ!")
    assert response.status_code == 303
    edit = c.get(response.headers["location"])
    assert 'value="spring-reunion-bbq"' in edit.text
    assert "saved" in edit.text.lower()
    assert "Created" in edit.text and "Updated" in edit.text and "Author" in edit.text


def test_slug_is_editable_and_unique(client_as):
    c = client_as("editor")
    response = _create(c, title="A", slug="Custom Slug")
    assert 'value="custom-slug"' in c.get(response.headers["location"]).text
    again = _create(c, title="B", slug="custom-slug")
    assert again.status_code == 409
    assert "already used" in again.text


def test_post_type_is_required_and_must_be_valid(client_as):
    """Post Type is required, and is Event or Team Update."""
    c = client_as("editor")
    assert _create(c, post_type=None).status_code == 422
    assert _create(c, post_type="").status_code == 422
    assert _create(c, post_type="news").status_code == 422
    assert _create(c, post_type="team_update").status_code == 303


def test_new_post_form_defaults_to_event(client_as):
    """A new post by an editor defaults to Event."""
    html = client_as("editor").get("/admin/posts/new").text
    assert re.search(r'<option value="event"\s+selected', html)


def test_edit_changes_type_and_body(client_as):
    c = client_as("editor")
    post_id = _post_id(_create(c))
    c.post(f"/admin/posts/{post_id}",
           data={"title": "New title", "slug": "", "body": "Changed",
                 "status": "draft", "post_type": "team_update",
                 "csrf_token": _token(c)})
    html = c.get(f"/admin/posts/{post_id}/edit").text
    assert "New title" in html and "Changed" in html
    assert re.search(r'<option value="team_update"\s+selected', html)


def test_publish_unpublish_delete(client_as):
    c = client_as("editor")
    post_id = _post_id(_create(c))
    c.post(f"/admin/posts/{post_id}/publish", data={"csrf_token": _token(c)})
    assert "published" in c.get("/admin/content").text
    c.post(f"/admin/posts/{post_id}/unpublish", data={"csrf_token": _token(c)})
    assert c.get("/admin/content?status=published").text.count("Reunion") == 0
    c.post(f"/admin/posts/{post_id}/delete", data={"csrf_token": _token(c)})
    assert c.get(f"/admin/posts/{post_id}/edit").status_code == 404


def test_posts_persist_across_restart(client_as, database_path):
    """A fresh app on the same database file still has the post."""
    c = client_as("editor")
    post_id = _post_id(_create(c, title="Survives restart"))
    fresh = TestClient(create_app(database_path))
    token = _csrf_from(fresh.get("/login"))
    fresh.post("/login", data={"email": "editor@example.test",
                               "password": "test-editor-pw", "csrf_token": token})
    assert "Survives restart" in fresh.get(f"/admin/posts/{post_id}/edit").text


def test_preview_is_sanitized(client_as):
    """The post editor shows a sanitized Markdown preview."""
    c = client_as("editor")
    response = c.post("/admin/posts/preview", data={
        "title": "T", "slug": "", "post_type": "event", "status": "draft",
        "body": '**bold** <script>alert(1)</script><img src=x onerror="alert(2)">',
        "csrf_token": _token(c)})
    assert response.status_code == 200
    preview = re.search(r'<div id="preview">(.*?)</div>', response.text, re.S).group(1)
    assert "<strong>bold</strong>" in preview
    assert "<script" not in preview and "onerror" not in preview


def test_content_list_shows_pages_and_posts_with_filters(client_as, database_path):
    """The content list filters by status and type and shows posts and pages together."""
    c = client_as("editor")
    conn = db.connect(database_path)
    pages.create(conn, title="About Page", slug="about", body="", status="published", author_id=1)
    conn.close()
    _create(c, title="Event Draft", post_type="event", status="draft")
    _create(c, title="Event Live", post_type="event", status="published")
    _create(c, title="Update Live", post_type="team_update", status="published")

    everything = c.get("/admin/content").text
    for title in ("About Page", "Event Draft", "Event Live", "Update Live"):
        assert title in everything

    live = c.get("/admin/content?status=published").text
    assert "Event Live" in live and "About Page" in live and "Event Draft" not in live

    events = c.get("/admin/content?type=event").text
    assert "Event Draft" in events and "Event Live" in events
    assert "Update Live" not in events and "About Page" not in events

    updates = c.get("/admin/content?type=team_update&status=published").text
    assert "Update Live" in updates and "Event Live" not in updates

    assert "About Page" in c.get("/admin/content?type=page").text
    assert "Event Live" not in c.get("/admin/content?type=page").text


def test_every_post_form_requires_csrf(client_as):
    """Each state-changing post route rejects a POST without a token."""
    c = client_as("editor")
    post_id = _post_id(_create(c))
    assert _create(c, csrf=False).status_code == 403
    for path in ("", f"/{post_id}", f"/{post_id}/publish",
                 f"/{post_id}/unpublish", f"/{post_id}/delete", "/preview"):
        data = {"title": "x", "post_type": "event", "body": "", "status": "draft"}
        assert c.post(f"/admin/posts{path}", data=data).status_code == 403, path
    assert c.get(f"/admin/posts/{post_id}/edit").status_code == 200


def test_post_forms_carry_a_token(client_as):
    c = client_as("editor")
    post_id = _post_id(_create(c))
    assert 'name="csrf_token"' in c.get("/admin/posts/new").text
    assert 'name="csrf_token"' in c.get(f"/admin/posts/{post_id}/edit").text
    assert 'name="csrf_token"' in c.get("/admin/content").text


def test_anonymous_visitor_is_sent_to_login(client):
    for path in ("/admin/posts/new", "/admin/content"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303 and response.headers["location"] == "/login"


# --- publish seam -------------------------------------------------------------

@pytest.fixture
def add_page(database_path):
    def _add(title, body="Body", status="published", slug=None):
        conn = db.connect(database_path)
        try:
            return pages.create(conn, title=title, slug=slug or pages.slugify(title),
                                body=body, status=status, author_id=1)
        finally:
            conn.close()
    return _add


@pytest.fixture
def add_post(database_path):
    from app import posts

    def _add(title, post_type="event", body="Body", status="published",
             created_at=None, slug=None):
        conn = db.connect(database_path)
        try:
            post_id = posts.create(conn, title=title, slug=slug or pages.slugify(title),
                                   body=body, status=status, post_type=post_type,
                                   author_id=1)
            if created_at:
                conn.execute("UPDATE posts SET created_at = ? WHERE id = ?",
                             (created_at, post_id))
                conn.commit()
            return post_id
        finally:
            conn.close()
    return _add


def _publish(tmp_path, database_path):
    return render_site(tmp_path / "site", database_path=database_path)


def _links(html):
    return re.findall(r'href="([^"]+)"', html)


def _main(html):
    return re.search(r"<main>(.*?)</main>", html, re.S).group(1)


def test_alumni_events_lists_published_events_newest_first(
        add_page, add_post, database_path, tmp_path):
    """Published Events newest first; drafts and Team Updates are omitted."""
    add_page("Alumni Events", slug="alumni-events", body="Gatherings")
    add_post("Oldest Event", created_at="2026-01-01 10:00:00")
    add_post("Newest Event", created_at="2026-06-01 10:00:00")
    add_post("Middle Event", created_at="2026-03-01 10:00:00")
    add_post("Draft Event", status="draft")
    add_post("Some Update", post_type="team_update")
    out = _publish(tmp_path, database_path)
    html = _main((out / "alumni-events.html").read_text())
    assert "Gatherings" in html
    assert html.index("Newest Event") < html.index("Middle Event") < html.index("Oldest Event")
    assert "Draft Event" not in html and "Some Update" not in html


def test_home_shows_latest_three_updates_and_three_recent_events(
        add_page, add_post, database_path, tmp_path):
    """Home: latest three published Team Updates and three recent Events."""
    add_page("Home", slug="home", body="Welcome fans")
    for i in range(1, 5):
        add_post(f"Update {i}", post_type="team_update", created_at=f"2026-0{i}-01 09:00:00")
        add_post(f"Event {i}", created_at=f"2026-0{i}-01 09:00:00")
    add_post("Update Draft", post_type="team_update", status="draft",
             created_at="2026-09-01 09:00:00")
    out = _publish(tmp_path, database_path)
    html = _main((out / "index.html").read_text())
    assert "Welcome fans" in html
    for shown in ("Update 4", "Update 3", "Update 2", "Event 4", "Event 3", "Event 2"):
        assert shown in html
    for hidden in ("Update 1", "Event 1", "Update Draft"):
        assert hidden not in html


def test_home_links_to_the_three_sections(add_page, database_path, tmp_path):
    add_page("Home", slug="home")
    add_page("Team Schedule")
    add_page("Alumni Events")
    add_page("Alumni Network")
    out = _publish(tmp_path, database_path)
    links = _links(_main((out / "index.html").read_text()))
    for target in ("team-schedule.html", "alumni-events.html", "alumni-network.html"):
        assert target in links


def test_generated_home_without_a_home_page_still_lists_posts(
        add_post, database_path, tmp_path):
    add_post("Lonely Update", post_type="team_update")
    out = _publish(tmp_path, database_path)
    assert "Lonely Update" in (out / "index.html").read_text()


def test_post_pages_are_exported_only_when_published(add_post, database_path, tmp_path):
    add_post("Live Event", body="See you there", slug="live-event")
    add_post("Hidden Event", status="draft", slug="hidden-event")
    out = _publish(tmp_path, database_path)
    live = [p for p in out.glob("*.html") if "See you there" in p.read_text()]
    assert len(live) == 1
    assert not any("Hidden Event" in p.read_text() for p in out.glob("*.html"))


def test_exported_posts_are_sanitized_and_relative(
        add_page, add_post, database_path, tmp_path):
    """Exported post content is sanitized and uses relative paths."""
    add_page("Home", slug="home", body="[x](/root-link)")
    add_page("Alumni Events", slug="alumni-events")
    add_post("Evil", body='Hi <script>alert(1)</script><img src="x" onerror="alert(2)"> '
                          "[bad](/abs) [ext](https://example.org)")
    add_post("Update", post_type="team_update", body="[abs](/abs)")
    out = _publish(tmp_path, database_path)
    files = list(out.glob("*.html"))
    assert files
    for f in files:
        html = f.read_text()
        assert "<script" not in html and "onerror" not in html, f.name
        assert 'href="/' not in html and 'src="/' not in html, f.name
        for link in _links(html):
            if re.match(r"[a-z][a-z0-9+.-]*:", link) or link.startswith("#"):
                continue
            assert (out / link.split("#")[0]).exists(), f"{f.name} -> {link}"


def test_post_slug_cannot_overwrite_a_page_file(add_page, add_post, database_path, tmp_path):
    add_page("About", body="PAGE BODY")
    add_post("About", body="POST BODY", slug="about")
    out = _publish(tmp_path, database_path)
    assert "PAGE BODY" in (out / "about.html").read_text()
    assert any("POST BODY" in p.read_text() for p in out.glob("*.html"))

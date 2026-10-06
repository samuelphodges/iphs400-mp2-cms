"""T02: write, preview and manage pages. Each test names the criterion it covers."""
import re

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import _csrf_from


def _create(c, title="Alumni Events", body="Hello", status="draft", slug="", csrf=True):
    data = {"title": title, "slug": slug, "body": body, "status": status}
    if csrf:
        data["csrf_token"] = _csrf_from(c.get("/admin/pages/new"))
    return c.post("/admin/pages", data=data, follow_redirects=False)


def _page_id(response) -> int:
    match = re.search(r"/admin/pages/(\d+)/edit", response.headers["location"])
    assert match, response.headers
    return int(match.group(1))


def _token(c) -> str:
    return _csrf_from(c.get("/admin/pages/new"))


@pytest.mark.parametrize("role", ["admin", "editor"])
def test_signed_in_user_can_create_page_with_generated_slug(client_as, role):
    """Create a page; slug is generated from the title."""
    c = client_as(role)
    response = _create(c, title="Alumni Events & More!", body="Welcome", status="published")
    assert response.status_code == 303
    edit = c.get(response.headers["location"])
    assert edit.status_code == 200
    assert 'value="alumni-events-more"' in edit.text
    assert "saved" in edit.text.lower()  # success message after the redirect


def test_slug_can_be_set_by_the_editor(client_as):
    """The slug can be changed."""
    c = client_as("editor")
    response = _create(c, title="About us", slug="Who We Are")
    assert 'value="who-we-are"' in c.get(response.headers["location"]).text


def test_two_pages_cannot_share_a_slug(client_as):
    """The second save shows an error."""
    c = client_as("editor")
    assert _create(c, title="About").status_code == 303
    second = _create(c, title="Other", slug="about")
    assert second.status_code == 409
    assert "already" in second.text.lower()
    # An error keeps what the editor typed.
    assert 'value="Other"' in second.text


def test_editing_a_page_may_keep_its_own_slug_but_not_take_another(client_as):
    c = client_as("editor")
    a = _page_id(_create(c, title="Alpha"))
    _create(c, title="Beta")
    token = _token(c)
    same = c.post(f"/admin/pages/{a}", data={"title": "Alpha 2", "slug": "alpha",
                  "body": "x", "status": "draft", "csrf_token": token},
                  follow_redirects=False)
    assert same.status_code == 303
    clash = c.post(f"/admin/pages/{a}", data={"title": "Alpha 2", "slug": "beta",
                   "body": "x", "status": "draft", "csrf_token": token})
    assert clash.status_code == 409


def test_blank_title_is_an_error(client_as):
    c = client_as("editor")
    response = _create(c, title="  ")
    assert response.status_code == 422
    assert "title" in response.text.lower()


def test_edit_publish_unpublish_delete_each_show_a_message(client_as):
    """A page can be edited, published, unpublished and deleted."""
    c = client_as("editor")
    pid = _page_id(_create(c, title="About"))
    token = _token(c)

    edited = c.post(f"/admin/pages/{pid}", data={"title": "About Us", "slug": "about",
                    "body": "New body", "status": "draft", "csrf_token": token})
    assert edited.status_code == 200  # redirect followed back to the editor
    assert "About Us" in edited.text and "saved" in edited.text.lower()

    pub = c.post(f"/admin/pages/{pid}/publish", data={"csrf_token": token})
    assert "published" in pub.text.lower() and "About Us" in pub.text
    assert re.search(r"About Us.*?published", c.get("/admin/pages").text, re.S)

    unpub = c.post(f"/admin/pages/{pid}/unpublish", data={"csrf_token": token})
    assert "unpublished" in unpub.text.lower()

    gone = c.post(f"/admin/pages/{pid}/delete", data={"csrf_token": token})
    assert "deleted" in gone.text.lower()
    assert "<td>" not in gone.text  # the list is empty again
    assert c.get(f"/admin/pages/{pid}/edit").status_code == 404


def test_author_and_timestamps_are_recorded_and_shown(client_as):
    """Author, created and updated timestamps are shown."""
    c = client_as("editor")
    pid = _page_id(_create(c, title="About"))
    edit = c.get(f"/admin/pages/{pid}/edit").text
    assert "Joe" in edit
    assert re.search(r"Created\s*(<[^>]+>\s*)*\d{4}-\d{2}-\d{2}", edit)
    assert re.search(r"Updated\s*(<[^>]+>\s*)*\d{4}-\d{2}-\d{2}", edit)


def test_pages_persist_across_a_restart(client_as, database_path):
    """A fresh app on the same database file still has the page."""
    c = client_as("admin")
    pid = _page_id(_create(c, title="Persistent", body="still here", status="published"))
    fresh = TestClient(create_app(database_path))
    # Log in again on the fresh app (sessions are cookies; the secret is shared).
    fresh.cookies.update(c.cookies)
    page = fresh.get(f"/admin/pages/{pid}/edit")
    assert page.status_code == 200
    assert "Persistent" in page.text and "still here" in page.text


def test_preview_renders_markdown_and_strips_script_and_onerror(client_as):
    """The preview shows sanitized Markdown."""
    c = client_as("editor")
    body = ('# Big heading\n\n<script>alert(1)</script>\n\n'
            '<img src="x" onerror="alert(2)">\n\n[ok](https://example.test)')
    response = c.post("/admin/pages/preview", data={
        "title": "T", "slug": "", "body": body, "status": "draft",
        "csrf_token": _token(c)})
    assert response.status_code == 200
    preview = response.text.split('id="preview"')[1]
    assert "<h1>Big heading</h1>" in preview
    assert "<script" not in preview.lower()
    assert "onerror" not in preview.lower()
    assert "alert(1)" not in preview
    assert "https://example.test" in preview
    # Preview saves nothing.
    assert "No pages yet" in c.get("/admin/pages").text


def test_markdown_javascript_links_are_stripped_in_preview(client_as):
    c = client_as("editor")
    response = c.post("/admin/pages/preview", data={
        "title": "T", "slug": "", "body": "[x](javascript:alert(1))",
        "status": "draft", "csrf_token": _token(c)})
    assert 'href="javascript' not in response.text.split('id="preview"')[1]


def test_content_list_shows_title_status_and_last_update(client_as):
    """A content list shows all pages with title, status and last update."""
    c = client_as("editor")
    _create(c, title="Draft one", status="draft")
    _create(c, title="Live one", status="published")
    listing = c.get("/admin/pages").text
    assert "Draft one" in listing and "Live one" in listing
    assert "draft" in listing and "published" in listing
    assert re.search(r"\d{4}-\d{2}-\d{2}", listing)


def _admin_page_routes(app):
    # Read the pages router itself: the app wraps included routers, and a route
    # added to this router later is picked up here automatically.
    from app.routes import pages
    return list(pages.router.routes)


def test_every_page_form_rejects_a_post_without_csrf(client_as):
    """Each state-changing page route rejects a POST without a token."""
    c = client_as("editor")
    pid = _page_id(_create(c, title="About"))
    posts = [("/admin/pages", {}), (f"/admin/pages/{pid}", {}),
             (f"/admin/pages/{pid}/publish", {}), (f"/admin/pages/{pid}/unpublish", {}),
             (f"/admin/pages/{pid}/delete", {}), ("/admin/pages/preview", {}),
             (f"/admin/pages/{pid}/lock", {}), (f"/admin/pages/{pid}/unlock", {})]
    form = {"title": "x", "slug": "x2", "body": "b", "status": "draft"}
    for path, _ in posts:
        assert c.post(path, data=form).status_code == 403, path
        assert c.post(path, data={**form, "csrf_token": "wrong"}).status_code == 403, path
    # And nothing changed.
    assert c.get(f"/admin/pages/{pid}/edit").status_code == 200
    assert len(re.findall(r"/edit", c.get("/admin/pages").text)) >= 1


def test_every_post_route_is_covered_by_the_csrf_test(client_as):
    """Guard: a new POST route under /admin/pages must be added to the test above."""
    paths = {r.path for r in _admin_page_routes(client_as("editor").app)
             if "POST" in r.methods}
    assert paths == {"/admin/pages", "/admin/pages/{page_id}",
                     "/admin/pages/{page_id}/publish",
                     "/admin/pages/{page_id}/unpublish",
                     "/admin/pages/{page_id}/delete", "/admin/pages/preview",
                     "/admin/pages/{page_id}/lock", "/admin/pages/{page_id}/unlock"}


def test_anonymous_visitor_is_redirected_to_login_on_every_page_route(client):
    """Routes come from the app's router, so a later route cannot escape."""
    routes = _admin_page_routes(client.app)
    assert routes
    for route in routes:
        path = route.path.replace("{page_id}", "1")
        for method in route.methods - {"HEAD", "OPTIONS"}:
            response = client.request(method, path, follow_redirects=False)
            assert response.status_code == 303, (method, path)
            assert response.headers["location"] == "/login", (method, path)


def test_unknown_page_is_404(client_as):
    c = client_as("editor")
    assert c.get("/admin/pages/999/edit").status_code == 404

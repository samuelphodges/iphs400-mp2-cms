"""T07: the Alumni Network. Each test names the criterion it covers."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db, pages, settings, users
from app.main import create_app
from app.publish import render_site
from tests.conftest import _csrf_from

EMAIL = "secret.alum@alumni.test"


def _token(c) -> str:
    return _csrf_from(c.get("/admin/listings/new"))


def _create(c, name="Pat Alum", email=EMAIL, class_year="1999", consented="on",
            consent_date="2026-09-01", csrf=True):
    data = {"name": name, "email": email, "class_year": class_year,
            "consent_date": consent_date}
    if consented:
        data["consented"] = consented
    if csrf:
        data["csrf_token"] = _token(c)
    return c.post("/admin/listings", data=data, follow_redirects=False)


def _listing_id(response) -> int:
    match = re.search(r"/admin/listings/(\d+)/edit", response.headers["location"])
    assert match, response.headers
    return int(match.group(1))


def _publish_network(database_path, tmp_path) -> Path:
    conn = db.connect(database_path)
    admin = users.get_by_email(conn, "admin@example.test")
    assert admin is not None
    pages.create(conn, title="Alumni Network", slug="alumni-network",
                 body="Alumni who chose to be listed.", status="published",
                 author_id=admin["id"])
    conn.close()
    return render_site(tmp_path / "site", database_path)


def _network_html(out: Path) -> str:
    return (out / "alumni-network.html").read_text()


@pytest.mark.parametrize("role", ["admin", "editor"])
def test_editor_can_create_edit_delete_listing(client_as, role):
    """An editor can create, edit and delete a Listing; recorded-by is the user."""
    c = client_as(role)
    response = _create(c)
    assert response.status_code == 303
    listing_id = _listing_id(response)
    edit = c.get(response.headers["location"])
    assert "saved" in edit.text.lower() and "Pat Alum" in edit.text
    assert "Recorded by" in edit.text
    assert ("Matt Burdette" if role == "admin" else "Joe") in edit.text

    token = _csrf_from(edit)
    saved = c.post(f"/admin/listings/{listing_id}", follow_redirects=False,
                   data={"name": "Pat Q. Alum", "email": EMAIL, "class_year": "",
                         "consented": "on", "consent_date": "2026-09-02",
                         "csrf_token": token})
    assert saved.status_code == 303
    assert "Pat Q. Alum" in c.get("/admin/listings").text

    gone = c.post(f"/admin/listings/{listing_id}/delete", data={"csrf_token": token},
                  follow_redirects=False)
    assert gone.status_code == 303
    assert "No listings yet" in c.get("/admin/listings").text


def test_listings_persist_across_restart(client_as, database_path):
    """Listings persist across a server restart."""
    _create(client_as("editor"))
    fresh = TestClient(create_app(database_path))
    token = _csrf_from(fresh.get("/login"))
    fresh.post("/login", data={"email": "editor@example.test",
                               "password": "test-editor-pw", "csrf_token": token})
    assert "Pat Alum" in fresh.get("/admin/listings").text


def test_consented_without_date_cannot_be_saved(client_as, database_path, tmp_path):
    """A Listing without a consent date cannot be saved as consented."""
    c = client_as("editor")
    response = _create(c, name="No Date", consent_date="")
    assert response.status_code == 422
    assert "consent date" in response.text.lower()
    assert "No Date" not in c.get("/admin/listings").text


def test_listing_without_consent_is_not_published(client_as, database_path, tmp_path):
    """A Listing without consent is saved but not published."""
    c = client_as("editor")
    assert _create(c, name="Quiet Quincy", consented=None, consent_date="").status_code == 303
    assert _create(c, name="Loud Larry").status_code == 303
    html = _network_html(_publish_network(database_path, tmp_path))
    assert "Loud Larry" in html and "Quiet Quincy" not in html


def test_published_names_are_alphabetical_below_page_text(client_as, database_path, tmp_path):
    """Names of consented Listings appear alphabetically, below the page's own text."""
    c = client_as("editor")
    for name in ("Zed Zimmer", "adam Archer", "Mia Moore"):
        _create(c, name=name, email=f"{name.split()[0].lower()}@alumni.test")
    html = _network_html(_publish_network(database_path, tmp_path))
    positions = [html.index(n) for n in ("adam Archer", "Mia Moore", "Zed Zimmer")]
    assert positions == sorted(positions)
    assert html.index("Alumni who chose to be listed.") < positions[0]


def test_delete_or_withdraw_removes_name_at_next_publish(client_as, database_path, tmp_path):
    """Deleting a Listing or removing consent, then publishing, removes the name."""
    c = client_as("editor")
    keep = _listing_id(_create(c, name="Withdrawn Wes"))
    drop = _listing_id(_create(c, name="Deleted Dan"))
    assert "Withdrawn Wes" in _network_html(_publish_network(database_path, tmp_path))
    token = _token(c)
    c.post(f"/admin/listings/{keep}", follow_redirects=False,
           data={"name": "Withdrawn Wes", "email": EMAIL, "class_year": "",
                 "consent_date": "", "csrf_token": token})
    c.post(f"/admin/listings/{drop}/delete", data={"csrf_token": token})
    html = _network_html(render_site(tmp_path / "site", database_path))
    assert "Withdrawn Wes" not in html and "Deleted Dan" not in html


def test_contact_line_uses_site_setting(client_as, database_path, tmp_path, monkeypatch):
    """The Alumni Contact Line appears and uses Joe's address from a site setting."""
    monkeypatch.setattr(settings, "CONTACT_EMAIL", "joe.contact@kenyon.test")
    html = _network_html(_publish_network(database_path, tmp_path))
    assert "joe.contact@kenyon.test" in html


def test_no_alumnus_email_anywhere_in_site(client_as, database_path, tmp_path):
    """No alumnus email appears anywhere in site/."""
    c = client_as("editor")
    _create(c, name="Pat Alum", email=EMAIL)
    _create(c, name="Quiet", email="quiet@alumni.test", consented=None, consent_date="")
    out = _publish_network(database_path, tmp_path)
    for path in out.rglob("*"):
        if path.is_file():
            text = path.read_text()
            assert EMAIL not in text and "quiet@alumni.test" not in text, path


def test_listing_names_are_escaped(client_as, database_path, tmp_path):
    c = client_as("editor")
    _create(c, name="<script>alert(1)</script>")
    assert "<script>" not in _network_html(_publish_network(database_path, tmp_path))


def test_listing_forms_need_csrf(client_as):
    """Every Listing form rejects a POST without a CSRF token."""
    c = client_as("editor")
    assert _create(c, csrf=False).status_code == 403
    listing_id = _listing_id(_create(c))
    assert c.post(f"/admin/listings/{listing_id}", data={"name": "X"}).status_code == 403
    assert c.post(f"/admin/listings/{listing_id}/delete").status_code == 403


def test_anonymous_redirected_to_login(client):
    """Anonymous visitors are redirected to login."""
    for method, path in (("get", "/admin/listings"), ("get", "/admin/listings/new"),
                         ("post", "/admin/listings"), ("post", "/admin/listings/1"),
                         ("post", "/admin/listings/1/delete")):
        r = getattr(client, method)(path, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/login", path

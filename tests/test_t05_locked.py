"""T05: only Matt can change Locked pages. Each test names the criterion it covers."""
import re

import pytest
from fastapi.routing import APIRoute

from app import db, pages
from app.main import create_app
from app.web import require_admin
from tests.conftest import _csrf_from


def _seed_page(database_path, title="Team Schedule", slug="team-schedule", locked=True):
    conn = db.connect(database_path)
    try:
        page_id = pages.create(conn, title=title, slug=slug, body="Sat 1pm vs Denison",
                               status="published", author_id=1)
        if locked:
            pages.set_locked(conn, page_id, True)
        return page_id
    finally:
        conn.close()


def _token(c):
    return _csrf_from(c.get("/admin/pages/new"))


def _save(c, page_id, **over):
    data = {"title": "Changed", "slug": "team-schedule", "body": "x",
            "status": "published", "csrf_token": _token(c)}
    data.update(over)
    return c.post(f"/admin/pages/{page_id}", data=data, follow_redirects=False)


def _action(c, page_id, action):
    return c.post(f"/admin/pages/{page_id}/{action}", data={"csrf_token": _token(c)},
                  follow_redirects=False)


def test_seeded_team_schedule_is_locked(tmp_path, monkeypatch):
    """The seeded Team Schedule page is Locked."""
    from scripts import seed_demo
    monkeypatch.setattr("app.settings.DATABASE_PATH", tmp_path / "seed.db")
    monkeypatch.setenv("CMS_ADMIN_PASSWORD", "a-pw")
    monkeypatch.setenv("CMS_EDITOR_PASSWORD", "e-pw")
    assert seed_demo.main() == 0
    conn = db.connect(tmp_path / "seed.db")
    row = conn.execute("SELECT locked FROM pages WHERE slug = 'team-schedule'").fetchone()
    conn.close()
    assert row is not None and row["locked"] == 1


def test_admin_can_edit_publish_unpublish_delete_locked_page(client_as, database_path):
    """An admin can change a Locked page."""
    c = client_as("admin")
    pid = _seed_page(database_path)
    assert _save(c, pid).status_code == 303
    assert _action(c, pid, "unpublish").status_code == 303
    assert _action(c, pid, "publish").status_code == 303
    assert _action(c, pid, "delete").status_code == 303
    assert c.get(f"/admin/pages/{pid}/edit").status_code == 404


def test_admin_can_lock_and_unlock_any_page(client_as, database_path):
    """An admin can lock or unlock any page."""
    c = client_as("admin")
    pid = _seed_page(database_path, locked=False)
    assert _action(c, pid, "lock").status_code == 303
    conn = db.connect(database_path)
    assert pages.get(conn, pid)["locked"] == 1
    assert _action(c, pid, "unlock").status_code == 303
    assert pages.get(conn, pid)["locked"] == 0
    conn.close()


def test_editor_can_read_a_locked_page(client_as, database_path):
    """An editor can open a Locked page and see its content."""
    pid = _seed_page(database_path)
    r = client_as("editor").get(f"/admin/pages/{pid}/edit")
    assert r.status_code == 200
    assert "Sat 1pm vs Denison" in r.text
    assert "locked" in r.text.lower()


@pytest.mark.parametrize("action", ["save", "publish", "unpublish", "delete"])
def test_editor_is_refused_on_a_locked_page(client_as, database_path, action):
    """Save, publish, unpublish and delete are refused with a clear refusal page."""
    c = client_as("editor")
    pid = _seed_page(database_path)
    r = _save(c, pid) if action == "save" else _action(c, pid, action)
    assert r.status_code == 403
    assert "only the head coach" in r.text.lower()
    conn = db.connect(database_path)
    row = pages.get(conn, pid)
    conn.close()
    assert row is not None and row["title"] == "Team Schedule" and row["status"] == "published"


def test_editor_sees_no_lock_control_and_admin_does(client_as, database_path):
    """An editor sees no lock or unlock control."""
    pid = _seed_page(database_path)
    other = _seed_page(database_path, title="About", slug="about", locked=False)
    for path in ("/admin/pages", f"/admin/pages/{pid}/edit", f"/admin/pages/{other}/edit"):
        editor_html = client_as("editor").get(path).text
        assert "/unlock" not in editor_html and f"/{other}/lock" not in editor_html
    assert f"/{pid}/unlock" in client_as("admin").get("/admin/pages").text
    assert f"/{other}/lock" in client_as("admin").get(f"/admin/pages/{other}/edit").text


def test_forged_lock_on_unlocked_page_gets_an_honest_message(client_as, database_path):
    """The refusal says what happened; it does not claim the page is Locked."""
    other = _seed_page(database_path, title="About", slug="about", locked=False)
    r = _action(client_as("editor"), other, "lock")
    assert r.status_code == 403 and "is locked" not in r.text.lower()


def test_seed_locks_an_existing_unlocked_team_schedule(tmp_path, monkeypatch):
    """The seeded Team Schedule is Locked, even in a database made before T05."""
    from scripts import seed_demo
    path = tmp_path / "old.db"
    db.init_db(path)
    monkeypatch.setattr("app.settings.DATABASE_PATH", path)
    monkeypatch.setenv("CMS_ADMIN_PASSWORD", "a-pw")
    monkeypatch.setenv("CMS_EDITOR_PASSWORD", "e-pw")
    seed_demo.main()
    conn = db.connect(path)
    conn.execute("UPDATE pages SET locked = 0")
    conn.commit()
    conn.close()
    seed_demo.main()
    conn = db.connect(path)
    assert conn.execute("SELECT locked FROM pages WHERE slug = 'team-schedule'").fetchone()[0] == 1
    conn.close()


@pytest.mark.parametrize("action", ["lock", "unlock"])
def test_editor_forged_lock_change_is_refused(client_as, database_path, action):
    """A forged request to change the flag is refused."""
    pid = _seed_page(database_path)
    assert _action(client_as("editor"), pid, action).status_code == 403
    conn = db.connect(database_path)
    assert pages.get(conn, pid)["locked"] == 1
    conn.close()


def test_editor_cannot_set_locked_through_a_save(client_as, database_path):
    """A forged request to change the flag is refused (a smuggled field is ignored)."""
    c = client_as("editor")
    pid = _seed_page(database_path, slug="about", title="About", locked=False)
    _save(c, pid, slug="about", locked="1")
    conn = db.connect(database_path)
    assert pages.get(conn, pid)["locked"] == 0
    conn.close()


def test_editor_can_still_edit_unlocked_pages(client_as, database_path):
    """An editor can edit and publish every unlocked page."""
    c = client_as("editor")
    pid = _seed_page(database_path, slug="about", title="About", locked=False)
    assert _save(c, pid, slug="about").status_code == 303
    assert _action(c, pid, "unpublish").status_code == 303
    assert _action(c, pid, "publish").status_code == 303


def test_refusal_page_is_reachable_for_screenshots(client_as, database_path):
    """The refusal page can be opened directly."""
    r = client_as("editor").get("/admin/refused")
    assert r.status_code == 403
    assert "only the head coach" in r.text.lower()


def _all_routes(app):
    """Every APIRoute, including those in included routers (FastAPI nests them)."""
    for route in app.routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "original_router"):
            yield from (r for r in route.original_router.routes if isinstance(r, APIRoute))


def _admin_only_routes(app):
    return [(route, method) for route in _all_routes(app)
            if any(d.call is require_admin for d in route.dependant.dependencies)
            for method in route.methods]


def test_every_admin_only_route_refuses_editor_and_anonymous(client_as, database_path):
    """Admin-only routes come from the router; each refuses editors and anonymous."""
    from fastapi.testclient import TestClient
    app = create_app(database_path)
    routes = _admin_only_routes(app)
    assert routes, "no admin-only routes found"
    pid = _seed_page(database_path)
    editor = client_as("editor")
    anon = TestClient(app)
    for route, method in routes:
        path = re.sub(r"\{[^}]+\}", str(pid), route.path)
        token = {"csrf_token": _token(editor)}
        r = editor.request(method, path, data=token if method != "GET" else None,
                           follow_redirects=False)
        assert r.status_code in (302, 303, 403), (method, path, r.status_code)
        r = anon.request(method, path, follow_redirects=False)
        assert r.status_code in (302, 303) and r.headers["location"] == "/login", (method, path)

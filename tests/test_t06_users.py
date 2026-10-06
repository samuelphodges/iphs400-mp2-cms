"""T06: the Head Coach can manage users. Each test names the criterion it covers."""
import re

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app import db, users
from app.main import create_app
from tests.conftest import DEMO_USERS, _csrf_from


def _token(c):
    return _csrf_from(c.get("/admin/users"))


def _new_user(c, **over):
    data = {"name": "Sam", "email": "sam@example.test", "password": "sam-secret-pw",
            "role": "editor", "csrf_token": _token(c)}
    data.update(over)
    return c.post("/admin/users", data=data, follow_redirects=False)


def _row(database_path, email):
    conn = db.connect(database_path)
    try:
        return users.get_by_email(conn, email)
    finally:
        conn.close()


def _login(database_path, email, password):
    c = TestClient(create_app(database_path))
    r = c.post("/login", data={"email": email, "password": password,
                               "csrf_token": _csrf_from(c.get("/login"))},
               follow_redirects=False)
    return c, r


def test_admin_creates_user_with_argon2_hash(client_as, database_path):
    """An admin can create a user; the password is stored as an argon2 hash."""
    r = _new_user(client_as("admin"))
    assert r.status_code == 303
    row = _row(database_path, "sam@example.test")
    assert row["role"] == "editor" and row["active"] == 1
    assert row["password_hash"].startswith("$argon2") and "sam-secret-pw" not in row["password_hash"]
    assert _login(database_path, "sam@example.test", "sam-secret-pw")[1].status_code == 303


@pytest.mark.parametrize("over", [{"role": "owner"}, {"name": " "}, {"password": ""},
                                  {"email": "not-an-email"}])
def test_create_rejects_bad_input(client_as, database_path, over):
    """Invalid input shows an error and creates nothing."""
    r = _new_user(client_as("admin"), **over)
    assert r.status_code == 422 and 'role="alert"' in r.text
    assert _row(database_path, "sam@example.test") is None


def test_create_rejects_duplicate_email(client_as):
    """A duplicate email is an error, not a crash."""
    r = _new_user(client_as("admin"), email=DEMO_USERS["editor"]["email"].upper())
    assert r.status_code == 409


def test_admin_changes_role(client_as, database_path):
    """An admin can change a user's role."""
    c = client_as("admin")
    joe = _row(database_path, DEMO_USERS["editor"]["email"])["id"]
    r = c.post(f"/admin/users/{joe}/role", data={"role": "admin", "csrf_token": _token(c)},
               follow_redirects=False)
    assert r.status_code == 303
    assert _row(database_path, DEMO_USERS["editor"]["email"])["role"] == "admin"


def test_deactivate_blocks_login_with_message_and_open_session(client_as, database_path):
    """A deactivated user is refused at login, and an open session stops working."""
    admin = client_as("admin")
    joe_session = client_as("editor")
    assert joe_session.get("/admin/pages").status_code == 200
    joe = _row(database_path, DEMO_USERS["editor"]["email"])["id"]
    r = admin.post(f"/admin/users/{joe}/deactivate", data={"csrf_token": _token(admin)},
                   follow_redirects=False)
    assert r.status_code == 303
    assert joe_session.get("/admin/pages", follow_redirects=False).status_code == 303
    _, r = _login(database_path, DEMO_USERS["editor"]["email"], DEMO_USERS["editor"]["password"])
    assert r.status_code == 401 and "deactivated" in r.text.lower()


def test_reactivate_restores_login(client_as, database_path):
    """An admin can reactivate a user."""
    admin = client_as("admin")
    joe = _row(database_path, DEMO_USERS["editor"]["email"])["id"]
    for action in ("deactivate", "reactivate"):
        admin.post(f"/admin/users/{joe}/{action}", data={"csrf_token": _token(admin)})
    _, r = _login(database_path, DEMO_USERS["editor"]["email"], DEMO_USERS["editor"]["password"])
    assert r.status_code == 303


def test_there_is_no_way_to_delete_a_user(client_as, database_path):
    """No route deletes a user, and the screen offers no delete control."""
    for route in _users_routes(create_app(database_path)):
        assert "delete" not in route.path and "DELETE" not in route.methods
    joe = _row(database_path, DEMO_USERS["editor"]["email"])["id"]
    c = client_as("admin")
    assert "delete" not in c.get("/admin/users").text.lower()
    assert c.post(f"/admin/users/{joe}/delete", data={"csrf_token": _token(c)}).status_code in (404, 405)


@pytest.mark.parametrize("action,data", [("deactivate", {}), ("role", {"role": "editor"})])
def test_admin_cannot_deactivate_or_demote_self(client_as, database_path, action, data):
    """The attempt shows an error and changes nothing."""
    c = client_as("admin")
    me = _row(database_path, DEMO_USERS["admin"]["email"])["id"]
    r = c.post(f"/admin/users/{me}/{action}", data={**data, "csrf_token": _token(c)},
               follow_redirects=False)
    assert r.status_code == 409 and 'role="alert"' in r.text
    row = _row(database_path, DEMO_USERS["admin"]["email"])
    assert row["active"] == 1 and row["role"] == "admin"


def test_unknown_user_is_404(client_as):
    c = client_as("admin")
    assert c.post("/admin/users/999/deactivate", data={"csrf_token": _token(c)}).status_code == 404


def _users_routes(app):
    """Every Users APIRoute, including those in included routers (FastAPI nests them)."""
    found = []
    for route in app.routes:
        nested = getattr(route, "original_router", None)
        for r in ([route] if isinstance(route, APIRoute) else nested.routes if nested else []):
            if isinstance(r, APIRoute) and r.path.startswith("/admin/users"):
                found.append(r)
    return found


def test_editor_and_anonymous_are_kept_out_of_every_users_route(client_as, database_path):
    """An editor is refused and an anonymous visitor is sent to login, on every Users route."""
    app = create_app(database_path)
    routes = _users_routes(app)
    assert len(routes) >= 5
    editor, anon = client_as("editor"), TestClient(app)
    token = _csrf_from(editor.get("/admin/pages/new"))  # valid, so only the role can refuse
    for route in routes:
        path = re.sub(r"\{[^}]+\}", "1", route.path)
        for method in route.methods - {"HEAD", "OPTIONS"}:
            r = editor.request(method, path, data={"csrf_token": token}, follow_redirects=False)
            assert r.status_code == 403, (method, path)
            r = anon.request(method, path, data={"csrf_token": "x"}, follow_redirects=False)
            assert r.status_code == 303 and r.headers["location"] == "/login", (method, path)
    assert _row(database_path, DEMO_USERS["editor"]["email"])["role"] == "editor"


def test_every_users_post_rejects_a_missing_csrf_token(client_as, database_path):
    """Each Users form rejects a POST without a token."""
    c = client_as("admin")
    joe = _row(database_path, DEMO_USERS["editor"]["email"])["id"]
    for path, data in [("/admin/users", {"name": "Z", "email": "z@example.test",
                                         "password": "pw-pw-pw", "role": "editor"}),
                       (f"/admin/users/{joe}/role", {"role": "admin"}),
                       (f"/admin/users/{joe}/deactivate", {}),
                       (f"/admin/users/{joe}/reactivate", {})]:
        assert c.post(path, data=data).status_code == 403, path
    assert _row(database_path, "z@example.test") is None
    assert _row(database_path, DEMO_USERS["editor"]["email"])["role"] == "editor"


def test_users_screen_lists_users_and_forms_carry_tokens(client_as):
    """The screen shows each user, and every form on it carries a CSRF token."""
    html = client_as("admin").get("/admin/users").text
    assert "Matt Burdette" in html and "Joe" in html
    assert html.count("<form") == html.count('name="csrf_token"')  # incl. sign-out form
    assert "/admin/users" in html and "Users</a>" in html


def test_editor_does_not_see_users_link(client_as):
    """The nav hides Users from editors."""
    assert "/admin/users" not in client_as("editor").get("/admin/pages").text

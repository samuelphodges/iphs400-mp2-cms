"""T01: sign in and out. Each test names the acceptance criterion it covers."""
import re
import sqlite3

from fastapi.testclient import TestClient

from tests.conftest import DEMO_USERS, _csrf_from


def _login(client, role="admin", password=None, csrf=True):
    user = DEMO_USERS[role]
    data = {"email": user["email"], "password": password or user["password"]}
    if csrf:
        data["csrf_token"] = _csrf_from(client.get("/login"))
    return client.post("/login", data=data, follow_redirects=False)


def test_seeded_users_can_log_in_and_reach_admin_home(client):
    for role, name in (("admin", "Matt Burdette"), ("editor", "Joe")):
        c = TestClient(client.app)
        response = _login(c, role)
        assert response.status_code == 303
        home = c.get("/admin")
        assert home.status_code == 200
        assert name in home.text  # shell shows who is signed in
        assert role in home.text


def test_wrong_password_is_refused_with_message_and_no_session(client):
    response = _login(client, password="nope")
    assert response.status_code == 401
    assert "do not match" in response.text
    assert client.get("/admin", follow_redirects=False).status_code == 303


def test_unknown_email_gets_the_same_message_as_wrong_password(client):
    token = _csrf_from(client.get("/login"))
    unknown = client.post("/login", data={"email": "nobody@example.test",
                                          "password": "x", "csrf_token": token})
    wrong = _login(client, password="nope")
    assert unknown.status_code == wrong.status_code == 401
    msg = lambda r: re.search(r'role="alert">([^<]+)', r.text).group(1)
    assert msg(unknown) == msg(wrong)


def test_logout_ends_the_session(client_as):
    c = client_as("editor")
    assert c.get("/admin").status_code == 200
    token = _csrf_from(c.get("/admin"))
    assert c.post("/logout", data={"csrf_token": token},
                  follow_redirects=False).status_code == 303
    response = c.get("/admin", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/login"


def test_anonymous_admin_visit_redirects_to_login(client):
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert "Admin home" not in response.text


def test_passwords_are_stored_as_argon2_hashes(database_path):
    conn = sqlite3.connect(database_path)
    rows = conn.execute("SELECT password_hash FROM users").fetchall()
    assert rows
    for (stored,) in rows:
        assert stored.startswith("$argon2")
        assert all(u["password"] not in stored for u in DEMO_USERS.values())


def test_password_is_not_logged(client, caplog):
    with caplog.at_level("DEBUG"):
        _login(client, password="super-secret-wrong-pw")
    assert "super-secret-wrong-pw" not in caplog.text


def test_login_form_carries_csrf_token_and_post_without_one_is_rejected(client):
    assert 'name="csrf_token"' in client.get("/login").text
    response = _login(client, csrf=False)
    assert response.status_code == 403
    bad = client.post("/login", data={**{"email": DEMO_USERS["admin"]["email"],
                                         "password": DEMO_USERS["admin"]["password"]},
                                      "csrf_token": "forged"})
    assert bad.status_code == 403
    assert client.get("/admin", follow_redirects=False).status_code == 303


def test_logout_without_csrf_token_is_rejected(client_as):
    c = client_as("admin")
    assert c.post("/logout", follow_redirects=False).status_code == 403
    assert c.get("/admin").status_code == 200


def test_session_records_role(client_as):
    # The admin shell derives the label from the session's user, per role.
    assert "(admin)" in client_as("admin").get("/admin").text
    assert "(editor)" in client_as("editor").get("/admin").text


def test_deactivated_user_is_refused_at_login_and_loses_session(client_as, database_path):
    c = client_as("editor")
    conn = sqlite3.connect(database_path)
    conn.execute("UPDATE users SET active = 0 WHERE role = 'editor'")
    conn.commit()
    conn.close()
    assert c.get("/admin", follow_redirects=False).status_code == 303
    fresh = TestClient(c.app)
    response = _login(fresh, "editor")
    assert response.status_code == 401 and "deactivated" in response.text


def test_session_cookie_records_the_role(client_as):
    import base64
    import json

    for role in ("admin", "editor"):
        cookie = client_as(role).cookies["cms_session"]
        payload = json.loads(base64.urlsafe_b64decode(cookie.split(".")[0] + "=="))
        assert payload["role"] == role


def test_every_admin_route_redirects_anonymous_visitors(client):
    """Enumerated from the app's own router, so a new route cannot escape."""
    # The OpenAPI schema lists routes added with include_router, which app.routes hides.
    paths = [path for path, ops in client.app.openapi()["paths"].items()
             if path.startswith("/admin") and "get" in ops and "{" not in path]
    assert "/admin" in paths and "/admin/users" in paths
    for path in paths:
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303, path
        assert response.headers["location"] == "/login", path

"""Shared test fixtures.

`client` gives you the app. `client_as(role)` gives you a client that is logged
in as a seeded user of that role — it works as soon as your login route exists,
so access-control tests stay one line:

    def test_editor_cannot_manage_users(client_as):
        assert client_as("editor").get("/admin/users").status_code in (302, 403)
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import db, users
from app.main import create_app

# Matches scripts/seed_demo.py. Passwords come from the environment there; in
# tests they are fixed and meaningless.
DEMO_USERS = {
    "admin": {"email": "admin@example.test", "password": "test-admin-pw"},
    "editor": {"email": "editor@example.test", "password": "test-editor-pw"},
}


def _csrf_from(response) -> str:
    """Pull the CSRF token out of a rendered form."""
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    assert match, "page has no CSRF token"
    return match.group(1)


@pytest.fixture
def database_path(tmp_path):
    """A fresh SQLite file with the two demo users, so tests never share state."""
    path = tmp_path / "test.db"
    db.init_db(path)
    conn = db.connect(path)
    for role, name in (("admin", "Matt Burdette"), ("editor", "Joe")):
        users.create_user(conn, email=DEMO_USERS[role]["email"], name=name,
                          password=DEMO_USERS[role]["password"], role=role)
    conn.close()
    return path


@pytest.fixture
def client(database_path) -> TestClient:
    return TestClient(create_app(database_path))


@pytest.fixture
def client_as(database_path):
    """Return a factory: client_as("editor") -> a logged-in TestClient."""

    def _login(role: str) -> TestClient:
        user = DEMO_USERS[role]
        c = TestClient(create_app(database_path))
        token = _csrf_from(c.get("/login"))
        response = c.post("/login", data={"email": user["email"],
                                          "password": user["password"],
                                          "csrf_token": token},
                          follow_redirects=False)
        if response.status_code == 404:
            pytest.skip("No /login route yet — build the login ticket first.")
        assert response.status_code in (200, 302, 303), (
            f"Login as {role} failed with {response.status_code}")
        return c

    return _login

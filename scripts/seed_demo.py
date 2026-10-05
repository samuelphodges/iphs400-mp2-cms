#!/usr/bin/env python3
"""Create demo data so a grader (and you) can use the CMS immediately.

    uv run python scripts/seed_demo.py

T00 has nothing to seed. As you build content types, extend this so it creates:
  - one admin and one editor (passwords read from .env, never hard-coded)
  - a few posts and pages, at least one draft and one published

The rubric expects this to run clean on a fresh clone with .env.example values
(item E4), because the database itself is never committed.
"""
from __future__ import annotations

import os
import sys

from app import db, posts, settings, users


def main() -> int:
    admin_pw = os.environ.get("CMS_ADMIN_PASSWORD")
    editor_pw = os.environ.get("CMS_EDITOR_PASSWORD")
    if not admin_pw or not editor_pw:
        print("Set CMS_ADMIN_PASSWORD and CMS_EDITOR_PASSWORD in .env "
              "(copy .env.example).")
        return 1

    db.init_db(settings.DATABASE_PATH)
    conn = db.connect(settings.DATABASE_PATH)
    try:
        for email, name, password, role in (
            ("admin@example.test", "Matt Burdette", admin_pw, "admin"),
            ("editor@example.test", "Joe", editor_pw, "editor"),
        ):
            if users.get_by_email(conn, email) is None:
                users.create_user(conn, email=email, name=name,
                                  password=password, role=role)
                print(f"Created {role}: {email}")
            else:
                print(f"Exists: {email}")
        editor = users.get_by_email(conn, "editor@example.test")
        if editor is not None and not posts.list_posts(conn):
            for title, post_type, status, body in (
                ("Spring Reunion Weekend", "event", "published",
                 "Join us on campus for the annual alumni reunion."),
                ("Game-Watch at the Pub", "event", "published",
                 "Watch the conference final together."),
                ("Fall Ball Wrap-Up", "team_update", "published",
                 "The team finished fall ball with a strong week."),
                ("Draft: Banquet Details", "event", "draft", "Still to be confirmed."),
            ):
                posts.create(conn, title=title, slug=posts.slugify(title), body=body,
                             status=status, post_type=post_type, author_id=editor["id"])
            print("Created sample posts")
    finally:
        conn.close()
    # TODO (later tickets): listings.
    return 0


if __name__ == "__main__":
    sys.exit(main())

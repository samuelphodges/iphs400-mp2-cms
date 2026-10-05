"""T03: publish pages to site/. Each test names the criterion it covers."""
import re
import subprocess
import sys

import pytest

from app import db, pages
from app.publish import render_site


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


def _publish(tmp_path, database_path):
    return render_site(tmp_path / "site", database_path=database_path)


def test_publish_writes_published_pages_and_not_drafts(add_page, database_path, tmp_path):
    """One HTML page per published page; drafts are not written."""
    add_page("About", status="published")
    add_page("Secret Plans", status="draft")
    out = _publish(tmp_path, database_path)
    assert (out / "about.html").exists()
    assert not (out / "secret-plans.html").exists()
    assert "Secret Plans" not in "".join(p.read_text() for p in out.glob("*.html"))


def test_unpublishing_and_republishing_removes_the_page(add_page, database_path, tmp_path):
    """Unpublish a page, re-run publish, and its file is gone."""
    page_id = add_page("About")
    out = _publish(tmp_path, database_path)
    assert (out / "about.html").exists()
    conn = db.connect(database_path)
    pages.set_status(conn, page_id, "draft")
    conn.close()
    out = _publish(tmp_path, database_path)
    assert not (out / "about.html").exists()
    assert "about.html" not in (out / "index.html").read_text()


def _nav_hrefs(html):
    nav = re.search(r"<nav.*?</nav>", html, re.S)
    assert nav, "page has no <nav>"
    return re.findall(r'href="([^"]+)"', nav.group(0))


def test_navigation_lists_published_pages_home_first_then_alphabetical(
        add_page, database_path, tmp_path):
    """Every page has a nav: Home first, the rest alphabetical, drafts absent."""
    add_page("Team Schedule")
    add_page("About")
    add_page("Home", slug="home")
    add_page("Alumni Network")
    add_page("Hidden", status="draft")
    out = _publish(tmp_path, database_path)
    expected = ["index.html", "about.html", "alumni-network.html", "team-schedule.html"]
    for f in out.glob("*.html"):
        assert _nav_hrefs(f.read_text()) == expected, f.name


def test_page_with_slug_index_does_not_overwrite_home(add_page, database_path, tmp_path):
    add_page("Home", body="Welcome fans", slug="home")
    add_page("Index", slug="index")
    out = _publish(tmp_path, database_path)
    assert "Welcome fans" in (out / "index.html").read_text()
    _assert_site_is_relative_and_resolves(out)


def test_home_page_is_the_index(add_page, database_path, tmp_path):
    """The page with slug home is written as index.html."""
    add_page("Home", body="Welcome fans", slug="home")
    out = _publish(tmp_path, database_path)
    assert "Welcome fans" in (out / "index.html").read_text()
    assert not (out / "home.html").exists()


def test_markdown_is_sanitized_on_export(add_page, database_path, tmp_path):
    """A <script> tag and an onerror= attribute are absent from the output."""
    add_page("About", body='Hi <script>alert(1)</script>\n\n<img src="x" onerror="alert(2)">')
    html = (_publish(tmp_path, database_path) / "about.html").read_text()
    assert "<script" not in html and "onerror" not in html
    assert "Hi" in html


def _assert_site_is_relative_and_resolves(out):
    files = list(out.rglob("*.html"))
    assert files
    for f in files:
        html = f.read_text()
        assert 'href="/' not in html and 'src="/' not in html, f.name
        for link in re.findall(r'(?:href|src)="([^"]+)"', html):
            if re.match(r"[a-z][a-z0-9+.-]*:", link) or link.startswith("#"):
                continue
            assert (f.parent / link.split("#")[0]).exists(), f"{f.name} -> {link}"


def test_no_root_absolute_paths_and_links_resolve(add_page, database_path, tmp_path):
    """Even a root-absolute link typed into a body is not exported."""
    add_page("Home", slug="home", body="[sched](/team-schedule) ![x](/img.png)")
    add_page("Team Schedule")
    add_page("Draft Page", status="draft")
    add_page("About", body="[d](draft-page.html) [t](team-schedule.html#top) [x](https://example.org)")
    out = _publish(tmp_path, database_path)
    about = (out / "about.html").read_text()
    assert "draft-page.html" not in about  # a link to an unpublished page is dropped
    assert 'href="team-schedule.html#top"' in about and "https://example.org" in about
    _assert_site_is_relative_and_resolves(_publish(tmp_path, database_path))


def test_site_works_from_a_subfolder(add_page, database_path, tmp_path):
    """CSS and nav are bare relative names, so a Pages subfolder serves them."""
    add_page("About")
    out = _publish(tmp_path, database_path)
    html = (out / "about.html").read_text()
    assert 'href="style.css"' in html
    assert (out / "style.css").exists()


def test_cms_publish_command_writes_site(add_page, database_path, tmp_path, monkeypatch):
    from app import cli, settings
    add_page("About")
    monkeypatch.setattr(settings, "DATABASE_PATH", database_path)
    monkeypatch.setattr(settings, "SITE", tmp_path / "site")
    assert cli.main(["publish"]) == 0
    assert (tmp_path / "site" / "about.html").exists()


def test_deploy_pushes_site_to_gh_pages_branch(add_page, database_path, tmp_path, monkeypatch):
    """`cms deploy` pushes site/ to gh-pages (checked against a local bare remote)."""
    from app import cli, settings

    def git(*args, cwd):
        subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)

    remote, work = tmp_path / "remote.git", tmp_path / "work"
    remote.mkdir(), work.mkdir()
    git("init", "--bare", cwd=remote)
    git("init", "-b", "main", cwd=work)
    git("config", "user.email", "t@example.test", cwd=work)
    git("config", "user.name", "T", cwd=work)
    git("commit", "--allow-empty", "-m", "init", cwd=work)
    git("remote", "add", "origin", str(remote), cwd=work)
    add_page("About")
    monkeypatch.setattr(settings, "DATABASE_PATH", database_path)
    monkeypatch.setattr(settings, "SITE", work / "site")
    monkeypatch.chdir(work)
    assert cli.main(["publish"]) == 0
    assert cli.main(["deploy"]) == 0
    tree = subprocess.run(["git", "ls-tree", "--name-only", "gh-pages"], cwd=remote,
                          check=True, capture_output=True, text=True).stdout.split()
    assert "about.html" in tree and "index.html" in tree

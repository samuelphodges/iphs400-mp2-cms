"""Markdown to safe HTML. Everything user-written goes through here (CLAUDE.md)."""
from __future__ import annotations

import re

import nh3
from markdown_it import MarkdownIt

# Raw HTML is allowed through the parser and then stripped by the sanitizer, so
# a <script> or onerror= disappears rather than showing up as visible text.
_md = MarkdownIt("commonmark", {"html": True})

_HAS_SCHEME = re.compile(r"[a-z][a-z0-9+.-]*:", re.I)


def _keep_only_resolving(link_targets: set[str]):
    """Attribute filter for publish: keep external, #fragment and in-site links.

    Published pages are served from a subfolder, so root-absolute links ("/x",
    "//x") would break, and a relative link to a file that is not in site/
    (a draft, a typo) would be dead. Both are dropped.
    """
    def keep(tag: str, attr: str, value: str) -> str | None:
        if attr not in ("href", "src"):
            return value
        target = value.strip()
        if target.startswith(("/", "\\")):
            return None
        if not target or target.startswith("#") or _HAS_SCHEME.match(target):
            return value
        return value if target.split("#")[0].split("?")[0] in link_targets else None
    return keep


def render_markdown(source: str, *, link_targets: set[str] | None = None) -> str:
    """Render and sanitize. With link_targets (the files in site/), also drop
    links that would not work on the published site."""
    html = _md.render(source)
    if link_targets is None:
        return nh3.clean(html)
    return nh3.clean(html, attribute_filter=_keep_only_resolving(link_targets))

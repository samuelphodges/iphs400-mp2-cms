"""Markdown to safe HTML. Everything user-written goes through here (CLAUDE.md)."""
from __future__ import annotations

import nh3
from markdown_it import MarkdownIt

# Raw HTML is allowed through the parser and then stripped by the sanitizer, so
# a <script> or onerror= disappears rather than showing up as visible text.
_md = MarkdownIt("commonmark", {"html": True})


def render_markdown(source: str) -> str:
    return nh3.clean(_md.render(source))

"""Shared Jinja2Templates instance with custom filters."""

from __future__ import annotations

import os
import re

from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin

_md = MarkdownIt("commonmark").use(dollarmath_plugin, allow_labels=True, allow_space=True)

_INLINE_CITATION_RE = re.compile(r"\[(\d+)\]")
# Finds a "## References" heading anywhere in the text
_REF_SECTION_SPLIT_RE = re.compile(r"^##\s*References\b", re.MULTILINE | re.IGNORECASE)
# Adds id="ref-N" to <li> items whose content starts with [N]
_REF_LI_RE = re.compile(r"<li>\s*\[(\d+)\]")


def _linkify_inline_citations(html: str) -> str:
    return _INLINE_CITATION_RE.sub(
        r'<sup><a href="#ref-\1" class="citation-ref">[\1]</a></sup>', html
    )


def _render_md(text: str) -> str:
    text = text.strip()
    m = _REF_SECTION_SPLIT_RE.search(text)
    if m:
        prose = text[: m.start()].strip()
        refs_md = text[m.start() :]
        prose_html = _linkify_inline_citations(_md.render(prose)) if prose else ""
        refs_html = _REF_LI_RE.sub(r'<li id="ref-\1">[\1]', _md.render(refs_md))
        return prose_html + refs_html
    html = _md.render(text)
    return _linkify_inline_citations(html)


_templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=_templates_dir)
templates.env.filters["md"] = _render_md

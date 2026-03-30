"""Shared Jinja2Templates instance with custom filters."""

from __future__ import annotations

import os
import re

from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin

_md = MarkdownIt("commonmark").use(dollarmath_plugin, allow_labels=True, allow_space=True)

_INLINE_CITATION_RE = re.compile(r"\[(\d+)\]")
_REF_HEADING_RE = re.compile(r"(<h2[^>]*>\s*References\s*</h2>.*)", re.DOTALL | re.IGNORECASE)
_REF_LIST_ITEM_RE = re.compile(r"<li>\[(\d+)\]")


def _linkify_inline_citations(html: str) -> str:
    return _INLINE_CITATION_RE.sub(
        r'<sup><a href="#ref-\1" class="citation-ref">[\1]</a></sup>', html
    )


def _render_md(text: str) -> str:
    html = _md.render(text)
    ref_match = _REF_HEADING_RE.search(html)
    if ref_match:
        prose_html = _linkify_inline_citations(html[: ref_match.start()])
        refs_html = _REF_LIST_ITEM_RE.sub(r'<li id="ref-\1">[\1]', html[ref_match.start() :])
        return prose_html + refs_html
    return _linkify_inline_citations(html)


_templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=_templates_dir)
templates.env.filters["md"] = _render_md

"""Shared Jinja2Templates instance with custom filters."""

from __future__ import annotations

import os
import re

from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin

_md = MarkdownIt("commonmark").use(dollarmath_plugin, allow_labels=True, allow_space=True)

_INLINE_CITATION_RE = re.compile(r"\[(\d+)\]")
# Matches "## References" heading optionally followed by ref lines in the same block
_REF_SECTION_RE = re.compile(r"^##\s*References\s*\n?(.*)", re.DOTALL | re.IGNORECASE)
_REF_LINE_RE = re.compile(r"^\[(\d+)\](.*)", re.MULTILINE)


def _linkify_inline_citations(html: str) -> str:
    return _INLINE_CITATION_RE.sub(
        r'<sup><a href="#ref-\1" class="citation-ref">[\1]</a></sup>', html
    )


def _render_ref_lines(refs_text: str) -> str:
    """Render [n] reference lines as separate anchored paragraphs."""
    parts = []
    for line in refs_text.strip().splitlines():
        m = _REF_LINE_RE.match(line.strip())
        if m:
            n, rest = m.group(1), m.group(2).strip()
            parts.append(
                f'<p id="ref-{n}" class="reference-item">'
                f'<span class="ref-num">[{n}]</span> {rest}</p>'
            )
    return "\n".join(parts)


def _is_ref_only_paragraph(text: str) -> bool:
    """Return True if every non-empty line is a [n] reference line."""
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    return bool(lines) and all(_REF_LINE_RE.match(ln) for ln in lines)


def _render_md(text: str) -> str:
    stripped = text.strip()
    # If this paragraph contains the References heading, split prose from refs
    ref_match = _REF_SECTION_RE.match(stripped)
    if ref_match:
        refs_html = _render_ref_lines(ref_match.group(1))
        return '<h2 class="references-heading">References</h2>\n' + refs_html
    # If the LLM put a blank line between "## References" and the ref lines,
    # they land here as a standalone paragraph — render them as anchored refs.
    if _is_ref_only_paragraph(stripped):
        return _render_ref_lines(stripped)
    html = _md.render(text)
    return _linkify_inline_citations(html)


_templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=_templates_dir)
templates.env.filters["md"] = _render_md

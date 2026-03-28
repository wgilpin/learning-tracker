"""Shared Jinja2Templates instance with custom filters."""

from __future__ import annotations

import os

from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin

_md = MarkdownIt("commonmark").use(dollarmath_plugin, allow_labels=True, allow_space=True)


def _render_md(text: str) -> str:
    return _md.render(text)


_templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=_templates_dir)
templates.env.filters["md"] = _render_md

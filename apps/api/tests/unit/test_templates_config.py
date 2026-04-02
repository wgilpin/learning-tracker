"""Unit tests for the _render_md filter: inline citation linkification."""

from __future__ import annotations

import pytest


class TestRenderMdCitations:
    def test_linkifies_inline_citation(self) -> None:
        from api.templates_config import _render_md

        html = _render_md("Some claim. [1]")
        assert '<a href="#ref-1"' in html
        assert "citation-ref" in html

    def test_linkifies_multiple_citations(self) -> None:
        from api.templates_config import _render_md

        html = _render_md("Claim one [1] and claim two [2].")
        assert '<a href="#ref-1"' in html
        assert '<a href="#ref-2"' in html

    def test_no_citations_passes_through_unchanged_structure(self) -> None:
        from api.templates_config import _render_md

        html = _render_md("Plain prose with no citations.")
        assert "citation-ref" not in html
        assert "Plain prose" in html

    def test_adds_id_to_reference_list_items_when_block_starts_with_heading(self) -> None:
        """A block that starts with ## References gets anchored <p id="ref-N"> items."""
        from api.templates_config import _render_md

        text = "## References\n\n[1] Smith (2023). A Title."
        html = _render_md(text)
        assert 'id="ref-1"' in html

    def test_mixed_prose_and_refs_linkifies_citations_only(self) -> None:
        """When prose precedes ## References, _render_md linkifies inline citations but
        does not add id attrs (the filter is per-block; refs are a separate block)."""
        from api.templates_config import _render_md

        prose = "Claim [1]."
        html = _render_md(prose)
        assert '<a href="#ref-1"' in html
        # No id attrs expected — refs section is a separate template block
        assert 'id="ref-1"' not in html

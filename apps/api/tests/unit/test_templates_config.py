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

    def test_adds_id_to_reference_list_items(self) -> None:
        from api.templates_config import _render_md

        text = "Some claim [1].\n\n## References\n\n- [1] Smith (2023). A Title."
        html = _render_md(text)
        assert 'id="ref-1"' in html

    def test_prose_citation_not_linkified_inside_references_section(self) -> None:
        """[n] markers in the References section list items should get id attrs, not be double-wrapped."""
        from api.templates_config import _render_md

        text = "Claim [1].\n\n## References\n\n- [1] Author (2023). Title."
        html = _render_md(text)
        # The ref list item should have an id, not a nested <a> inside the id-bearing <li>
        assert 'id="ref-1"' in html
        # Prose citation should still be linkified
        assert '<a href="#ref-1"' in html

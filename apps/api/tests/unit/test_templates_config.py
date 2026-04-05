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


class TestRenderMdRefsSplitByBlankLine:
    """The template splits chapter.content by '\\n\\n' before calling | md.

    When the LLM puts a blank line between '## References' and the [n] lines,
    each lands in a separate _render_md call. Both must be handled correctly.
    """

    def test_standalone_ref_lines_get_anchored_paragraphs(self) -> None:
        """[n] lines in their own paragraph produce id='ref-N', no <a> wrapping."""
        from api.templates_config import _render_md

        html = _render_md("[1] Smith (2023). A Title. https://example.com")
        assert 'id="ref-1"' in html
        assert "ref-num" in html

    def test_standalone_ref_lines_no_citation_linkification(self) -> None:
        """[n] in a ref-only paragraph must NOT become a superscript <a> link."""
        from api.templates_config import _render_md

        html = _render_md("[1] Smith (2023). A Title.")
        assert "<sup>" not in html
        assert "citation-ref" not in html

    def test_standalone_ref_lines_no_autolinked_urls(self) -> None:
        """URLs in ref lines must not be wrapped in <a> tags by the markdown renderer."""
        from api.templates_config import _render_md

        html = _render_md("[1] (n.d.) mathbooks.unl.edu https://mathbooks.unl.edu/Contemporary/sec-graph-intro.html")
        assert 'href="https://mathbooks.unl.edu' not in html

    def test_multiple_standalone_ref_lines(self) -> None:
        """Multiple [n] lines in one paragraph each get their own anchor."""
        from api.templates_config import _render_md

        html = _render_md("[1] First source.\n[2] Second source.")
        assert 'id="ref-1"' in html
        assert 'id="ref-2"' in html

    def test_prose_paragraph_not_mistaken_for_refs(self) -> None:
        """A prose paragraph that happens to start with text is not treated as refs."""
        from api.templates_config import _render_md

        html = _render_md("Some ordinary prose with no citation markers.")
        assert 'id="ref-' not in html

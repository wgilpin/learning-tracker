"""Unit tests for chapter_scribe helpers: citation extraction, source formatting."""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import MagicMock

import pytest


class TestExtractCitedIndices:
    def test_extracts_single_citation(self) -> None:
        from documentlm_core.agents.chapter_scribe import _extract_cited_indices

        assert _extract_cited_indices("Some claim. [1]") == {1}

    def test_extracts_multiple_citations(self) -> None:
        from documentlm_core.agents.chapter_scribe import _extract_cited_indices

        assert _extract_cited_indices("Claim one [1] and claim two [3].") == {1, 3}

    def test_deduplicates_repeated_citation(self) -> None:
        from documentlm_core.agents.chapter_scribe import _extract_cited_indices

        assert _extract_cited_indices("[1] is mentioned again [1].") == {1}

    def test_returns_empty_set_for_no_citations(self) -> None:
        from documentlm_core.agents.chapter_scribe import _extract_cited_indices

        assert _extract_cited_indices("No citations here.") == set()

    def test_ignores_non_numeric_brackets(self) -> None:
        from documentlm_core.agents.chapter_scribe import _extract_cited_indices

        assert _extract_cited_indices("[abc] and [1]") == {1}


class TestFormatSourceForPrompt:
    def _make_source(
        self,
        *,
        title: str = "Test Title",
        authors: list[str] | None = None,
        publication_date=None,
        doi: str | None = None,
        url: str | None = None,
    ) -> MagicMock:
        source = MagicMock()
        source.title = title
        source.authors = authors
        source.publication_date = publication_date
        source.doi = doi
        source.url = url
        return source

    def test_formats_with_doi(self) -> None:
        from documentlm_core.agents.chapter_scribe import _format_source_for_prompt

        pub_date = MagicMock()
        pub_date.year = 2017
        source = self._make_source(
            title="Attention Is All You Need",
            authors=["Vaswani", "Shazeer"],
            publication_date=pub_date,
            doi="10.1234/arxiv.1706.03762",
        )
        result = _format_source_for_prompt(1, source)
        assert result.startswith("[1]")
        assert "Vaswani" in result
        assert "2017" in result
        assert "DOI:10.1234/arxiv.1706.03762" in result

    def test_formats_with_url_when_no_doi(self) -> None:
        from documentlm_core.agents.chapter_scribe import _format_source_for_prompt

        pub_date = MagicMock()
        pub_date.year = 2020
        source = self._make_source(
            title="Some Paper",
            authors=["Smith"],
            publication_date=pub_date,
            url="https://arxiv.org/abs/2001.00001",
        )
        result = _format_source_for_prompt(2, source)
        assert "https://arxiv.org/abs/2001.00001" in result
        assert "DOI" not in result

    def test_omits_authors_when_missing(self) -> None:
        from documentlm_core.agents.chapter_scribe import _format_source_for_prompt

        source = self._make_source(title="No Author Paper", authors=None)
        result = _format_source_for_prompt(1, source)
        assert result.startswith("[1]")
        assert "Unknown" not in result
        assert "No Author Paper" in result

    def test_omits_date_when_missing(self) -> None:
        from documentlm_core.agents.chapter_scribe import _format_source_for_prompt

        source = self._make_source(title="Undated Paper", publication_date=None)
        result = _format_source_for_prompt(1, source)
        assert result.startswith("[1]")
        assert "Undated Paper" in result

    def test_unknown_citation_index_dropped_from_cited_ids(self) -> None:
        """If LLM cites [99] which is not in source_map, it is silently dropped."""
        from documentlm_core.agents.chapter_scribe import _extract_cited_indices

        content = "Some claim [1] and hallucinated [99]."
        cited_indices = _extract_cited_indices(content)
        source_map = {1: uuid.uuid4()}
        cited_source_ids = [source_map[n] for n in sorted(cited_indices) if n in source_map]
        assert len(cited_source_ids) == 1
        assert 99 not in {n for n in cited_indices if n in source_map}

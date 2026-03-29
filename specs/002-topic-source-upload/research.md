# Research: Topic Source Upload

**Date**: 2026-03-29 | **Branch**: `002-topic-source-upload`

## 1. PDF extraction from uploaded bytes

**Decision**: Extend `nlp_utils` with `extract_pdf_text_from_bytes(data: bytes) -> str`.

**Rationale**: The existing `fetch_pdf_text(url)` in nlp_utils downloads from a URL; file uploads arrive as `bytes` from `UploadFile.read()`. Adding a bytes-in variant keeps all PDF logic in one place and avoids re-implementing pypdf usage in the app layer.

**Alternatives considered**:
- Re-implement pypdf in the API layer — rejected (duplicates nlp_utils).
- Decode upload to a temp file and call the URL version — rejected (unnecessary I/O).

**Image-only fallback**: When pypdf returns no text, fall back to `fetch_pdf_text_llm` (already in nlp_utils) by passing the base64-encoded bytes directly. This covers scanned syllabi.

---

## 2. URL scraping for text extraction

**Decision**: Add `fetch_url_text(url: str, timeout: float = 30.0) -> str` to `nlp_utils/fetcher.py`.

**Rationale**: The function composes the already-present `httpx` client with `extract_clean_html` from `nlp_utils/html.py`. Adding it to nlp_utils keeps the app layer free of HTTP/parse logic and makes it mockable in tests.

**Alternatives considered**:
- Use `html_to_markdown` for storage — rejected for now; clean plain text is sufficient for agent prompts and avoids markdown artefacts from poorly structured pages.
- Scrape in the API layer with a direct httpx call — rejected (not mockable cleanly, logic leaks).

---

## 3. YouTube transcript extraction

**Decision**: Add `fetch_youtube_transcript(url_or_id: str) -> tuple[str, str]` (returns `(title, text)`) to a new `nlp_utils/youtube.py`, surfaced via `__init__.py`.

**Rationale**: `youtube-transcript-api` is the standard Python library for this purpose. It does not require an API key and handles language selection. A title is retrieved via `yt-dlp`'s metadata or a lightweight info fetch; if unavailable the video ID is used as the title.

**Alternatives considered**:
- Use YouTube Data API v3 — rejected; requires API key, already used for search in `academic_scout`; transcript endpoint is separate and more complex.
- Parse transcript from the HTML page — rejected; fragile.

**Error handling**: `TranscriptsDisabled`, `NoTranscriptFound` from the library are caught and re-raised as `ValueError` with a user-friendly message so the caller can show inline feedback.

---

## 4. Source model — storing extracted content

**Decision**: Add three columns to the `sources` table:
- `source_type: str` — values: `PDF_UPLOAD`, `URL_SCRAPE`, `YOUTUBE_TRANSCRIPT`, `RAW_TEXT`, `SEARCH` (existing sources become `SEARCH`).
- `is_primary: bool NOT NULL DEFAULT false` — true for all user-provided sources.
- `content: TEXT NULL` — extracted text; NULL for `SEARCH` sources that were never fetched.

**Rationale**: The current `Source` model is purely bibliographic (title, authors, URL, DOI). It has no content field. Content must be stored to pass to agents at generation time without re-fetching.

**Alternatives considered**:
- Separate `PrimarySource` table — rejected; the spec says primary sources are saved "just like any other source"; a single table with a flag is simpler.
- Store content in a separate `source_content` table — rejected (premature normalisation for a prototype).

**Deduplication for raw text**: Detect duplicates by SHA-256 hash of the content stored in a new `content_hash: str NULL` column. URL/DOI deduplication already handled by existing `UniqueConstraint`.

---

## 5. Topic creation workflow — two-step wizard

**Decision**: Split topic creation into two stages:
1. **Step 1** — Title + description form → `POST /topics` → creates topic → redirects to `/topics/{id}/sources`.
2. **Step 2** — Source intake page → user adds sources one at a time via HTMX → `POST /topics/{id}/sources/extract` → immediate inline feedback → "Generate" button becomes active.

**Rationale**: This is the simplest way to satisfy "extraction happens immediately on add" (Q1) while keeping topic_id available for FK constraints. It also naturally satisfies post-creation source management (Q2) because Step 2 is just the topic detail page with a source intake panel — the same panel can be used later.

**Alternatives considered**:
- Stateless extraction endpoint + hidden form fields: rejects large PDFs and complex multi-source state.
- Draft topic concept: additional complexity with draft/published lifecycle.
- Keep single-step creation: requires sessionStorage or cookies to hold extracted text client-side before topic_id exists.

---

## 6. Syllabus Architect — primary source integration

**Decision**: Extend `run_syllabus_architect` to accept an optional `primary_source_texts: list[str]`.

- If `primary_source_texts` is non-empty: inject them into the LLM prompt as "provided course materials". If exactly one is present, instruct the agent to use it exactly. If multiple, instruct it to synthesise a single coherent structure.
- If empty: existing free-generation behaviour unchanged (FR-014).

**Rationale**: The agent already uses a string prompt to the Gemini model. Prepending primary source content to the prompt is the minimal change needed to satisfy FR-010. No new agent type required.

---

## 7. Academic Scout — skip search when primary sources present

**Decision**: Add a guard at the start of `run_academic_scout`:  if the topic already has any primary sources (`is_primary=True`), run search only after emitting a log message confirming primaries are loaded first. Search results are still added as non-primary sources to supplement gaps (FR-011).

**Rationale**: The spec requires search to happen *after* primary sources are processed, not to be suppressed entirely. The Academic Scout runs in a background task after topic creation; by the time it runs, primary sources are already saved.

---

## 8. nlp_utils — dependency additions

| Package | Purpose | Added to |
|---------|---------|----------|
| `youtube-transcript-api` | Transcript download | nlp_utils pyproject.toml |
| `yt-dlp` | Video title metadata | nlp_utils pyproject.toml |

`pypdf` and `httpx` are already in nlp_utils. `beautifulsoup4`/`lxml`/`markdownify` already present.

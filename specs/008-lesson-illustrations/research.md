# Research: Lesson Illustrations

**Feature**: 008-lesson-illustrations  
**Date**: 2026-04-04

---

## Decision 1: Image Generation API

**Decision**: Use `google.genai.Client` directly (not Google ADK `Agent`/`Runner`) for image generation.

**Rationale**: Image generation is a single stateless API call, not a multi-turn agent conversation. Using the ADK's `Runner`/`InMemorySessionService` for this purpose adds unnecessary overhead. The `google.genai` library is already transitively available (Google ADK depends on it). The call pattern is:

```python
from google import genai
from google.genai import types as genai_types

client = genai.Client(api_key=settings.google_api_key)
response = await client.aio.models.generate_content(
    model=settings.illustration_model,
    contents=prompt,
    config=genai_types.GenerateContentConfig(
        response_modalities=["IMAGE", "TEXT"]
    ),
)
# Image bytes are in: response.candidates[0].content.parts[0].inline_data.data
# MIME type: response.candidates[0].content.parts[0].inline_data.mime_type
```

**Alternatives considered**:
- Google ADK `Agent` + `Runner`: Rejected — overkill for a stateless image call; adds session management overhead.
- `google-generativeai` legacy client (`genai.configure`, `genai.GenerativeModel`): Rejected — the project already uses the newer `google.genai` client (via ADK's internal imports); mixing both would create confusion.

---

## Decision 2: Paragraph Assessment (Text → JSON)

**Decision**: Use Google ADK `Agent`/`Runner` (same pattern as `chapter_scribe.py`) for paragraph assessment, since the project already has the helper `_run_agent` pattern established.

**Rationale**: Assessment is a text-in / structured-text-out call. The existing `chapter_scribe._run_agent` abstraction handles streaming, session management, and final-response extraction. Replicating this pattern for the assessor keeps the codebase consistent and avoids a direct API call for text generation (which the existing code has already abstracted). The response will be JSON — extracted with `json.loads()` after stripping markdown fences if present.

**Alternatives considered**:
- Direct `google.genai` call for text: Would work, but inconsistent with existing text-generation pattern.
- Pydantic structured outputs / function calling: Considered but the project doesn't currently use this pattern; keeping the simple JSON-in-text approach matches existing code style.

---

## Decision 3: Image Storage

**Decision**: Store image bytes in a new PostgreSQL `chapter_illustrations` table using a `LargeBinary` (bytea) column.

**Rationale**: The project is a prototype using a single PostgreSQL container. Storing images in the DB avoids introducing a new file-system dependency (no need to configure static file mounts, shared volumes, or S3). Typical illustration images will be small (under 500KB each) and there will be at most ~10 per chapter, making bytea storage viable at prototype scale.

**Alternatives considered**:
- Disk files in `static/illustrations/`: Requires filesystem path management, Docker volume mounts, and a cleanup strategy. Rejected per constitution's simplicity principle.
- Base64 in an existing column: Rejected — bloats existing tables with unrelated binary data.
- Object storage (S3, GCS): Rejected — adds external dependency inappropriate for a local prototype.

---

## Decision 4: Timing of Illustration Generation

**Decision**: Trigger illustration generation as a chained background task immediately after `create_chapter()` succeeds (within the existing `_draft_chapter_bg` background task in `chapters.py` router).

**Rationale**: The existing chapter generation flow already uses a background task pattern. Adding illustration generation as a sequential follow-on step in the same background task is the simplest change — no new polling endpoint needed for illustration status (illustrations appear when the chapter re-renders after generation). If illustration generation fails, the chapter still renders without images (FR-007).

**Alternatives considered**:
- Separate background task triggered by client: Requires a new polling mechanism; adds complexity.
- On-demand generation at render time: Would delay initial page load significantly; rejected.
- Separate webhook/event: Over-engineered for a prototype.

---

## Decision 5: Image Serving

**Decision**: Add a new FastAPI endpoint `GET /chapters/{chapter_id}/illustrations/{paragraph_index}` that reads image bytes from the DB and returns a `Response` with the correct `Content-Type`.

**Rationale**: Direct DB-served images keep the architecture simple. The endpoint is fast for small images (< 1MB). Templates embed `<img src="/chapters/{id}/illustrations/{n}">` tags.

**Alternatives considered**:
- Serve as base64 data URIs embedded in HTML: Bloats HTML page significantly; rejected.
- Serve from static file directory: Requires file system management; rejected (see Decision 3).

---

## Decision 6: Rendering Position

**Decision**: Images are rendered **below** the paragraph they illustrate, within the existing `<div class="chapter-paragraph">` container, using a new Jinja2 template fragment. The illustration dict (mapping paragraph index → illustration URL) is passed to the template from the router.

**Rationale**: "Below" is simpler to implement than a side-by-side float layout, avoids CSS complexity, and degrades gracefully when no image exists (the paragraph just ends at the text). Side-by-side layout is explicitly deferred per the spec's assumption about mobile/responsive layout.

---

## Decision 7: Assessment Model

**Decision**: Use the existing `settings.gemini_model` (the text generation model, e.g., `gemini-3-flash-preview`) for paragraph assessment. Do **not** add a second configurable model for assessment.

**Rationale**: Assessment is a lightweight text task. Sharing the text model avoids adding a second `.env` variable for a secondary model, keeping configuration minimal (constitution principle III: simplicity). Only the image generation model needs to be separately configurable per the spec.

---

## Resolved Unknowns

| Unknown | Resolution |
|---------|------------|
| Which Gemini API to call for images | `client.aio.models.generate_content` with `response_modalities=["IMAGE"]` |
| Where to store images | PostgreSQL `bytea` via new `chapter_illustrations` table |
| When to run illustration pipeline | Chained within existing `_draft_chapter_bg` background task |
| How to serve images | New `GET /chapters/{id}/illustrations/{n}` endpoint |
| How to pass illustrations to template | Router fetches illustration index dict; passes to template context |
| Assessment model | Reuse `settings.gemini_model` (text model) |
| JSON extraction from LLM response | `json.loads()` with markdown fence stripping; treat parse errors as `requires_image=False` |

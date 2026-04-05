# Quickstart: Lesson Illustrations

**Feature**: 008-lesson-illustrations  
**Date**: 2026-04-04

---

## What This Feature Does

After a chapter is generated, the system automatically:
1. Assesses each paragraph to decide if it needs an illustration.
2. Generates images for paragraphs that benefit from them using a configurable Gemini image model.
3. Stores images in the database and renders them inline in the chapter view.

---

## Configuration

Add to your `.env` file:

```env
# Image generation model for lesson illustrations (default shown below)
ILLUSTRATION_MODEL=gemini-3.1-flash-image-preview
```

The `GOOGLE_API_KEY` you already have configured is used for both text assessment and image generation.

---

## How It Works End-to-End

```
Student requests chapter generation
        │
        ▼
Chapter Scribe generates markdown content
        │
        ▼
Chapter saved to DB
        │
        ▼  (background task, non-blocking)
Illustration pipeline runs:
  ├── Split chapter content into paragraphs (by \n\n)
  ├── For each paragraph:
  │     ├── Call text model → JSON assessment (requires_image + image_description)
  │     └── If requires_image:
  │           └── Call illustration model → image bytes → save to chapter_illustrations table
  └── Done (errors logged, never surfaced to student)
        │
        ▼
Student views chapter
  ├── Template fetches illustration index for chapter
  └── Each para-N renders its text + <img> if an illustration exists
```

---

## Key Files

| Path | Purpose |
|------|---------|
| `packages/documentlm-core/src/documentlm_core/config.py` | Add `illustration_model` setting |
| `packages/documentlm-core/src/documentlm_core/db/models.py` | Add `ChapterIllustration` ORM model |
| `packages/documentlm-core/src/documentlm_core/schemas.py` | Add `ParagraphAssessment`, `IllustrationRead` |
| `packages/documentlm-core/src/documentlm_core/agents/illustration_assessor.py` | LLM assessment logic |
| `packages/documentlm-core/src/documentlm_core/agents/image_generator.py` | Gemini image generation call |
| `packages/documentlm-core/src/documentlm_core/services/illustration.py` | Orchestrate assess→generate→persist |
| `packages/documentlm-core/src/documentlm_core/alembic/versions/xxx_add_chapter_illustrations.py` | DB migration |
| `apps/api/src/api/routers/chapters.py` | Trigger pipeline, add image endpoint |
| `apps/api/src/api/templates/chapters/detail.html` | Render images alongside paragraphs |
| `apps/api/src/api/templates/chapters/_inline.html` | Render images in syllabus inline view |

---

## Running Tests

```bash
cd src
# Unit tests (no live API calls — all LLM calls mocked)
pytest packages/documentlm-core/tests/unit/test_illustration_assessor.py -v
pytest packages/documentlm-core/tests/unit/test_image_generator.py -v
pytest packages/documentlm-core/tests/unit/test_illustration_service.py -v

# Integration tests (requires running PostgreSQL)
pytest packages/documentlm-core/tests/integration/test_illustration_db.py -v

# Full suite
pytest
```

---

## Applying the Migration

```bash
cd src
uv run alembic -c packages/documentlm-core/alembic.ini upgrade head
```

---

## Verifying the Feature

1. Start the stack as usual (`docker compose up`).
2. Generate a new chapter for any topic.
3. Wait a few seconds after generation completes.
4. Reload the chapter view — paragraphs covering concrete concepts should display illustrations below their text.
5. Check logs for `illustration` entries at `INFO` and `DEBUG` level.

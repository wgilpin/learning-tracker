# Contract: Illustration Image Endpoint

**Feature**: 008-lesson-illustrations  
**Date**: 2026-04-04

---

## `GET /chapters/{chapter_id}/illustrations/{paragraph_index}`

Serves the raw image bytes for the illustration associated with a specific paragraph of a chapter.

### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `chapter_id` | UUID | The chapter owning the illustration |
| `paragraph_index` | integer | 1-based paragraph position (matches `para-N` anchor) |

### Responses

| Status | Content-Type | Body | Condition |
|--------|-------------|------|-----------|
| `200 OK` | `image/png` or `image/jpeg` (from DB) | Raw image bytes | Illustration found |
| `404 Not Found` | `application/json` | `{"detail": "Illustration not found"}` | No illustration for this chapter/paragraph |

### Notes

- No request body.
- Authentication follows the existing session-based auth guard applied to all routes.
- The endpoint is read-only; illustration creation happens server-side as part of chapter generation.
- `Content-Type` is set to the value stored in `image_mime_type` for the record.

### Template Usage

Templates reference this endpoint as:

```html
<img
  src="/chapters/{{ chapter.id }}/illustrations/{{ loop.index }}"
  alt="{{ illustration.image_description }}"
  class="chapter-illustration"
/>
```

The router passes an `illustrations` dict (`{paragraph_index: IllustrationRead}`) to the template. The template checks `loop.index in illustrations` before rendering the `<img>` tag.

---

## Internal Pipeline (not a public HTTP contract)

The following describes the internal data flow — not exposed as an HTTP API.

### Paragraph Assessment Prompt

Input:
```
As part of an educational system, your job is to decide if a given piece of text
would be enhanced by the addition of a small illustration. Assess the following
text and respond with a json record containing a boolean flag, "requires_image",
set to true or false, and a field "image_description", string, which is a clear
description of the image that will be used by the illustrator.
<lesson text>
{paragraph_title} {paragraph_text}
</lesson text>
```

Expected output (raw JSON, may be wrapped in markdown fences):
```json
{"requires_image": true, "image_description": "A diagram showing ..."}
```

### Image Generation Prompt

Input:
```
For use in an academic textbook, create the following as a simple image only,
no background, no descriptive text. {image_description}
```

Model: `settings.illustration_model` (default: `gemini-3.1-flash-image-preview`)  
Response modalities: `["IMAGE", "TEXT"]`  
Expected response: binary image bytes in `response.candidates[0].content.parts[0].inline_data`

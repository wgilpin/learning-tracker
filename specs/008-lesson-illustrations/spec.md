# Feature Specification: Lesson Illustrations

**Feature Branch**: `008-lesson-illustrations`  
**Created**: 2026-04-04  
**Status**: Draft  
**Input**: User description: "We need to add illustrations to the lessons. For each paragraph in the generated text run an AI prompt to decide if it needs an illustration, then generate the illustration using gemini-3.1-flash-image-preview and place it alongside the text. Image model name needs to be configurable via .env"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Student Views Illustrated Lesson (Priority: P1)

A student opens a generated lesson and sees relevant illustrations displayed alongside paragraphs that benefit from visual support. The illustrations are simple academic-style images with no background or descriptive text overlay, integrated naturally into the lesson layout.

**Why this priority**: The core value of the feature — enriched visual comprehension — is only delivered when a student successfully sees illustrations embedded in lesson content.

**Independent Test**: Navigate to any generated lesson page and verify that paragraphs assessed as needing illustrations render with a corresponding image directly adjacent to the paragraph text.

**Acceptance Scenarios**:

1. **Given** a lesson has been generated with multiple paragraphs, **When** a student opens the lesson, **Then** paragraphs that were assessed as benefiting from illustration each display a relevant image alongside their text.
2. **Given** a paragraph was assessed as not requiring an illustration, **When** a student views that paragraph, **Then** no image placeholder or gap appears — the paragraph renders as plain text only.
3. **Given** the lesson page loads, **When** images are present, **Then** each image appears visually adjacent to (beside or immediately below) the paragraph it illustrates.

---

### User Story 2 - Lesson Renders Gracefully When Image Generation Fails (Priority: P2)

If the image generation service is unavailable or returns an error for a specific paragraph, the lesson still renders completely with all text content intact. Affected paragraphs simply display without an illustration rather than blocking the entire lesson.

**Why this priority**: Reliability of lesson delivery must not be contingent on the availability of a third-party image generation service. Content is always shown to the student.

**Independent Test**: Simulate an image generation failure for one paragraph and confirm the lesson renders fully with the remaining paragraphs (illustrated or not) and the failed paragraph shows only its text.

**Acceptance Scenarios**:

1. **Given** the image generation service is unavailable, **When** a lesson is rendered, **Then** all paragraph text is still displayed and no error is shown to the student.
2. **Given** image generation fails for one paragraph out of several, **When** the lesson renders, **Then** successfully illustrated paragraphs display their images and the failed paragraph displays text only.

---

### User Story 3 - Developer Configures Image Model via Environment (Priority: P3)

A developer can change which image generation model is used for illustration generation by updating a single environment variable, without modifying any application code. The default model is `gemini-3.1-flash-image-preview`.

**Why this priority**: Enables future model upgrades, cost optimisation, or environment-specific overrides without code changes.

**Independent Test**: Set the image model environment variable to a different valid model name, generate a lesson, and confirm that illustrations are produced (indicating the configured model was used).

**Acceptance Scenarios**:

1. **Given** the image model environment variable is set, **When** the system generates illustrations, **Then** the specified model is used for all image generation in that session.
2. **Given** the image model environment variable is not set, **When** the system generates illustrations, **Then** the default model (`gemini-3.1-flash-image-preview`) is used.

---

### Edge Cases

- What happens when every paragraph in a lesson is assessed as not requiring an illustration? The lesson renders as plain text with no errors or visual gaps.
- What happens when the illustration assessment returns malformed or non-JSON output? The system treats the paragraph as not requiring an illustration and continues.
- What happens when a lesson has a very large number of paragraphs? Image assessments and generations for paragraphs not needing images are skipped; only paragraphs requiring images incur generation cost.
- What happens when an image description is empty or too vague for generation? The generation step is skipped for that paragraph and the text is shown alone.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST assess each paragraph (title + body text) of a generated lesson individually to determine whether it would benefit from an illustration.
- **FR-002**: The assessment MUST produce a structured result with a boolean indicating whether an image is required and, when true, a clear description suitable for an illustrator.
- **FR-003**: System MUST generate an illustration only for paragraphs where the assessment indicates an image is required.
- **FR-004**: Generated illustrations MUST be simple academic-style images: no background, no descriptive text overlaid on the image.
- **FR-005**: System MUST place each generated illustration visually adjacent to the paragraph it was generated for in the rendered lesson content.
- **FR-006**: System MUST allow the image generation model to be specified via an environment variable, with `gemini-3.1-flash-image-preview` as the default.
- **FR-007**: System MUST NOT prevent lesson rendering if image assessment or generation fails for any paragraph — text content is always shown.
- **FR-008**: Paragraphs assessed as not requiring an illustration MUST render without any image placeholder or visual gap.

### Key Entities

- **Paragraph**: A discrete section of lesson content with a title and body text, the unit against which illustration assessment is performed.
- **Illustration Assessment**: The result of evaluating a paragraph — a boolean (`requires_image`) and a textual description (`image_description`) used to drive image generation.
- **Generated Illustration**: An image produced for a specific paragraph, stored or referenced so it can be embedded in the rendered lesson.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 80% of lessons containing conceptual or procedural content include at least one illustration after the feature is live.
- **SC-002**: Lesson pages with illustrations load and render completely within an acceptable time (no more than 5 seconds longer than a lesson without illustrations under normal network conditions).
- **SC-003**: Illustration generation failures never prevent a student from reading lesson text — 100% of lesson page loads succeed regardless of image service availability.
- **SC-004**: Developers can switch the active image model by changing a single environment variable with no code changes required.

## Assumptions

- Generated lessons are already structured into discrete paragraphs (each with a title and body text) before illustration processing begins.
- The image generation model API is accessible from the application environment and requires an API key already provisioned.
- Illustrations are generated at lesson-render time or as a post-generation step; caching of generated images is out of scope for this feature but may be added later.
- The rendering layer (HTMX/Jinja2 templates) supports embedding inline images returned from the generation service.
- Image storage (where generated images are held before being served) follows the existing pattern used elsewhere in the project for binary assets.
- Mobile/responsive layout for image placement is out of scope for v1; images are placed inline with paragraph text.

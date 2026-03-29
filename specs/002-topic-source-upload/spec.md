# Feature Specification: Topic Source Upload

**Feature Branch**: `002-topic-source-upload`
**Created**: 2026-03-29
**Status**: Draft
**Input**: User description: "During topic description, allow user upload of sources - pdfs, urls for scraping, youtube links for transcript download via youtube-transcript-api, raw text paste. These are downloaded/extracted then saved as sources just like any other source. These should be treated as the primary sources. For example if a user uploads a syllabus, that is exactly the one our syllabus needs to follow and we dont need to make up a new syllabus. Only once these are added do we search for more."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upload PDF Sources During Topic Creation (Priority: P1)

A user creating a new topic can attach one or more PDF files before submitting. The system extracts text content from each PDF and saves each as a source record flagged as primary. If a PDF is a course syllabus, the system uses it as the authoritative syllabus rather than generating one.

**Why this priority**: PDFs are the most common form of structured academic material (syllabi, textbooks, papers). This is the highest-value upload path and anchors the concept of user-provided primary sources.

**Independent Test**: Can be tested by creating a topic, uploading a PDF syllabus, and verifying that the extracted text is saved as a primary source and reflected in the topic's generated content without modification to the syllabus structure.

**Acceptance Scenarios**:

1. **Given** a user is on the topic creation form, **When** they attach a PDF file, **Then** the file is accepted, text is extracted, and a source record is created and marked as primary.
2. **Given** a primary PDF source contains a syllabus, **When** the topic's content is generated, **Then** the system uses that syllabus structure exactly rather than generating its own.
3. **Given** a user uploads a PDF that cannot be parsed, **When** the upload is processed, **Then** the user sees a clear error message and the topic creation is not blocked.

---

### User Story 2 - Provide URLs for Scraping During Topic Creation (Priority: P1)

A user creating a new topic can paste one or more URLs. The system fetches and scrapes the text content from each URL, saves each as a primary source, and uses the scraped content as authoritative material during content generation.

**Why this priority**: URLs are easy to provide and cover a wide range of reference material (course pages, documentation, articles). They complement PDFs as the second most common source type.

**Independent Test**: Can be tested by creating a topic, entering a URL pointing to a course outline page, and confirming the scraped text is stored as a primary source and visible in the topic's source list.

**Acceptance Scenarios**:

1. **Given** a user provides a valid URL, **When** the topic is submitted, **Then** the system fetches and stores the page's text content as a primary source.
2. **Given** a URL is unreachable or returns an error, **When** the system attempts to scrape it, **Then** the user is notified and the topic creation proceeds with the remaining sources.
3. **Given** a URL is provided, **When** the content is scraped, **Then** the source record stores the original URL alongside the extracted text.

---

### User Story 3 - Provide YouTube Links for Transcript Extraction (Priority: P2)

A user creating a new topic can paste one or more YouTube video URLs. The system downloads the transcript for each video, saves the transcript as a primary source, and uses it during content generation.

**Why this priority**: YouTube lectures and tutorials are valuable learning resources. Transcripts provide rich text-based content. Lower priority than PDFs/URLs because not all topics have relevant video content and transcript availability is not guaranteed.

**Independent Test**: Can be tested by providing a YouTube URL for a lecture video, verifying the transcript is retrieved and stored as a primary source, and confirming it is referenced during content generation.

**Acceptance Scenarios**:

1. **Given** a user provides a YouTube URL with an available transcript, **When** the topic is submitted, **Then** the transcript is extracted and saved as a primary source.
2. **Given** a YouTube video has no available transcript, **When** the system attempts extraction, **Then** the user is notified that no transcript is available; the source is skipped and topic creation continues.
3. **Given** a YouTube URL is provided, **When** the source is saved, **Then** the record includes the video URL, video title (if retrievable), and the full transcript text.

---

### User Story 4 - Paste Raw Text During Topic Creation (Priority: P2)

A user creating a new topic can paste arbitrary text directly into the form (e.g., a course description, a list of learning objectives, or notes). The system saves this text as a primary source and uses it as authoritative input during content generation.

**Why this priority**: Raw text paste is the lowest-friction input method and covers cases where users have content that does not come from a file or URL. It complements the other upload paths without requiring any external fetch.

**Independent Test**: Can be tested by entering raw text in the source text area, submitting the topic, and verifying a primary source record is created containing exactly the pasted text.

**Acceptance Scenarios**:

1. **Given** a user enters text in the raw text input, **When** the topic is submitted, **Then** a primary source record is created containing that exact text.
2. **Given** a user submits the topic with no text in the raw text field, **When** the form is processed, **Then** no empty source record is created.

---

### User Story 5 - Primary Sources Take Precedence Before Additional Search (Priority: P1)

Once user-provided sources are saved, the system treats them as the authoritative foundation for content generation. The system only searches for additional sources after all user-provided sources have been processed. Agents and content generators must consult primary sources first and must not contradict or replace content defined in them.

**Why this priority**: This is the defining behavior of the feature. Without it, the upload capability has no meaningful effect — users would upload a syllabus but still get a generated one.

**Independent Test**: Can be tested by providing a syllabus as a primary source and confirming the generated chapter structure matches the syllabus exactly, with any supplemental search results only filling in gaps rather than replacing the provided structure.

**Acceptance Scenarios**:

1. **Given** one or more primary sources have been added to a topic, **When** content generation begins, **Then** primary sources are processed and used before any external search is triggered.
2. **Given** exactly one primary source defines a syllabus or chapter structure, **When** the topic's chapters are generated, **Then** the generated structure matches that source exactly. **Given** multiple primary sources each define a syllabus, **When** the topic's chapters are generated, **Then** the system produces a single coherent structure synthesized from all of them, not a verbatim copy of any one nor a flat union of all.
3. **Given** primary sources are present, **When** additional sources are searched, **Then** search results are used only to supplement gaps not covered by primary sources.
4. **Given** no primary sources are provided, **When** the topic is created, **Then** the system proceeds with its normal search-first approach unchanged.

---

### Edge Cases

- What happens when a PDF is password-protected and cannot be extracted?
- What happens when a YouTube video's transcript is in a different language than the topic?
- What happens when a URL scrape returns only JavaScript (no static content)?
- What happens when a user provides more than one document defining a syllabus — how are they synthesized?
- What happens when a raw text paste is extremely long?
- Duplicate sources (same URL or identical text added twice) are silently deduplicated — only one copy is kept and a brief notice is shown to the user.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to attach one or more PDF files during topic creation before submitting. Each PDF MUST be no larger than 50MB; files exceeding this limit MUST be rejected with a clear error message.
- **FR-002**: Users MUST be able to enter one or more URLs during topic creation for content scraping.
- **FR-003**: Users MUST be able to enter one or more YouTube video URLs during topic creation for transcript extraction.
- **FR-004**: Users MUST be able to paste raw text directly into the topic creation form as a source.
- **FR-005**: The system MUST extract text content from each provided PDF and store it as a source record.
- **FR-006**: The system MUST scrape and extract text content from each provided URL and store it as a source record.
- **FR-007**: The system MUST retrieve the transcript for each provided YouTube URL and store it as a source record.
- **FR-008**: Each user-provided source MUST be saved with a flag indicating it is a primary source, distinguishing it from sources discovered through search.
- **FR-018**: If a user adds a source whose URL or text content is identical to one already added, the system MUST silently discard the duplicate and display a brief notice; only one copy is retained.
- **FR-009**: During content generation, the system MUST consult primary sources before initiating any external search for additional material.
- **FR-010**: When exactly one primary source defines a syllabus or chapter structure, the system MUST use it as-is without regeneration. When multiple primary sources each define a syllabus, an AI agent MUST read all of them and generate a single unified structure that resolves overlaps and fills gaps — not a verbatim copy of any one source and not a flat union of all chapters.
- **FR-011**: External source search MUST only be triggered after all user-provided sources have been processed.
- **FR-012**: Each source MUST be extracted immediately when added; the result (extracted text or error) MUST be displayed inline before the user submits the form. If a source fails to process, the user MUST be shown the error inline and MUST be able to remove the failing source or proceed anyway.
- **FR-015**: The topic submit action MUST only be available once all added sources have finished processing (succeeded or failed) — the form must not allow submission while any extraction is in progress.
- **FR-013**: The topic creation flow MUST allow users to add multiple sources across different types before submitting.
- **FR-014**: Users MUST be able to submit a topic with no user-provided sources, preserving the existing search-first behavior.
- **FR-016**: Users MUST be able to add new primary sources to an existing topic from the topic detail page, using the same input types (PDF, URL, YouTube, raw text) available at creation.
- **FR-017**: Users MUST be able to remove a primary source from a topic after creation.

### Key Entities

- **Source**: Represents a piece of content associated with a topic. Has a type (pdf, url, youtube, raw text), extracted text content, original reference (file name, URL, or video URL), and a flag indicating whether it is a primary (user-provided) source.
- **Topic**: The subject being studied. Can have zero or more primary sources attached at creation time.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can add at least one source of any supported type during topic creation without leaving the topic creation form.
- **SC-002**: 100% of successfully processed user-provided sources are saved as primary source records when topic creation succeeds.
- **SC-003**: When a primary source defines a syllabus or chapter structure, the generated topic content matches that structure with no structural divergence.
- **SC-004**: External source search is never initiated before all user-provided sources have been processed.
- **SC-005**: Users receive a clear notification for each source that fails to process, within the topic creation flow, without blocking completion.
- **SC-006**: Topic creation with up to 5 user-provided sources completes without requiring the user to wait through an unresponsive UI.

## Clarifications

### Session 2026-03-29

- Q: When does source extraction happen relative to form submission? → A: Immediately on add, before form submit — each source shows inline success/error feedback before the user submits the topic.
- Q: Can users add or remove primary sources after topic creation? → A: Yes — users can add and remove primary sources from the topic detail page at any time after creation.
- Q: How are multiple user-provided syllabi synthesized? → A: An AI agent reads all provided syllabi and generates a single unified structure, resolving overlaps and gaps.
- Q: How should duplicate sources be handled? → A: Silently deduplicate — keep only one copy and show a brief notice to the user.
- Q: What is the maximum PDF file size? → A: 50MB per file.

## Assumptions

- The existing source model stores extracted text content; a boolean or status field can be added to distinguish primary (user-provided) sources from secondary (searched) sources.
- PDFs are expected to contain extractable text and must not exceed 50MB; scanned image-only PDFs may not yield useful content in the initial version.
- URL scraping uses basic HTTP fetch and text extraction; JavaScript-heavy single-page applications may yield incomplete content, which is acceptable for v1.
- YouTube transcript availability depends on the video's captions; the system will not generate transcripts for videos that have none.
- When multiple user-provided sources each define a syllabus, an AI agent reads all of them and generates a unified structure resolving overlaps and gaps — not a simple union and not first-wins.
- The topic creation UI is a single form or wizard; source uploads happen within that flow before the final submit action.
- Users are authenticated; anonymous source upload is out of scope.
- Source extraction (PDF parsing, URL scraping, transcript download) is triggered immediately when the user adds each source, before the topic form is submitted. Each source displays inline success or error feedback. The topic submit action is only available once all added sources have been processed (or failed).

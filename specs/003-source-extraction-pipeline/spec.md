# Feature Specification: Source Extraction Pipeline

**Feature Branch**: `003-source-extraction-pipeline`
**Created**: 2026-03-29
**Status**: Draft
**Input**: User description: "All sources found are to be processed in a similar way, with text extraction and indexing, then that content is used as context for the lesson generation agents. This includes the sources found as part of the lesson generation flow."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Lesson Content Is Grounded in Actual Source Material (Priority: P1)

When a user's topic has sources — whether uploaded by the user or discovered by the system during generation — the chapter written for each syllabus item draws on the actual text of those sources, not just their titles or bibliographic metadata. The chapter reads as if the agent has read the material, not just found it.

**Why this priority**: This is the core value proposition of the whole system. Without grounding lesson content in source text, agents produce generic output indistinguishable from asking an LLM to improvise. Accurate, grounded content is the defining quality signal.

**Independent Test**: Can be tested by providing a source with specific unique facts (e.g., a document describing a fictional process) and verifying those facts appear in the generated chapter — facts that the agent could not have invented.

**Acceptance Scenarios**:

1. **Given** a topic has one or more sources with extractable content, **When** a chapter is generated for any syllabus item, **Then** the chapter's content reflects material from those sources.
2. **Given** a topic has sources discovered during the generation flow, **When** those sources are processed, **Then** their extracted text is available to the chapter-writing agent before it writes.
3. **Given** a source whose content cannot be extracted (e.g., paywalled, image-only), **When** the pipeline processes it, **Then** the source row shows a FAILED badge, the agent uses the remaining indexed sources, and chapter generation is not blocked.

---

### User Story 2 - All Source Types Are Processed the Same Way (Priority: P1)

Regardless of how a source entered the system — uploaded by the user as a PDF or URL, provided as a YouTube link or raw text, or discovered by the system via search — it goes through the same extraction and indexing steps before being used by agents. A user does not need to think about whether their source "type" affects the quality of the generated lesson.

**Why this priority**: Consistency of processing is foundational. If some sources are used as context and others are ignored, the output quality becomes unpredictable and the system behaviour is confusing to reason about.

**Independent Test**: Can be tested by adding one source of each type (user-uploaded PDF, search-discovered URL, YouTube transcript) to a topic, generating a chapter, and confirming content from all three appears in the output.

**Acceptance Scenarios**:

1. **Given** a user-uploaded PDF source, **When** the pipeline runs, **Then** text is extracted and indexed the same as any other source type.
2. **Given** a URL source discovered during the search phase, **When** the pipeline runs, **Then** its text is scraped, extracted, and indexed before the chapter agent writes.
3. **Given** a YouTube transcript source, **When** the pipeline runs, **Then** the transcript text is indexed and available to agents.
4. **Given** a raw-text source, **When** the pipeline runs, **Then** the pasted text is indexed directly with no additional processing step.

---

### User Story 3 - Agents See Relevant Source Content, Not Everything (Priority: P2)

When generating a chapter for a specific syllabus item, the agent receives the most relevant portions of available sources — not the full text of every source indiscriminately. This keeps the agent's context focused and the output coherent.

**Why this priority**: Topics may have many sources with large amounts of text. Passing all extracted text verbatim to every agent call would exceed context limits and dilute relevance. Scoped retrieval makes output better and the system more robust.

**Independent Test**: Can be tested by adding a large multi-section source and verifying that the chapter for section A cites material from section A, and the chapter for section B cites material from section B — demonstrating that retrieval is scoped to the syllabus item.

**Acceptance Scenarios**:

1. **Given** a source with content covering multiple distinct topics, **When** a chapter is generated for a specific syllabus item, **Then** the context provided to the agent contains the portions of the source most relevant to that item.
2. **Given** many sources with large total text, **When** a chapter is generated, **Then** the agent receives a bounded, relevant excerpt rather than the full corpus.

---

### User Story 4 - Previously Extracted Content Is Not Re-Extracted (Priority: P2)

When a source has already been extracted and indexed, re-triggering chapter generation (e.g., regenerating a chapter) does not re-fetch or re-extract its content. The pipeline is idempotent with respect to extraction.

**Why this priority**: Re-extraction on every agent call would be slow and wasteful. Users expect fast chapter regeneration once sources are in place.

**Independent Test**: Can be tested by logging extraction calls and verifying that generating the same chapter twice results in exactly one extraction event per source.

**Acceptance Scenarios**:

1. **Given** a source whose content has already been extracted and indexed, **When** a chapter is regenerated, **Then** no new extraction request is made for that source.
2. **Given** a source that was added after initial generation, **When** a chapter is generated, **Then** the new source is extracted and indexed before the agent writes.

---

### Edge Cases

- What happens when a source's URL is no longer accessible at extraction time (was valid when discovered)?
- What happens when extracted content is in a different language than the topic?
- What happens when the total indexed content for a topic is very large — how is relevance scoped per chapter?
- What happens when re-indexing is triggered for a source whose content has not changed?
- How does the pipeline handle sources with near-zero extractable text (e.g., a page with only an image and a caption)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every source, regardless of type or how it was added, MUST be extracted and embedded as a background task immediately when it is added or discovered — not deferred to chapter generation time.
- **FR-002**: The extraction process MUST be the same pipeline for all source types: user-uploaded PDFs, user-provided URLs, user-provided YouTube links, user-pasted raw text, and search-discovered URLs and PDFs.
- **FR-003**: Extracted source content MUST be chunked and each chunk upserted into a ChromaDB collection, which handles embedding and storage. The source's ID MUST be stored as chunk metadata for traceability.
- **FR-004**: When generating a chapter, the system MUST query ChromaDB for the top 10 most similar chunks to the syllabus item's title and description — approximately 5,000 characters of source context passed to the agent per call.
- **FR-005**: The pipeline MUST be idempotent: a source whose content has already been extracted and indexed MUST NOT be re-extracted on subsequent chapter generation calls.
- **FR-006**: If a source's content cannot be extracted (unreachable, empty, unsupported format), the pipeline MUST log the failure, mark the source status as FAILED, and continue with the remaining sources — chapter generation MUST NOT be blocked.
- **FR-009**: Each source row in the UI MUST display a status badge reflecting the current extraction state: PENDING (awaiting processing), INDEXED (ready), or FAILED (with a brief reason).
- **FR-007**: Search-discovered sources MUST go through the same extraction and indexing pipeline as user-provided sources before their content is used in chapter generation.
- **FR-008**: The content available to agents MUST reflect the actual text of sources, not just titles, URLs, or metadata.

### Key Entities

- **Source**: Represents any piece of content associated with a topic. Has a type, a reference (URL, file name, or none for raw text), extracted text content, and an index status indicating whether it has been extracted and indexed.
- **Source**: Has an extraction status with three states: `PENDING` (not yet processed), `INDEXED` (extracted and embedded successfully), `FAILED` (extraction or embedding could not complete). Transitions: PENDING → INDEXED or PENDING → FAILED.
- **Source Chunk**: A fixed-size (~500 character) portion of a source's extracted text, stored in ChromaDB (which manages the embedding). Each chunk carries the source ID as metadata. Retrieval is a ChromaDB similarity query against the syllabus item title and description.
- **Chapter Generation Context**: The set of relevant source excerpts assembled for a specific syllabus item before the chapter-writing agent is called.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of sources with extractable content have their text stored and indexed before chapter generation begins.
- **SC-002**: Generated chapters for topics with sources contain material that can be traced back to at least one source — measurable by fact-checking against source content in tests.
- **SC-003**: Re-generating a chapter for a topic with already-indexed sources produces output in no more time than a first generation — extraction does not re-run.
- **SC-004**: Sources that fail extraction are marked as such within the pipeline run; chapter generation proceeds with zero additional user intervention.
- **SC-005**: Each chapter generation call receives at most 10 source chunks (~5,000 characters total) as context; no call exceeds this bound regardless of how many sources a topic has.

## Clarifications

### Session 2026-03-29

- Q: How should relevant source portions be retrieved per syllabus item? → A: Vector embeddings — chunks are embedded; retrieval uses cosine similarity. Embedding support to be added to nlp_utils (using litellm, which is already a dependency).
- Q: What is the agent context size bound? → A: Top 10 chunks of ~500 characters each (~5,000 characters total) per chapter generation call.
- Q: When does extraction/embedding run? → A: Eagerly — as a background task immediately when a source is added or discovered, not deferred to chapter generation time.
- Q: What does the user see for extraction status? → A: A per-source status badge on each source row showing pending / indexed / failed.
- Q: How are chunks embedded and stored for retrieval? → A: Via ChromaDB — ChromaDB manages the embedding model, chunk storage, and cosine similarity retrieval. No embedding function is added to nlp_utils.

## Assumptions

- All source types (PDF, URL, YouTube, raw text, search-discovered) share a single unified extraction pipeline; there is no separate fast or slow path by type.
- Indexing means chunking extracted text (via nlp_utils) and upserting each chunk into ChromaDB, which manages embedding model selection, vector storage, and similarity search.
- "Relevant portions" are retrieved by querying ChromaDB with the syllabus item's title and description as the query text; ChromaDB handles the embedding and ranking.
- Sources found during the search flow (e.g., ArXiv, YouTube search) are considered part of the same extraction pipeline as user-provided sources; the distinction is only in how they were added, not in how they are processed.
- Extraction failures do not block lesson generation; the system degrades gracefully with fewer sources.
- Content re-extraction is detected by checking whether a source already has stored content; no external cache or event log is required.
- This feature depends on Feature 002 (Topic Source Upload) for the user-provided source intake mechanism; this feature generalises the processing to all sources.

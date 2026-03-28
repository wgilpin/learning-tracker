# Feature Specification: Academic Learning Tracker App

**Feature Branch**: `001-academic-learning-tracker`
**Created**: 2026-03-28
**Status**: Draft
**Input**: User description: "the app as per docs/overview.md"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Topic Initialisation & Syllabus Generation (Priority: P1)

A learner wants to master a complex subject (e.g. "Transformer Architecture in Deep Learning").
They supply the topic name and the system produces a prerequisite-aware, hierarchical syllabus —
a checklist of concepts ordered so that foundational nodes always precede advanced ones. The
learner reviews the generated syllabus before any content is drafted.

**Why this priority**: Without a syllabus the rest of the system cannot function. This is the
entry point for every learning session and the highest-value interaction.

**Independent Test**: A user supplies a topic; the system returns a structured syllabus with at
least two dependency levels and no circular prerequisites. No chapter content is written yet.

**Acceptance Scenarios**:

1. **Given** a user provides a topic name, **When** they request syllabus generation, **Then**
   the system returns a hierarchical list of concepts with prerequisite relationships indicated.
2. **Given** the generated syllabus, **When** the user reviews it, **Then** every concept node
   has a valid set of prerequisite nodes (no cycles, no self-references).
3. **Given** a broad topic, **When** the syllabus is generated, **Then** the system identifies
   and surfaces bottleneck concepts — those that unlock the most downstream nodes.

---

### User Story 2 — Targeted Chapter Drafting (Priority: P2)

With a syllabus in place, the learner selects a single unblocked concept node and requests a
deep-dive chapter. The system drafts a chapter for that node only, using verified academic
sources. Context from previously completed chapters arrives as summaries rather than full text,
keeping the explanation coherent without overwhelming the source budget.

**Why this priority**: Chapter generation per node is the core value proposition — it turns the
syllabus from a plan into a living document.

**Independent Test**: Select an unblocked syllabus node → system produces a chapter with inline
citations. The chapter references prerequisite context coherently without duplicating it.

**Acceptance Scenarios**:

1. **Given** a syllabus node whose prerequisites are all `Mastered` or `In Progress`, **When**
   the user requests a chapter draft, **Then** the system produces a focused explanation with
   at least one cited verified source per key claim.
2. **Given** a node whose direct prerequisite is `Unresearched`, **When** the user attempts to
   draft it, **Then** the system blocks the request and names the unsatisfied prerequisites.
3. **Given** one or more previously drafted chapters exist, **When** drafting a dependent
   chapter, **Then** the agent receives concise summaries of prior chapters, not their full text.

---

### User Story 3 — Progress Tracking & Pedagogical Blocking (Priority: P3)

The learner tracks their progress through the syllabus. Each concept node has a status:
`Unresearched`, `In Progress`, or `Mastered`. The learner updates status manually; the system
enforces blocking so advanced nodes cannot be drafted until prerequisites are complete.

**Why this priority**: Progress tracking and blocking together enforce the pedagogical contract —
concepts are learned in dependency order, preventing shallow understanding.

**Independent Test**: Mark a prerequisite as `Unresearched` → verify advanced node is blocked.
Mark it `Mastered` → verify the advanced node becomes available for drafting.

**Acceptance Scenarios**:

1. **Given** a node's prerequisite is `Unresearched`, **When** the user marks the prerequisite
   `Mastered`, **Then** the dependent node transitions to available for drafting.
2. **Given** a node is `In Progress`, **When** viewed, **Then** the current chapter draft and
   its outstanding source-verification tasks are both displayed.
3. **Given** all nodes are `Mastered`, **When** the user views the topic overview, **Then** the
   Virtual Book is presented as a coherent, fully linked document.

---

### User Story 4 — Active Reading via Margin Comments (Priority: P4)

While reading a drafted chapter, the learner adds margin comments to request elaboration, a
simpler analogy, or a worked example for any passage. The system responds inline without
regenerating the entire chapter.

**Why this priority**: Passive reading is not learning. Margin interactions personalise the
content and surface gaps in understanding.

**Independent Test**: Add a margin comment to a paragraph → system returns a targeted inline
response anchored to that paragraph without altering surrounding text.

**Acceptance Scenarios**:

1. **Given** a drafted chapter, **When** the user highlights a passage and requests a simpler
   explanation, **Then** an inline response is inserted adjacent to the original passage.
2. **Given** a margin comment requesting a worked example, **When** processed, **Then** the
   example uses only concepts the learner has already encountered in the syllabus.
3. **Given** a margin comment is resolved, **When** the chapter is viewed, **Then** resolved
   comments are visually distinguished from the main text (e.g. collapsible or greyed out).

---

### User Story 5 — Automated Bibliography Aggregation (Priority: P5)

Citations added to each chapter are automatically aggregated into a master bibliography for the
entire Virtual Book. Duplicates are removed. The bibliography is always current and accessible
from the topic overview.

**Why this priority**: Traceability to authoritative sources is a core project objective. A live
bibliography allows the learner to audit source quality.

**Independent Test**: Draft two chapters each citing the same source → bibliography lists it
once. Draft a third chapter with a new source → bibliography adds it without duplication.

**Acceptance Scenarios**:

1. **Given** two chapters cite the same source by identifier (DOI or URL), **When** the
   bibliography is viewed, **Then** the source appears exactly once.
2. **Given** a chapter is amended with a new citation, **When** the bibliography is refreshed,
   **Then** the new source appears without requiring a manual rebuild.
3. **Given** the Virtual Book overview, **When** the learner selects a bibliography entry,
   **Then** they can navigate to every chapter that references that source.

---

### Edge Cases

- What happens when syllabus generation produces a cyclic prerequisite dependency (A requires B,
  B requires A)? The system MUST detect and report cycles rather than silently producing a
  broken syllabus.
- How does the system behave when no high-quality sources can be located for a requested node?
  It MUST surface this explicitly rather than drafting an unsourced chapter.
- How does context folding behave when the Virtual Book grows very large? Summaries MUST remain
  coherent and not silently truncate key concepts.
- What happens when a previously verified source becomes unavailable? The system MUST flag the
  citation rather than silently leaving a broken reference.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST accept a free-text topic name and generate a hierarchical,
  prerequisite-aware syllabus of concept nodes.
- **FR-002**: The system MUST detect and reject cyclic prerequisite relationships, reporting
  the cycle to the user.
- **FR-003**: The system MUST identify and surface bottleneck concepts (nodes with the highest
  count of downstream dependents) in the syllabus view.
- **FR-004**: Each syllabus node MUST have a status of `Unresearched`, `In Progress`, or
  `Mastered`, persisted across sessions.
- **FR-005**: The system MUST block chapter drafting for any node that has at least one direct
  prerequisite with status `Unresearched`.
- **FR-006**: The system MUST draft chapters using only sources promoted to the verified Core
  Bucket; unverified sources MUST NOT appear in any chapter.
- **FR-007**: When drafting a chapter, the system MUST supply the agent with the master topic
  overview and concise summaries of all previously completed chapters, not full chapter text.
- **FR-008**: The system MUST maintain a source verification queue where the user can review
  and promote or reject sources before they are used in chapters.
- **FR-009**: The system MUST allow learners to add margin comments to any paragraph of a
  drafted chapter and receive targeted inline responses.
- **FR-010**: The system MUST maintain a deduplicated master bibliography across all chapters,
  updated whenever a chapter is created or amended.
- **FR-011**: The system MUST persist all state (syllabus, chapter drafts, source queue,
  bibliography, progress) durably across sessions.
- **FR-012**: The system MUST log every agent action (inputs, tool calls, outputs) for
  auditability. No agent action may fail silently.

### Key Entities

- **Topic**: The root learning goal. Attributes: title, description. Owns one Syllabus and one
  VirtualBook.
- **SyllabusItem**: A single concept node. Attributes: title, description, status
  (`Unresearched` | `In Progress` | `Mastered`), list of prerequisite SyllabusItem references.
- **VirtualBook**: The master document for a Topic. Composed of an ordered list of
  AtomicChapters and a master Bibliography.
- **AtomicChapter**: A drafted chapter for one SyllabusItem. Contains prose content, a list of
  MarginComments, and local citations linking to Source records.
- **Source**: A bibliographic record (URL or DOI, title, authors, publication). Verification
  status: `Queued`, `Verified` (Core Bucket), or `Rejected`.
- **MarginComment**: A user annotation anchored to a paragraph in an AtomicChapter. Status:
  `Open` or `Resolved`. May have an inline response.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A learner can go from topic input to a reviewed syllabus in under 2 minutes for a
  topic with up to 20 concept nodes.
- **SC-002**: A learner can go from selecting an unblocked node to reading a drafted chapter in
  under 5 minutes (excluding source verification wait time).
- **SC-003**: Pedagogical blocking is enforced 100% of the time — no chapter is ever drafted for
  a node with an `Unresearched` prerequisite.
- **SC-004**: The master bibliography contains zero duplicate entries at all times.
- **SC-005**: All session state is restored exactly on resume — no data loss across sessions.
- **SC-006**: Every chapter references only Core Bucket sources; zero unverified sources appear
  in any chapter.
- **SC-007**: The system produces a structured log entry for every agent action with no silent
  failures.

## Assumptions

- Initial version targets a single learner per topic; multi-user collaboration is out of scope.
- Source verification is a manual step — the user reviews and promotes sources to the Core
  Bucket. Automated verification is out of scope for the prototype.
- The system operates online; an internet connection is assumed for agent and source operations.
- "High-quality sources" means ArXiv papers, peer-reviewed publications, and curated
  educational video channels; the Academic Scout is pre-configured with these domains.
- Margin comment responses use the same agent and Core Bucket sources as chapter drafting.
- Export of the Virtual Book (PDF, EPUB, etc.) is out of scope for the prototype.
- A single topic is the unit of work; linking multiple topics into a curriculum is out of scope.

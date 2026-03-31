# Feature Specification: Multi-User Isolation

**Feature Branch**: `004-multi-user-isolation`
**Created**: 2026-03-31
**Status**: Draft
**Input**: User description: "make the app multi user. No shared documents. If the same source is added by two users, that can be shared (no need to to have 2 copies in chroma etc) but the 2 users dont know it. There'll need to be something like reference counting so we can delete a file if everyone who added it deletes it. Course, content and progress are per-person."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Invitation Code Generation (Priority: P1)

An administrator (or the person running the app) uses a command-line tool to generate a single-use invitation code. They share this code out-of-band (e.g. via email or message) with the intended new user.

**Why this priority**: Generating codes is a prerequisite for onboarding any user. Without this, no one can join the system.

**Independent Test**: Run `manage invite`, confirm a code is printed to stdout, confirm the code is stored in the system and marked unused.

**Acceptance Scenarios**:

1. **Given** access to the CLI, **When** the operator runs `manage invite`, **Then** a unique, single-use code is printed to stdout and persisted in the system.
2. **Given** a code has already been used, **When** the operator generates a new code via the CLI, **Then** a fresh, previously-unused code is produced.
3. **Given** an invalid or missing configuration (e.g. no database connection), **When** the operator runs the CLI command, **Then** a clear error message is printed and no partial record is written.

---

### User Story 2 - Join by Invitation Code and Login (Priority: P2)

A new user receives an invitation code, visits the app, enters the code along with their chosen credentials, and creates their account. Subsequent visits use those credentials to log in. After login they see only their own data.

**Why this priority**: This is the only onboarding path. Public self-registration does not exist; the invitation code is the gate.

**Independent Test**: Generate a code via CLI, use it to create account A, attempt to reuse the same code for account B (must fail), then log in as A and verify isolation from any other accounts.

**Acceptance Scenarios**:

1. **Given** a valid, unused invitation code, **When** the user submits it along with their chosen email and password, **Then** their account is created and they are logged in.
2. **Given** a code that has already been used, **When** a second user attempts to register with it, **Then** registration is rejected with a clear error.
3. **Given** an invalid or expired code, **When** a user submits it, **Then** registration is rejected with a clear error and no account is created.
4. **Given** two registered users A and B, **When** user A logs in and views their dashboard, **Then** they see only their own courses and documents — none of user B's.
5. **Given** an unauthenticated request, **When** the user attempts to access any protected resource, **Then** they are redirected to the login page.

---

### User Story 3 - Per-User Course and Content Ownership (Priority: P3)

A logged-in user creates courses, adds content (topics, lessons, syllabi), and tracks their own learning progress. All of this data is scoped exclusively to them.

**Why this priority**: This is the primary value of the application. Users must own their learning data independently.

**Independent Test**: Create a course with topics and lessons as user A; log in as user B and confirm the course does not appear. Mark a lesson complete as user A; confirm it remains incomplete for user B.

**Acceptance Scenarios**:

1. **Given** user A has created a course, **When** user B logs in, **Then** user B's course list does not include user A's course.
2. **Given** user A marks a lesson as complete, **When** user B views the same content they independently added, **Then** their progress is unaffected.
3. **Given** user A deletes a course, **When** user A views their course list, **Then** the course no longer appears; user B's data is unchanged.

---

### User Story 4 - Source Document Deduplication with Reference Counting (Priority: P4)

When a user adds a source document (e.g. a PDF), the system checks whether that exact document already exists (uploaded by another user). If it does, it reuses the stored file and vector embeddings silently — the user never knows. When a user removes a source they added, the system decrements its reference count and only deletes the underlying file and embeddings when no user references it any longer.

**Why this priority**: This optimises storage and processing cost without affecting the user experience. It is a backend concern that can be added after basic per-user isolation works.

**Independent Test**: Upload the same PDF as two different users. Verify only one copy is stored in the document store and vector index. Delete the document as one user; verify the other user's document still works. Delete as the second user; verify the underlying file is removed.

**Acceptance Scenarios**:

1. **Given** user A has added document X, **When** user B adds the identical document X, **Then** only one physical copy and one set of vector embeddings exist in the system.
2. **Given** both user A and user B reference document X, **When** user A removes document X from their library, **Then** user A no longer sees it, but user B's copy remains fully functional.
3. **Given** user A is the last user referencing document X and removes it, **When** that deletion is processed, **Then** the underlying file and all associated vector embeddings are permanently deleted.
4. **Given** user A removes a document, **When** user B queries that document via search or chat, **Then** user B receives correct results (the document is still present for them).

---

### Edge Cases

- What happens when a deactivated user attempts to log in — is the error message distinct from a wrong-password error?
- What happens when a user attempts to access another user's resource by manipulating a URL or API parameter?
- How does the system handle a user who deletes their account — are all their uniquely-referenced documents cleaned up?
- What happens if two users upload the same document simultaneously (race condition on reference counting)?
- How is document identity determined — by content hash, filename, or both?
- What happens if an invitation code is generated but never used — does it expire or remain valid indefinitely?
- What happens if the CLI is run without a valid environment/configuration (e.g. outside Docker)?
- What happens if the operator sets a temporary password for a user who is currently logged in — are their active sessions invalidated?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a single CLI entry-point with subcommands for all operator management tasks (e.g. `manage invite`, `manage reset-password`).
- **FR-002**: The `manage invite` subcommand MUST generate a unique, single-use invitation code and print it to stdout.
- **FR-003**: The system MUST NOT allow account creation without a valid, unused invitation code; public self-registration is not permitted.
- **FR-004**: Each invitation code MUST be single-use; once an account is created with it, the code MUST be invalidated and cannot be reused.
- **FR-005**: The system MUST support distinct user accounts, each with a unique identity and secure credentials (email + password).
- **FR-006**: All courses MUST be owned by and visible only to the user who created them.
- **FR-007**: All topics, lessons, syllabi, and associated content MUST be scoped to the owning user; no cross-user access is permitted.
- **FR-008**: All learning progress records MUST be stored per-user; completing a lesson for one user MUST NOT affect another user's progress on the same content.
- **FR-009**: The system MUST prevent any user from reading, modifying, or deleting another user's courses, content, or progress — including via direct URL or API parameter manipulation.
- **FR-010**: When a user adds a source document, the system MUST check for an existing copy using a deterministic identity mechanism before storing a new physical file or generating new vector embeddings.
- **FR-011**: The system MUST maintain a reference count for each stored source document, incrementing it when a user adds that document and decrementing it when a user removes it.
- **FR-012**: When a source document's reference count reaches zero, the system MUST delete the underlying stored file and all associated vector embeddings.
- **FR-013**: A user removing a shared source document MUST NOT affect the availability of that document for any other user who still references it.
- **FR-014**: Users MUST have no visibility into whether a document they added is shared with other users.
- **FR-015**: The system MUST require authentication for all operations that access or modify user-owned data.
- **FR-016**: The `manage reset-password` subcommand MUST allow the operator to set a temporary password for a specified user account; there is no in-app self-service password reset.
- **FR-017**: The `manage deactivate-user` subcommand MUST allow the operator to deactivate a user account, blocking all future logins for that user while retaining all their data.
- **FR-018**: A deactivated user MUST NOT be able to log in or access any protected resource; all their data (courses, content, progress, document references) MUST be preserved and remain recoverable.

### Key Entities

- **Invitation Code**: A single-use token generated by the CLI; consumed at account creation and then permanently invalidated.
- **User**: Represents an individual account created via an invitation code; owns all courses, content, progress, and source-document references.
- **Source Document**: A physical file and its vector embeddings stored once; referenced by one or more users. Carries a reference count.
- **User–Source Reference**: A relationship record linking a user to a source document, enabling per-user removal without affecting other users.
- **Course**: A learning unit owned by a single user; invisible to all other users.
- **Progress Record**: A per-user record of completion state for a given lesson or topic.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Invitation enforcement — automated tests confirm that account creation always requires a valid, unused code, and that any used code cannot create a second account.
- **SC-002**: Zero data leakage — automated tests confirm that no user can retrieve, list, or modify another user's courses, content, or progress records.
- **SC-003**: Storage deduplication — when 10 users each add the same document, exactly one physical copy and one set of embeddings exists in the system.
- **SC-004**: Reference-count correctness — when the last user referencing a document removes it, the file and embeddings are deleted within one request cycle; confirmed by integration tests.
- **SC-005**: Access control coverage — all endpoints that operate on user-owned resources enforce ownership checks, verified by a security test suite with no bypasses.
- **SC-006**: Seamless user experience — users can add, search, and remove documents without any indication of backend deduplication; user-facing flows are identical to single-user behaviour.

## Clarifications

### Session 2026-03-31

- Q: How should password recovery work? → A: Operator runs a CLI command to set a temporary password for a user.
- Q: How should CLI commands be grouped — single entry-point with subcommands or separate standalone scripts? → A: Single entry-point with subcommands (e.g. `manage invite`, `manage reset-password`).
- Q: Should the operator be able to deactivate or delete a user account via the CLI? → A: Operator can deactivate a user (blocks login, data retained) via `manage deactivate-user`.

## Assumptions

- There is no public self-registration; the only onboarding path is via a CLI-generated invitation code.
- There is no in-app self-service password reset; account recovery is operator-managed via a CLI command that sets a temporary password.
- Active sessions are not invalidated when the operator resets a password (deferred to a future security hardening iteration).
- The CLI is a single entry-point tool with subcommands (e.g. `manage invite`, `manage reset-password`), intended to be run by whoever operates the app (e.g. via `docker exec` or directly on the host); it is not a web-accessible endpoint.
- Invitation codes do not expire; they remain valid until used. Expiry can be added in a future iteration.
- Each user authenticates with an email-and-password credential; social/SSO login is out of scope for this feature.
- Document identity for deduplication is determined by a content hash (e.g. SHA-256 of the raw file bytes); filename alone is insufficient.
- Account self-deletion is out of scope; operator-managed deactivation (data-preserving, login-blocking) is the only account removal mechanism in v1.
- Re-activation of a deactivated account is out of scope for this feature iteration.
- Concurrent uploads of the same document by two users at the same moment will be handled with a database-level uniqueness constraint on the content hash to prevent duplicate storage.
- Existing single-user data in the database will be migrated to a default seed user or discarded; a migration strategy will be defined during planning.
- Session management follows standard web security practices (secure, HTTP-only cookies or short-lived tokens).

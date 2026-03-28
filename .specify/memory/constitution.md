<!--
SYNC IMPACT REPORT
==================
Version change: (none — initial ratification) → 1.0.0
Bump type: MAJOR (first concrete version; all placeholders replaced)

Modified principles: N/A (first population of template)

Added sections:
  - Core Principles (I–V)
  - Technology Stack
  - Code Quality Gates
  - Governance

Removed sections: N/A

Templates updated:
  ✅ .specify/memory/constitution.md (this file)
  ✅ .specify/templates/plan-template.md (Constitution Check gates updated)
  ⚠  .specify/templates/spec-template.md (no changes required; structure compatible)
  ⚠  .specify/templates/tasks-template.md (no changes required; logging/typing tasks already exemplified)
  ⚠  .specify/templates/commands/ (directory does not exist; no command templates to update)

Deferred TODOs:
  - None; all fields resolved from user input and docs/overview.md.
-->

# Learning Tracker Constitution

## Core Principles

### I. Test-First Development (NON-NEGOTIABLE)

TDD is mandatory for all backend services and business logic:

- Tests MUST be written and reviewed before implementation begins.
- Tests MUST fail before implementation is written (Red → Green → Refactor).
- Remote APIs (LLMs, external HTTP services) MUST NOT be called in tests; use mocks/fakes.
  Tests that depend on live remote calls provide no reliable signal and MUST NOT be written.
- Integration tests MUST target real local infrastructure (Dockerised PostgreSQL) not mocks
  of the database layer.

**Rationale**: Untested prototype code rots fastest; TDD is the minimum viable safety net.
Remote-API tests are flaky by nature and couple the test suite to external availability.

### II. Strong Typing (NON-NEGOTIABLE)

All Python code MUST be fully and explicitly typed:

- Every function argument and return value MUST carry a concrete type annotation.
- `TypedDict` or `pydantic.BaseModel` MUST be used for structured data; plain `dict` is
  forbidden as a function signature type.
- `Any` MUST NOT appear in production code. Annotate with the narrowest concrete type or
  use a bounded `TypeVar`.
- `mypy` MUST pass with no errors on the entire codebase before a feature is considered done.
- Pydantic models MUST be used for all API request/response schemas and for config objects.

**Rationale**: The project uses AI-generated outputs and complex data pipelines; silent type
errors are costly. Strong typing makes refactoring safe and agent-generated code reviewable.

### III. Simplicity & Scope Discipline

This project is a **demo/prototype**, not a production system:

- The simplest implementation that satisfies the spec MUST be chosen over a more general one.
- New features or capabilities MUST NOT be added without an explicit user confirmation step.
  When in doubt, stop and ask rather than extend scope.
- YAGNI applies strictly: do not build abstractions, configuration options, or extension
  points for hypothetical future requirements.
- Remove dead code; do not leave commented-out implementations or feature flags.

**Rationale**: Prototype codebases accumulate complexity faster than production ones because
there is no release pressure to trim scope. This principle counteracts that drift.

### IV. Functional Style Over OOP

Prefer functions and data over classes and inheritance:

- Pure functions with explicit inputs/outputs MUST be preferred over stateful classes.
- Classes are permitted only where a framework requires them (e.g., FastAPI routers,
  SQLAlchemy models) or where encapsulating mutable I/O state is genuinely cleaner.
- Inheritance MUST NOT be used for code reuse; use composition or plain function calls.
- Side-effectful code (DB writes, HTTP calls) MUST be pushed to the edges of the call graph,
  keeping core logic pure and easily testable.

**Rationale**: Functional code is easier to test, reason about, and pass to an AI agent for
review or generation. It reduces hidden coupling between components.

### V. Comprehensive Logging — No Silent Failures

Every non-trivial operation MUST produce a structured log entry:

- All exceptions MUST be caught at appropriate boundaries and logged with full traceback
  before re-raising or returning an error response. Silent `except: pass` blocks are
  forbidden.
- Agent operations (Syllabus Architect, Academic Scout, Chapter Scribe) MUST log inputs,
  outputs, and any tool calls at `DEBUG` level.
- Request/response cycles MUST be logged at `INFO` level with duration and status code.
- Use Python's `logging` module with structured formatting (JSON preferred for machine
  parsing). Do not use `print` for operational output.

**Rationale**: This is an AI-agent system where failures may be subtle (wrong answer, not an
exception). Rich logs are the primary debugging surface.

## Technology Stack

Canonical technology choices for this project — deviations require explicit justification:

- **Language**: Python 3.12+ managed via `uv` workspaces (monorepo).
- **Backend framework**: FastAPI for all HTTP APIs.
- **Frontend**: HTMX for interactivity; JavaScript MUST be minimised. No JS framework.
- **Database**: PostgreSQL running in a Docker container. No SQLite or in-memory DB in any
  environment including development.
- **Server runtime**: Application server(s) run in Docker containers. `docker compose` is
  the canonical way to start the full stack locally.
- **AI/Agent SDK**: Google ADK for agent orchestration; `documentlm-core` package wraps
  shared RAG, vector storage, and DB base models.
- **Package management**: `uv` only. Do not use `pip`, `poetry`, or `conda` directly.

## Code Quality Gates

The following checks MUST pass before any code is committed or a task marked complete:

- **Ruff**: `ruff check` MUST produce zero errors. `ruff format` MUST be applied.
- **Mypy**: `mypy` MUST produce zero errors in strict mode for the changed package(s).
- **Tests**: `pytest` MUST pass for all tests in scope of the change (no skipped tests
  without a recorded reason).
- **No `Any`**: grep for `: Any` and `-> Any` MUST return no results in new code.
- **No bare dicts in signatures**: grep for `-> dict` and `: dict` (unparameterised)
  MUST return no results in new code.

These gates apply to every task, not just release tasks.

## Governance

- This constitution supersedes all other practices documented in this repository.
- Amendments MUST be made via the `/speckit.constitution` command; do not edit this file
  manually.
- Any amendment that removes or materially redefines a principle is a MAJOR version bump.
  Adding a principle or section is a MINOR bump. Clarifications are PATCH bumps.
- After each amendment the Sync Impact Report (HTML comment at top of this file) MUST be
  updated and all templates flagged as `⚠ pending` reviewed within the same PR.
- All implementation plans MUST include a Constitution Check section that gates Phase 0
  research on compliance with Principles I–V and the Technology Stack section above.

**Version**: 1.0.0 | **Ratified**: 2026-03-28 | **Last Amended**: 2026-03-28

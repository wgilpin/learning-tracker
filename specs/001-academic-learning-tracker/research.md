# Research: Academic Learning Tracker App

**Branch**: `001-academic-learning-tracker`
**Date**: 2026-03-28
**Phase**: 0 — Outline & Research

---

## Decision 1: Monorepo Structure

**Decision**: `uv` workspace with two packages:
- `packages/documentlm-core` — shared engine (DB models, RAG, agent wrappers, services)
- `apps/api` — FastAPI application (routes, HTMX templates, request handlers)

**Rationale**: The spec references `documentlm-core` explicitly. Separating shared logic into a
library package makes it independently testable and keeps the web app thin. Two packages is
the minimum for the described architecture; a single flat project would conflate agent
orchestration logic with HTTP concerns.

**Alternatives considered**:
- Single flat project: rejected — mixes agent logic, DB models, and HTTP routes; harder to
  test core logic in isolation.
- Three or more packages: rejected — YAGNI for a prototype. A `documentlm-core` + `apps/api`
  split is sufficient.

---

## Decision 2: Vector Storage

**Decision**: `pgvector` PostgreSQL extension for vector embeddings. No separate vector
database (Weaviate, Pinecone, Chroma, etc.).

**Rationale**: The constitution mandates PostgreSQL in Docker as the only storage backend.
`pgvector` adds embedding support via a standard Postgres extension, keeping the infrastructure
footprint to a single container. For prototype scale (single user, tens of documents), pgvector
cosine similarity search is more than adequate.

**Alternatives considered**:
- ChromaDB: rejected — adds a second storage dependency; overkill for prototype scale.
- In-memory numpy arrays: rejected — not durable across sessions (violates FR-011).
- Weaviate/Pinecone: rejected — remote APIs not appropriate for offline/prototype use.

---

## Decision 3: Google ADK Agent Patterns

**Decision**: Define each agent (Syllabus Architect, Academic Scout, Chapter Scribe) as a
standalone ADK `Agent` with explicit typed tool functions. Agents are invoked as pure async
functions from FastAPI background tasks; they do not hold server-side state between calls.

**Rationale**: ADK agents are stateless callable units. Routing agent calls through FastAPI
background tasks (or `asyncio` tasks triggered by an HTMX request) allows the UI to poll or
use SSE for progress while the agent runs. This keeps agent logic in `documentlm-core` and
HTTP concerns in `apps/api`.

Key ADK patterns:
- `Agent(name=..., model=..., tools=[...])` — one instance per agent type, created at startup.
- Tool functions are typed Python callables; ADK serialises their signatures for the model.
- `runner.run_async(agent, session_service, ...)` for async invocation.
- All tool functions that call external services MUST be mocked in tests (constitution P-I).

**Alternatives considered**:
- LangChain agents: rejected — constitution specifies Google ADK.
- Direct LLM API calls without ADK: rejected — loses structured tool-use and session management.

---

## Decision 4: HTMX Interaction Patterns

**Decision**: Use HTMX `hx-post` / `hx-get` for all UI interactions. Use Server-Sent Events
(`hx-ext="sse"`) to stream agent progress updates to the browser. Jinja2 templates serve
HTML partials. No JavaScript framework.

**Rationale**: Constitution mandates HTMX with minimal JS. SSE is the HTMX-native pattern for
long-running server operations (agent calls). Jinja2 is the standard FastAPI template engine.

Key patterns:
- Syllabus item status updates: `hx-patch` → returns updated item partial.
- Chapter draft request: `hx-post` starts background task → returns a polling partial that
  uses `hx-trigger="every 2s"` to poll a status endpoint until done.
- Margin comment submission: `hx-post` → returns inline response partial.
- Bibliography: `hx-get` with `hx-trigger="revealed"` for lazy load.

**Alternatives considered**:
- WebSockets for agent progress: more complex to implement; SSE is sufficient for one-way
  server→client progress and is simpler.
- Full page reloads: too slow for the interactive syllabus; defeats the purpose of HTMX.

---

## Decision 5: Database ORM & Migrations

**Decision**: SQLAlchemy 2.x (async, Core + ORM) with Alembic for migrations. Pydantic v2
models are used for all API/service layer data; SQLAlchemy models are used only for DB I/O.

**Rationale**: SQLAlchemy async is the standard pairing with FastAPI. Keeping SQLAlchemy models
separate from Pydantic models enforces the constitution's functional-style boundary — DB
entities are not passed directly to route handlers.

**Alternatives considered**:
- Tortoise ORM: less mature ecosystem, fewer Alembic equivalents.
- Raw asyncpg: more control but much more boilerplate for a prototype.
- Single model (SQLModel): blurs DB/API boundary; constitution prefers explicit separation.

---

## Decision 6: Source Retrieval (Academic Scout)

**Decision**: The Academic Scout uses ADK tool functions that call `httpx` to fetch metadata
from ArXiv API and YouTube Data API. In tests, these tool functions are replaced with mocks
(constitution P-I). The Scout returns a list of `Source` typed objects to be placed in the
verification queue.

**Rationale**: External API calls are isolated to clearly named tool functions, making them
trivially mockable. No live API calls in any test.

**Alternatives considered**:
- Scrapy/BeautifulSoup crawling: overkill for prototype; structured APIs (ArXiv, YouTube) are
  sufficient.

---

## NEEDS CLARIFICATION Resolved

All technical unknowns resolved above. No deferred items.

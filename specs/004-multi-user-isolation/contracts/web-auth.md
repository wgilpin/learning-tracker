# Web Auth Endpoints Contract

All endpoints are part of the FastAPI app (`apps/api`). HTML responses use Jinja2 templates; HTMX partial responses use the `HX-Redirect` header pattern.

---

## `GET /login`

Render the login page.

**Auth required**: No
**Redirects**: If already authenticated, redirect to `/`.

**Response**: `200 OK`, `text/html` — login form with email + password fields and invitation-code registration link.

---

## `POST /login`

Authenticate a user and establish a session.

**Auth required**: No

**Request body** (form-encoded)
| Field | Type | Required |
|-------|------|----------|
| `email` | string | yes |
| `password` | string | yes |

**Success response**
| Request type | Response |
|---|---|
| HTMX (`HX-Request: true`) | `200 OK` + `HX-Redirect: /` header |
| Full page | `302 → /` |

Sets signed session cookie `session` containing `{"user_id": "<uuid>"}`.

**Failure response**
| Condition | Status | Body |
|-----------|--------|------|
| Wrong credentials | `401` | Re-render login form with error message |
| Account deactivated | `403` | Re-render login form with "account deactivated" message |
| Missing fields | `422` | Re-render login form with validation error |

---

## `POST /logout`

Invalidate the current session.

**Auth required**: Yes (no-op if unauthenticated)

**Request body**: none

**Success response**
| Request type | Response |
|---|---|
| HTMX | `200 OK` + `HX-Redirect: /login` header |
| Full page | `302 → /login` |

Clears the session cookie.

---

## `GET /register`

Render the registration page (invitation code + new credentials form).

**Auth required**: No

**Response**: `200 OK`, `text/html` — form with fields: `invite_code`, `email`, `password`, `password_confirm`.

---

## `POST /register`

Redeem an invitation code and create a new user account.

**Auth required**: No

**Request body** (form-encoded)
| Field | Type | Required |
|-------|------|----------|
| `invite_code` | string | yes |
| `email` | string | yes |
| `password` | string | yes |
| `password_confirm` | string | yes |

**Success response**
| Request type | Response |
|---|---|
| HTMX | `200 OK` + `HX-Redirect: /` header |
| Full page | `302 → /` |

Creates `users` row, marks `invitation_codes.is_used = true`, sets session cookie.

**Failure responses**
| Condition | Status | Body |
|-----------|--------|------|
| Invalid / used invitation code | `400` | Re-render form with "invalid invitation code" error |
| Email already registered | `409` | Re-render form with "email already in use" error |
| Passwords don't match | `422` | Re-render form with validation error |
| Weak password (< 8 chars) | `422` | Re-render form with validation error |

---

## Protected Route Behaviour

All routes except `/login`, `/register`, and `/static/*` require authentication.

| Condition | Response |
|-----------|----------|
| No session cookie | `302 → /login` |
| HTMX request, no session | `200 OK` + `HX-Redirect: /login` header |
| Deactivated user (has session but `is_active=false`) | Clear session, `302 → /login?reason=deactivated` |

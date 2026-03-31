# CLI Contract: `manage` Command

Entry-point registered as `manage` in `apps/api/pyproject.toml`.
Invoked as `uv run manage <subcommand> [args]` or (inside container) `manage <subcommand> [args]`.

---

## `manage invite`

Generate a single-use invitation code and print it to stdout.

**Usage**
```
manage invite
```

**Arguments**: none

**Output (stdout)**
```
INV-<32-char-hex>
```
Exactly one line. No surrounding whitespace or labels.

**Exit codes**
| Code | Meaning |
|------|---------|
| 0 | Code generated and persisted successfully |
| 1 | DB connection error or any other failure |

**Stderr** (on failure): human-readable error message + Python traceback at DEBUG level.

**Idempotency**: Each invocation always produces a new, distinct code. No deduplication.

---

## `manage reset-password <email> <new-password>`

Set a new password for an existing user account.

**Usage**
```
manage reset-password user@example.com <new-password>
```

**Arguments**
| Arg | Type | Required | Description |
|-----|------|----------|-------------|
| `email` | string | yes | Email address of the target user |
| `new-password` | string | yes | Plaintext password to hash and store |

**Output (stdout)**
```
Password updated for user@example.com
```

**Exit codes**
| Code | Meaning |
|------|---------|
| 0 | Password updated successfully |
| 1 | User not found, DB error, or invalid arguments |

**Notes**
- Active sessions for the user are **not** invalidated (by design in v1).
- The new password is bcrypt-hashed before storage; the plaintext is never written to disk or logs.

---

## `manage deactivate-user <email>`

Deactivate a user account. Blocks all future logins. Data is preserved.

**Usage**
```
manage deactivate-user user@example.com
```

**Arguments**
| Arg | Type | Required | Description |
|-----|------|----------|-------------|
| `email` | string | yes | Email of the user to deactivate |

**Output (stdout)**
```
User user@example.com deactivated.
```

**Exit codes**
| Code | Meaning |
|------|---------|
| 0 | User deactivated successfully |
| 1 | User not found, already deactivated, DB error, or invalid arguments |

**Notes**
- Sets `users.is_active = false` and `users.deactivated_at = now()`.
- A deactivated user receives a "Your account has been deactivated" message on login attempt.
- All data (topics, sources, progress) is fully preserved.
- Re-activation is out of scope for v1; the row can be manually updated in the DB if needed.

---

## General Error Format

All subcommands write errors to **stderr** and exit with code 1:
```
Error: <human-readable message>
```
At `--verbose` / `DEBUG=true`, a Python traceback follows.

## `manage --help`

```
usage: manage [-h] {invite,reset-password,deactivate-user} ...

Learning Tracker operator CLI.

subcommands:
  invite              Generate a single-use invitation code
  reset-password      Set a new password for a user account
  deactivate-user     Deactivate a user account (blocks login, preserves data)
```

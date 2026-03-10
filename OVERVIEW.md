# Permission Marketing MCP — Functional Overview

At its core this server is a **CRUD store** (`Dict[permission_id → PermissionGrant]`) where every record carries an integer `level` (1–5) representing the trust stage of Godin's Permission Marketing ladder. The semantic layer on top enforces that this integer can only ever increase through an explicit user consent moment — never silently.

**Tools**

| Tool | What it does |
|---|---|
| `request_permission(scope, reason, duration, constraints?)` | Inserts a new grant; auto-grants level 1, requires explicit consent for 2–4, requires a `constraints` dict for level 5. |
| `check_permission(scope)` | Read-only lookup with hierarchical prefix matching (`orders` covers `orders.auto_create`). Returns `bool`. |
| `revoke_permission(permission_id)` | Soft-delete: sets `revoked_at`, never removes the row so the audit trail stays intact. |
| `list_permissions(user_id?)` | Returns all active (non-revoked, non-expired) grants for a user. |
| `escalate_permission(current_scope, desired_scope, reason)` | Dry-run only — returns the value proposition and what the user must agree to. **Writes nothing.** |
| `confirm_permission(current_scope, desired_scope, reason, ...)` | Atomic upgrade: soft-deletes the old grant (`superseded_by_escalation`) and inserts the new one, then writes an `ESCALATE` audit event. |
| `explain_permission(scope)` | Returns a human-readable description of what a scope enables and how to revoke it. |

**Key invariants**
- No scope above level 1 is granted without an explicit consent source (`explicit_consent` / `explicit_delegation`).
- Level 5 always requires a `constraints` dict and auto-attaches `guardrails`; enforced before any write.
- Every tool call appends an immutable `AuditEvent` (action: `GRANT / CHECK / REVOKE / ESCALATE / DENY`).
- The split `escalate → confirm` keeps the user's "Yes" visible between the two calls — Godin's consent moment is never bypassed.

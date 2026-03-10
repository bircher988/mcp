# Permission Marketing MCP — Functionalities

A reference implementation of Seth Godin's Permission Marketing framework for Agentic AI, exposing tools and resources to manage multi-level user consent with full audit capability.

---

## Permission Ladder (5 Levels)

| Level | Label | Description | Auto-granted |
|-------|-------|-------------|:---:|
| 1 | **Situational** | One-time interaction, public access (browse, search, view) — (scopes: `catalog.browse`, `product.search`, `product.view_details`) | Yes (source: `"auto_granted"`) |
| 2 | **Brand Trust** | Save preferences & receive recommendations — requires opt-in (scopes: `preferences.save`, `recommendations.receive`, `wishlist.manage`) | No (source: `"explicit_consent"`) |
| 3 | **Personal Relationship** | Cross-session context, order history — requires authentication (scopes: `history.read`, `profile.personalize`, `cross_session.context`) | No (source: `"explicit_consent"`) |
| 4 | **Points Permission** | Loyalty data, behavioural analytics, expedited checkout — requires enrolment (scopes: `loyalty.read`, `offers.personalized`, `analytics.behavioral`) | No (source: `"explicit_consent"`) |
| 5 | **Agentic (Intravenous)** | Agent acts autonomously on behalf of the user — requires explicit delegation with constraints (scopes: `orders.auto_create`, `inventory.monitor`, `payment.authorize`) | No (source: `"explicit_delegation"`) |

---

## MCP Tools

### `request_permission`
Requests user consent for a given scope. **In the current implementation this is also the write operation** — it creates and persists the `PermissionGrant` immediately, assuming the client has already obtained the user's agreement before calling the tool.

- Determines the appropriate ladder level automatically from the scope name (by matching `scope` against each `PermissionLadderLevel.scopes` list; defaults to level 1 if not found).
- Auto-grants Level 1 scopes without user interaction (sets `source = "auto_granted"` and skips consent dialogue).
- **Requires explicit `constraints` dict** for Level 5 (raises `ValueError` otherwise — enforced before the grant is created).
- Supports flexible durations parsed into an `expires_at` datetime: `"session"` (+24 h), `"1 year"` (+365 days), `"until_revoked"` / `"permanent"` → `null`; also accepts `"N days"`, `"N weeks"`, `"N months"`.
- At Level 5, automatically attaches default `guardrails` (`require_confirmation_if: ["price_increase > 10%"]`, `auto_revoke_if: ["inactivity > 6 months"]`, `notify_on: ["action_taken"]`).
- Writes to the in-memory `PermissionDatabase` (`db.save_grant`) and appends a `GRANT` event to the audit log.
- Returns the full `PermissionGrant` object serialised to JSON (`model.model_dump(mode='json')`).

> **Design note:** `request_permission` conflates two logical steps — the consent dialogue (step 1) and the grant storage (step 2). A stricter implementation would split these into `request_permission` (returns a pending request) and `confirm_permission` (records the user's "yes").

---

### `check_permission`
Verifies whether the agent currently holds an active, non-expired permission for a scope.

- Looks up all grants for `user_id` in the in-memory store, filters out revoked (`revoked_at is not None`) and expired (`expires_at < now()`) entries.
- Supports **hierarchical scope matching**: a grant on `"orders"` also covers `"orders.auto_create"` (prefix + dot check).
- Returns `bool` — `True` if at least one matching active grant is found.
- Appends a `CHECK` event to the audit log with outcome `"granted"` or `"denied"`.

---

### `revoke_permission`
Revokes a previously granted permission by its ID (`permission_id: str`).

- Performs a **soft delete** — sets `revoked_at = datetime.now()` and `revoked_by = "user_initiated"` on the grant object; the row is never removed from the store (preserves the audit trail).
- Returns `bool` — `False` if the ID is unknown or already revoked.
- Appends a `REVOKE` event to the audit log.
- Enables graceful degradation: because the revocation is scope-specific, the agent automatically falls back to the highest remaining active permission level.

---

### `list_permissions`
Returns all active (non-revoked, non-expired) permissions for a user (`user_id: Optional[str]`, defaults to `CURRENT_USER_ID`).

- Iterates the user's permission ID list, hydrates each `PermissionGrant`, and filters in a single pass.
- Returns a `List[Dict]` serialised via `model_dump(mode='json')`.
- No audit event is written (read-only, non-sensitive enumeration).

---

### `escalate_permission`
Requests to climb the ladder from a current scope to a higher-level one (`current_scope`, `desired_scope`, `reason`).

- Computes `current_level` and `desired_level` by calling `determine_permission_level()` on each scope.
- Returns `{"success": False}` immediately if `desired_level <= current_level` (no downgrade allowed).
- Otherwise returns: `current_level`, `desired_level`, `value_proposition` and `requires` (pulled from `PERMISSION_LADDER` config), plus a `suggested_request` string formatted by `format_permission_request()` (ready to display in a conversational UI).
- Does **not** create any grant — it is a planning/UX helper only.

---

### `explain_permission`
Returns a human-readable explanation of what a given scope enables (`scope: str`).

- Resolves the scope to its `PermissionLadderLevel` via `determine_permission_level()`.
- Returns: `scope`, `level` (int), `label`, `description`, `value_proposition`, `requires`, `example` (use case), `can_revoke: true`, and `revocation_command` (e.g. `"'stop orders'"`).
- Intended for use in consent UI copy or agent-generated explanations.

---

## MCP Resources

| URI | Purpose |
|-----|---------|
| `resource://permissions/{user_id}/current` | Snapshot of all active grants — returns `permission_count` (int), `highest_level` (int 0–5), and the full serialised grant list |
| `resource://permissions/{user_id}/ladder` | Full `PERMISSION_LADDER` definition + `available_escalations` filtered to levels above the user's current maximum |
| `resource://permissions/{user_id}/audit` | Last 50 `AuditEvent` entries (sliced from the tail of the log) — labelled GDPR Article 30 compliant |

---

## Data Models

| Model | Role | Key fields |
|-------|------|------------|
| `PermissionGrant` | Core persisted entity (one row per consent act) | `permission_id` (UUID prefix), `level` (1–5), `scope` (str), `granted_at`, `expires_at` (nullable), `source`, `context`, `use_count` (int), `constraints`, `guardrails`, `revoked_at` (nullable) |
| `PermissionConstraints` | Bounded scope for Level 5 — attached to the grant at creation | `product_id`, `category_id`, `max_price_usd` (float), `max_quantity` (int), `frequency_limit` (`"daily"` / `"weekly"` / `"monthly"`), `time_windows` (list), `require_notification` (bool, default `True`) |
| `PermissionGuardrails` | Escalation / safety triggers — auto-attached at Level 5 | `require_confirmation_if` (list of condition strings), `auto_revoke_if` (list), `notify_on` (list) |
| `AuditEvent` | Immutable log entry — written on every tool call | `event_id`, `timestamp`, `action` (`GRANT` / `CHECK` / `REVOKE` / `DENY` / `ESCALATE`), `user_id`, `agent_id`, `scope`, `level`, `outcome`, `context` (dict) |

---

## Key Design Principles

- **Consent is explicit** — no scope above Level 1 is assumed without user agreement (auto-grant flag is `False` for levels 2–5).
- **Value exchange is visible** — every permission request surfaces a clear `value_proposition` string from the ladder config.
- **Revocation is always possible** — soft-delete pattern means `revoke_permission` never breaks referential integrity; the agent degrades gracefully.
- **Audit trail by default** — every tool call appends an `AuditEvent`; the log is never truncated, only sliced on read.
- **Constraints are mandatory at Level 5** — `ValueError` is raised at the top of `request_permission` before any write occurs.

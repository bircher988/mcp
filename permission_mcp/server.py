"""
Permission Marketing MCP Server
================================
A reusable, application-agnostic MCP server that implements Seth Godin's
Permission Marketing ladder for Agentic AI.

Any application can connect to this server and use it to manage user consent
across five trust levels.  The server knows nothing about the consuming
application — it only understands scopes, levels, grants, and audit events.

Transport: stdio (spawned as a subprocess by the consuming application).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

# ────────────────────────────────────────────────────────────────────────────
# MCP Server
# ────────────────────────────────────────────────────────────────────────────
mcp = FastMCP("Permission Marketing")

# ────────────────────────────────────────────────────────────────────────────
# Permission Ladder — Godin's five levels
# ────────────────────────────────────────────────────────────────────────────

LADDER = [
    {
        "level": 1,
        "label": "Situational",
        "description": "One-time interaction, no ongoing relationship",
        "auto_grant": True,
        "requires": "None (public access)",
        "value_proposition": "Frictionless browsing experience",
    },
    {
        "level": 2,
        "label": "Brand Trust",
        "description": "Customer returns, trusts brand enough to share preferences",
        "auto_grant": False,
        "requires": "Explicit verbal/click opt-in",
        "value_proposition": "Personalised suggestions that save time",
    },
    {
        "level": 3,
        "label": "Personal Relationship",
        "description": "Personalised relationship across sessions",
        "auto_grant": False,
        "requires": "User authentication",
        "value_proposition": "Seamless experience — no need to repeat yourself",
    },
    {
        "level": 4,
        "label": "Points Permission",
        "description": "Loyalty programme justifies deeper data use",
        "auto_grant": False,
        "requires": "Loyalty programme enrolment",
        "value_proposition": "Exclusive benefits and substantial savings",
    },
    {
        "level": 5,
        "label": "Agentic (Intravenous)",
        "description": "Customer delegates decisions to an agent with constraints",
        "auto_grant": False,
        "requires": "Explicit delegation with constraints and guardrails",
        "value_proposition": "Effortless management — the agent acts on your behalf",
    },
]

# ────────────────────────────────────────────────────────────────────────────
# In-memory state
# ────────────────────────────────────────────────────────────────────────────

# scope -> { level, description }  (registered by the consuming application)
_registered_scopes: dict[str, dict[str, Any]] = {}

# user_id -> { scope -> grant_dict }
_grants: dict[str, dict[str, dict[str, Any]]] = {}

# flat list of audit events
_audit: list[dict[str, Any]] = []


def _user_grants(user_id: str) -> dict[str, dict[str, Any]]:
    return _grants.setdefault(user_id, {})


def _log(user_id: str, action: str, scope: str | None, outcome: str, extra: dict | None = None):
    _audit.append({
        "id": uuid.uuid4().hex[:8],
        "ts": datetime.now().isoformat(),
        "user_id": user_id,
        "action": action,
        "scope": scope,
        "outcome": outcome,
        **(extra or {}),
    })


def _is_active(grant: dict[str, Any]) -> bool:
    if grant.get("revoked"):
        return False
    exp = grant.get("expires_at")
    if exp and datetime.fromisoformat(exp) < datetime.now():
        return False
    return True


def _scope_level(scope: str) -> int:
    reg = _registered_scopes.get(scope)
    return reg["level"] if reg else 1


def _ladder_for(level: int) -> dict[str, Any] | None:
    for l in LADDER:
        if l["level"] == level:
            return l
    return None


# ────────────────────────────────────────────────────────────────────────────
# MCP Tools — Scope registration
# ────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def register_scopes(scopes: list[dict]) -> str:
    """
    Register application-specific scopes with their permission levels.

    Each item in *scopes* must have:
      - scope  (str):  unique identifier, e.g. "preferences.save"
      - level  (int):  permission ladder level 1-5
      - description (str): human-readable explanation

    Call this once at application startup so the Permission MCP knows
    which scopes your application uses and what level they require.
    """
    for s in scopes:
        _registered_scopes[s["scope"]] = {
            "level": s["level"],
            "description": s.get("description", ""),
        }
    return json.dumps({
        "status": "ok",
        "registered": len(scopes),
        "total_scopes": len(_registered_scopes),
    })


# ────────────────────────────────────────────────────────────────────────────
# MCP Tools — Permission lifecycle
# ────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def request_permission(user_id: str, scope: str, reason: str) -> str:
    """
    Request permission from a user for a given scope.

    • Level 1 scopes are auto-granted (no user interaction needed).
    • Level 2-5 returns status "pending_approval" — the calling application
      must present the request to the user and call grant_permission when
      the user accepts.

    Args:
        user_id: User identifier.
        scope:   The scope to request permission for.
        reason:  Human-readable explanation of why permission is needed.
    """
    level = _scope_level(scope)
    ladder = _ladder_for(level)

    # Level 1 → auto-grant
    if level <= 1 or (ladder and ladder.get("auto_grant")):
        grants = _user_grants(user_id)
        grants[scope] = {
            "scope": scope,
            "level": level,
            "granted_at": datetime.now().isoformat(),
            "source": "auto_granted",
            "reason": reason,
        }
        _log(user_id, "GRANT", scope, "auto_granted")
        return json.dumps({
            "status": "granted",
            "level": level,
            "scope": scope,
            "message": "Level 1 permission auto-granted.",
        })

    # Levels 2-5 → pending approval
    _log(user_id, "REQUEST", scope, "pending", {"reason": reason})
    return json.dumps({
        "status": "pending_approval",
        "level": level,
        "scope": scope,
        "label": ladder["label"] if ladder else f"Level {level}",
        "reason": reason,
        "value_proposition": ladder["value_proposition"] if ladder else "",
        "requires": ladder["requires"] if ladder else "",
        "message": (
            f"Permission requested: Level {level} "
            f"({ladder['label'] if ladder else ''}) for '{scope}'. "
            f"Reason: {reason}. Awaiting user approval."
        ),
    })


@mcp.tool()
def grant_permission(
    user_id: str,
    scope: str,
    duration: str = "until_revoked",
    constraints: dict | None = None,
) -> str:
    """
    Grant a previously requested permission (called after the user approves).

    Args:
        user_id:     User identifier.
        scope:       The scope being granted.
        duration:    How long the grant lasts.
                     Options: "session", "until_revoked", "7 days", "30 days", "1 year".
        constraints: Optional dict of constraints for Level 5 (agentic) grants.
                     Example: {"max_price": 25.0, "frequency": "weekly", "product_id": "eth-01"}
    """
    level = _scope_level(scope)

    # Level 5 requires constraints
    if level >= 5 and not constraints:
        return json.dumps({
            "status": "error",
            "message": (
                "Level 5 (Agentic) permissions require explicit constraints. "
                "Provide a constraints dict with limits such as max_price, "
                "frequency, product restrictions, etc."
            ),
        })

    expires_at = _calc_expiry(duration)
    grants = _user_grants(user_id)
    grants[scope] = {
        "scope": scope,
        "level": level,
        "granted_at": datetime.now().isoformat(),
        "expires_at": expires_at,
        "source": "explicit_consent" if level < 5 else "explicit_delegation",
        "constraints": constraints,
    }
    _log(user_id, "GRANT", scope, "granted", {"constraints": constraints})
    return json.dumps({
        "status": "granted",
        "level": level,
        "scope": scope,
        "expires_at": expires_at,
        "message": f"Permission for '{scope}' granted (Level {level}).",
    })


@mcp.tool()
def check_permission(user_id: str, scope: str) -> str:
    """
    Check whether a user currently has an active permission for a scope.

    Returns { granted: true/false, level, scope }.
    """
    grants = _user_grants(user_id)
    grant = grants.get(scope)
    has = grant is not None and _is_active(grant)
    _log(user_id, "CHECK", scope, "granted" if has else "denied")
    result: dict[str, Any] = {
        "scope": scope,
        "level": _scope_level(scope),
        "granted": has,
    }
    if has and grant:
        result["constraints"] = grant.get("constraints")
    return json.dumps(result)


@mcp.tool()
def revoke_permission(user_id: str, scope: str) -> str:
    """
    Revoke a user's permission for a scope. Users can always revoke at any time.
    """
    grants = _user_grants(user_id)
    grant = grants.get(scope)
    if not grant or grant.get("revoked"):
        return json.dumps({"status": "not_found", "message": f"No active permission for '{scope}'."})
    grant["revoked"] = True
    grant["revoked_at"] = datetime.now().isoformat()
    _log(user_id, "REVOKE", scope, "revoked")
    return json.dumps({"status": "revoked", "scope": scope, "message": f"Permission for '{scope}' revoked."})


@mcp.tool()
def list_permissions(user_id: str) -> str:
    """
    List all active (non-revoked, non-expired) permissions for a user.
    """
    grants = _user_grants(user_id)
    active = {k: v for k, v in grants.items() if _is_active(v)}
    highest = max((v["level"] for v in active.values()), default=0)
    return json.dumps({
        "user_id": user_id,
        "permissions": active,
        "count": len(active),
        "highest_level": highest,
    })


# ────────────────────────────────────────────────────────────────────────────
# MCP Tools — Introspection
# ────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_permission_ladder() -> str:
    """
    Return the full permission ladder configuration (levels 1-5).
    Useful for presenting escalation options to the user.
    """
    return json.dumps({"ladder": LADDER})


@mcp.tool()
def get_registered_scopes() -> str:
    """
    Return all scopes that the application has registered,
    grouped by permission level.
    """
    by_level: dict[int, list[dict]] = {}
    for scope, info in _registered_scopes.items():
        lv = info["level"]
        by_level.setdefault(lv, []).append({"scope": scope, **info})
    return json.dumps({"scopes_by_level": by_level, "total": len(_registered_scopes)})


@mcp.tool()
def get_audit_trail(user_id: str, last_n: int = 50) -> str:
    """
    Return the last *last_n* audit events for a user.
    Supports GDPR Article 30 compliance.
    """
    user_events = [e for e in _audit if e["user_id"] == user_id]
    return json.dumps({"user_id": user_id, "events": user_events[-last_n:], "total": len(user_events)})


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def _calc_expiry(duration: str) -> str | None:
    if duration in ("until_revoked", "permanent"):
        return None
    if duration == "session":
        return (datetime.now() + timedelta(hours=24)).isoformat()
    for unit, delta in [("day", timedelta(days=1)), ("week", timedelta(weeks=1)),
                        ("month", timedelta(days=30)), ("year", timedelta(days=365))]:
        if unit in duration:
            try:
                n = int(duration.split()[0])
            except (ValueError, IndexError):
                n = 1
            return (datetime.now() + delta * n).isoformat()
    return None


# ────────────────────────────────────────────────────────────────────────────
# Run
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")

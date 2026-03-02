"""
Permission Marketing MCP Server
A reference implementation of Seth Godin's Permission Marketing framework for Agentic AI

This server provides tools for managing multi-level permissions, from situational
browsing to agentic delegation with constraints and guardrails.
"""

from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import json
import uuid

# ============================================================================
# DATA MODELS
# ============================================================================

class PermissionConstraints(BaseModel):
    """Constraints that limit scope of permission (required for Level 5)"""
    product_id: Optional[str] = None
    category_id: Optional[str] = None
    max_price_usd: Optional[float] = None
    max_quantity: Optional[int] = None
    frequency_limit: Optional[str] = None  # "daily", "weekly", "monthly"
    time_windows: Optional[List[str]] = None
    require_notification: bool = True


class PermissionGuardrails(BaseModel):
    """Conditions that trigger escalation back to user"""
    require_confirmation_if: List[str] = Field(default_factory=list)
    auto_revoke_if: List[str] = Field(default_factory=list)
    notify_on: List[str] = Field(default_factory=list)


class PermissionGrant(BaseModel):
    """A granted permission with metadata and audit trail"""
    permission_id: str
    level: int  # 1-5 (Godin's ladder)
    scope: str
    granted_at: datetime
    expires_at: Optional[datetime] = None
    source: str  # "verbal_consent", "explicit_delegation", "auto_granted"
    context: str  # User's actual words or action
    last_used: Optional[datetime] = None
    use_count: int = 0
    constraints: Optional[PermissionConstraints] = None
    guardrails: Optional[PermissionGuardrails] = None
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None


class PermissionLadderLevel(BaseModel):
    """Definition of a permission ladder level"""
    level: int
    label: str
    description: str
    scopes: List[str]
    auto_grant: bool
    requires: str
    example_use_case: str
    value_proposition: str


class AuditEvent(BaseModel):
    """Audit log entry for compliance and transparency"""
    event_id: str
    timestamp: datetime
    action: str  # "GRANT", "USE", "REVOKE", "DENY", "ESCALATE"
    permission_id: Optional[str] = None
    user_id: str
    agent_id: str
    scope: Optional[str] = None
    level: Optional[int] = None
    outcome: str
    context: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# PERMISSION LADDER CONFIGURATION
# ============================================================================

PERMISSION_LADDER: List[PermissionLadderLevel] = [
    PermissionLadderLevel(
        level=1,
        label="Situational",
        description="One-time interaction, no ongoing relationship",
        scopes=["catalog.browse", "product.search", "product.view_details"],
        auto_grant=True,
        requires="None (public access)",
        example_use_case="User asks 'Show me coffee beans'",
        value_proposition="Frictionless browsing experience"
    ),
    PermissionLadderLevel(
        level=2,
        label="Brand Trust",
        description="Customer returns, trusts brand enough to engage",
        scopes=["preferences.save", "recommendations.receive", "wishlist.manage"],
        auto_grant=False,
        requires="Explicit verbal/click opt-in",
        example_use_case="Remember favorite products for personalized recommendations",
        value_proposition="Tailored suggestions that save time"
    ),
    PermissionLadderLevel(
        level=3,
        label="Personal Relationship",
        description="Personalized relationship across sessions",
        scopes=["history.read", "profile.personalize", "cross_session.context"],
        auto_grant=False,
        requires="User authentication",
        example_use_case="Show past orders and maintain context between visits",
        value_proposition="Seamless experience, no need to repeat yourself"
    ),
    PermissionLadderLevel(
        level=4,
        label="Points Permission",
        description="Loyalty program justifies deeper data use",
        scopes=["loyalty.read", "offers.personalized", "purchase.expedited_checkout", "analytics.behavioral"],
        auto_grant=False,
        requires="Loyalty program enrollment",
        example_use_case="Unlock VIP pricing and early access to new products",
        value_proposition="Exclusive benefits and substantial savings"
    ),
    PermissionLadderLevel(
        level=5,
        label="Agentic (Intravenous)",
        description="Customer delegates decisions to agent",
        scopes=["orders.auto_create", "inventory.monitor", "payment.authorize", "preferences.auto_adjust"],
        auto_grant=False,
        requires="Explicit delegation with constraints and guardrails",
        example_use_case="Auto-reorder coffee when running low",
        value_proposition="Effortless supply management, never run out"
    )
]


# ============================================================================
# PERMISSION DATABASE (In-Memory for Demo)
# ============================================================================

class PermissionDatabase:
    """Simple in-memory database for permissions and audit trail"""
    
    def __init__(self):
        self.permissions: Dict[str, PermissionGrant] = {}
        self.audit_log: List[AuditEvent] = []
        self.user_permissions: Dict[str, List[str]] = {}  # user_id -> [permission_ids]
    
    def save_grant(self, grant: PermissionGrant, user_id: str) -> str:
        """Save a permission grant"""
        self.permissions[grant.permission_id] = grant
        
        if user_id not in self.user_permissions:
            self.user_permissions[user_id] = []
        self.user_permissions[user_id].append(grant.permission_id)
        
        return grant.permission_id
    
    def get_grant(self, permission_id: str) -> Optional[PermissionGrant]:
        """Retrieve a permission grant"""
        return self.permissions.get(permission_id)
    
    def get_user_grants(self, user_id: str) -> List[PermissionGrant]:
        """Get all active grants for a user"""
        permission_ids = self.user_permissions.get(user_id, [])
        grants = []
        for pid in permission_ids:
            grant = self.permissions.get(pid)
            if grant and not grant.revoked_at:
                # Check expiration
                if grant.expires_at and grant.expires_at < datetime.now():
                    continue
                grants.append(grant)
        return grants
    
    def has_permission(self, user_id: str, scope: str) -> bool:
        """Check if user has active permission for scope"""
        grants = self.get_user_grants(user_id)
        for grant in grants:
            if grant.scope == scope or scope.startswith(grant.scope + "."):
                return True
        return False
    
    def revoke(self, permission_id: str, revoked_by: str = "user") -> bool:
        """Revoke a permission"""
        grant = self.permissions.get(permission_id)
        if grant and not grant.revoked_at:
            grant.revoked_at = datetime.now()
            grant.revoked_by = revoked_by
            return True
        return False
    
    def log_event(self, event: AuditEvent):
        """Add event to audit log"""
        self.audit_log.append(event)
    
    def get_audit_trail(self, user_id: str) -> List[AuditEvent]:
        """Get audit events for user"""
        return [e for e in self.audit_log if e.user_id == user_id]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def determine_permission_level(scope: str) -> int:
    """Determine which ladder level a scope belongs to"""
    for ladder_level in PERMISSION_LADDER:
        if scope in ladder_level.scopes:
            return ladder_level.level
    
    # Default to level 1 for unknown scopes
    return 1


def get_ladder_level_config(level: int) -> Optional[PermissionLadderLevel]:
    """Get configuration for a specific permission level"""
    for ladder_level in PERMISSION_LADDER:
        if ladder_level.level == level:
            return ladder_level
    return None


def calculate_expiry(duration: str) -> Optional[datetime]:
    """Calculate expiration datetime from duration string"""
    if duration == "session":
        return datetime.now() + timedelta(hours=24)
    elif duration == "until_revoked" or duration == "permanent":
        return None
    elif "day" in duration:
        days = int(duration.split()[0])
        return datetime.now() + timedelta(days=days)
    elif "week" in duration:
        weeks = int(duration.split()[0])
        return datetime.now() + timedelta(weeks=weeks)
    elif "month" in duration:
        months = int(duration.split()[0])
        return datetime.now() + timedelta(days=30 * months)
    elif "year" in duration:
        years = int(duration.split()[0])
        return datetime.now() + timedelta(days=365 * years)
    
    return None


def format_permission_request(
    scope: str,
    reason: str,
    level: int,
    constraints: Optional[Dict] = None
) -> str:
    """Format a conversational permission request"""
    ladder_config = get_ladder_level_config(level)
    
    if not ladder_config:
        return f"May I {reason}?"
    
    request = f"To {reason}, I need permission to access: {scope}\n\n"
    request += f"**What this enables:** {ladder_config.value_proposition}\n\n"
    
    if level >= 5 and constraints:
        request += "**Constraints:**\n"
        for key, value in constraints.items():
            request += f"  • {key}: {value}\n"
        request += "\n"
    
    request += f"**You can revoke this anytime** by saying 'stop {scope.split('.')[0]}'\n"
    
    return request


# ============================================================================
# MCP TOOLS
# ============================================================================

# Global database instance
db = PermissionDatabase()

# Current user context (in real implementation, extract from MCP session)
CURRENT_USER_ID = "user_789"
CURRENT_AGENT_ID = "shopping_assistant"


async def request_permission(
    scope: str,
    reason: str,
    duration: str = "session",
    constraints: Optional[Dict] = None
) -> Dict:
    """
    Request user permission for specific scope
    
    Args:
        scope: Permission scope (e.g., "orders.auto_create")
        reason: Human-readable explanation of why permission is needed
        duration: How long permission lasts ("session", "1 year", "until_revoked")
        constraints: Optional constraints for Level 5 permissions
    
    Returns:
        PermissionGrant object as dict
    """
    level = determine_permission_level(scope)
    
    # Level 5 (Agentic) requires constraints
    if level == 5 and not constraints:
        raise ValueError(
            "Agentic permissions (Level 5) require explicit constraints. "
            "Specify max_price, frequency_limit, product restrictions, etc."
        )
    
    # Auto-grant Level 1 (Situational)
    ladder_config = get_ladder_level_config(level)
    if ladder_config and ladder_config.auto_grant:
        source = "auto_granted"
        context = f"Level 1 permission auto-granted for: {reason}"
    else:
        # In real implementation, would present to user and await response
        # For demo, we simulate explicit grant
        source = "explicit_consent" if level < 5 else "explicit_delegation"
        context = f"User granted permission for: {reason}"
    
    # Create permission grant
    grant = PermissionGrant(
        permission_id=f"P{str(uuid.uuid4())[:8]}",
        level=level,
        scope=scope,
        granted_at=datetime.now(),
        expires_at=calculate_expiry(duration),
        source=source,
        context=context,
        use_count=0,
        constraints=PermissionConstraints(**constraints) if constraints else None,
        guardrails=PermissionGuardrails(
            require_confirmation_if=["price_increase > 10%"],
            auto_revoke_if=["inactivity > 6 months"],
            notify_on=["action_taken"]
        ) if level == 5 else None
    )
    
    # Save to database
    db.save_grant(grant, CURRENT_USER_ID)
    
    # Log audit event
    db.log_event(AuditEvent(
        event_id=f"E{str(uuid.uuid4())[:8]}",
        timestamp=datetime.now(),
        action="GRANT",
        permission_id=grant.permission_id,
        user_id=CURRENT_USER_ID,
        agent_id=CURRENT_AGENT_ID,
        scope=scope,
        level=level,
        outcome="success",
        context={"reason": reason, "source": source}
    ))
    
    return grant.model_dump(mode='json')


async def check_permission(scope: str) -> bool:
    """
    Verify if agent currently has permission for scope
    
    Args:
        scope: Permission scope to check
    
    Returns:
        True if permission granted and active, False otherwise
    """
    has_perm = db.has_permission(CURRENT_USER_ID, scope)
    
    # Log usage attempt
    db.log_event(AuditEvent(
        event_id=f"E{str(uuid.uuid4())[:8]}",
        timestamp=datetime.now(),
        action="CHECK",
        user_id=CURRENT_USER_ID,
        agent_id=CURRENT_AGENT_ID,
        scope=scope,
        outcome="granted" if has_perm else "denied",
        context={}
    ))
    
    return has_perm


async def revoke_permission(permission_id: str) -> bool:
    """
    Revoke previously granted permission
    
    Args:
        permission_id: ID of permission to revoke
    
    Returns:
        True if successfully revoked, False otherwise
    """
    success = db.revoke(permission_id, revoked_by="user_initiated")
    
    if success:
        grant = db.get_grant(permission_id)
        db.log_event(AuditEvent(
            event_id=f"E{str(uuid.uuid4())[:8]}",
            timestamp=datetime.now(),
            action="REVOKE",
            permission_id=permission_id,
            user_id=CURRENT_USER_ID,
            agent_id=CURRENT_AGENT_ID,
            scope=grant.scope if grant else None,
            level=grant.level if grant else None,
            outcome="success",
            context={"revoked_by": "user_initiated"}
        ))
    
    return success


async def list_permissions(user_id: Optional[str] = None) -> List[Dict]:
    """
    Retrieve all active permissions for user
    
    Args:
        user_id: User ID (defaults to current user)
    
    Returns:
        List of PermissionGrant objects as dicts
    """
    uid = user_id or CURRENT_USER_ID
    grants = db.get_user_grants(uid)
    return [g.model_dump(mode='json') for g in grants]


async def escalate_permission(
    current_scope: str,
    desired_scope: str,
    reason: str
) -> Dict:
    """
    Request to climb permission ladder (Level N → Level N+1)
    
    Args:
        current_scope: Current permission scope
        desired_scope: Desired higher-level scope
        reason: Why escalation is needed
    
    Returns:
        Escalation request with value proposition
    """
    current_level = determine_permission_level(current_scope)
    desired_level = determine_permission_level(desired_scope)
    
    if desired_level <= current_level:
        return {
            "success": False,
            "message": "Desired scope is not a higher permission level"
        }
    
    ladder_config = get_ladder_level_config(desired_level)
    
    return {
        "success": True,
        "current_level": current_level,
        "desired_level": desired_level,
        "value_proposition": ladder_config.value_proposition if ladder_config else "",
        "requires": ladder_config.requires if ladder_config else "",
        "suggested_request": format_permission_request(desired_scope, reason, desired_level)
    }


async def explain_permission(scope: str) -> Dict:
    """
    Return human-readable explanation of what scope enables
    
    Args:
        scope: Permission scope to explain
    
    Returns:
        Explanation with examples and constraints
    """
    level = determine_permission_level(scope)
    ladder_config = get_ladder_level_config(level)
    
    if not ladder_config:
        return {"error": "Unknown permission scope"}
    
    return {
        "scope": scope,
        "level": level,
        "label": ladder_config.label,
        "description": ladder_config.description,
        "value_proposition": ladder_config.value_proposition,
        "requires": ladder_config.requires,
        "example": ladder_config.example_use_case,
        "can_revoke": True,
        "revocation_command": f"'stop {scope.split('.')[0]}'"
    }


# ============================================================================
# MCP RESOURCES
# ============================================================================

async def get_current_permissions_resource(user_id: str) -> Dict:
    """Resource: resource://permissions/{user_id}/current"""
    grants = db.get_user_grants(user_id)
    
    return {
        "user_id": user_id,
        "agent_id": CURRENT_AGENT_ID,
        "last_updated": datetime.now().isoformat(),
        "permissions": [g.model_dump(mode='json') for g in grants],
        "permission_count": len(grants),
        "highest_level": max([g.level for g in grants], default=0)
    }


async def get_permission_ladder_resource(user_id: str) -> Dict:
    """Resource: resource://permissions/{user_id}/ladder"""
    current_grants = db.get_user_grants(user_id)
    current_scopes = {g.scope for g in current_grants}
    current_max_level = max([g.level for g in current_grants], default=0)
    
    available_escalations = []
    for ladder_level in PERMISSION_LADDER:
        if ladder_level.level > current_max_level:
            available_escalations.append({
                "level": ladder_level.level,
                "label": ladder_level.label,
                "scopes": ladder_level.scopes,
                "value_proposition": ladder_level.value_proposition,
                "requires": ladder_level.requires
            })
    
    return {
        "user_id": user_id,
        "current_level": current_max_level,
        "available_escalations": available_escalations,
        "ladder": [l.model_dump() for l in PERMISSION_LADDER]
    }


async def get_permission_audit_resource(user_id: str) -> Dict:
    """Resource: resource://permissions/{user_id}/audit"""
    events = db.get_audit_trail(user_id)
    
    return {
        "user_id": user_id,
        "event_count": len(events),
        "events": [e.model_dump(mode='json') for e in events[-50:]],  # Last 50 events
        "compliance_note": "GDPR Article 30 - Records of processing activities"
    }


# ============================================================================
# DEMO / TESTING
# ============================================================================

async def demo_permission_flow():
    """Demonstrate the complete permission escalation flow"""
    
    print("=" * 80)
    print("PERMISSION MARKETING MCP - DEMO FLOW")
    print("Scenario: Coffee Auto-Reorder Journey")
    print("=" * 80)
    
    # Session 1: Situational (Level 1)
    print("\n📍 SESSION 1: First Visit (Situational Permission)")
    print("-" * 80)
    print("User: 'Show me coffee beans'")
    
    perm1 = await request_permission(
        scope="catalog.browse",
        reason="browse product catalog",
        duration="session"
    )
    print(f"✓ Auto-granted: {perm1['scope']} (Level {perm1['level']})")
    
    # Session 1: Brand Trust (Level 2)
    print("\n📍 SESSION 1: Permission Request (Brand Trust)")
    print("-" * 80)
    print("User: 'I like this Ethiopian Yirgacheffe'")
    print("Agent: 'May I remember your coffee preferences for next time?'")
    print("User: 'Sure'")
    
    perm2 = await request_permission(
        scope="preferences.save",
        reason="personalized recommendations",
        duration="1 year"
    )
    print(f"✓ Granted: {perm2['scope']} (Level {perm2['level']})")
    print(f"  Expires: {perm2['expires_at']}")
    
    # Session 2: Personal Relationship (Level 3)
    print("\n📍 SESSION 2: Two Weeks Later (Personal Relationship)")
    print("-" * 80)
    print("User: 'What did I order before?'")
    print("Agent: 'To show past orders, I need access to your history'")
    print("User: 'Go ahead'")
    
    perm3 = await request_permission(
        scope="history.read",
        reason="display order history",
        duration="permanent"
    )
    print(f"✓ Granted: {perm3['scope']} (Level {perm3['level']})")
    
    # Session 3: Agentic Delegation (Level 5)
    print("\n📍 SESSION 3: After 5 Purchases (Agentic Delegation)")
    print("-" * 80)
    print("Agent: 'You buy Ethiopian Yirgacheffe monthly. Auto-reorder when low?'")
    print("User: 'Okay, but only that coffee, max $50'")
    
    perm5 = await request_permission(
        scope="orders.auto_create",
        reason="autonomous replenishment",
        duration="until_revoked",
        constraints={
            "product_id": "ETH-YRG-001",
            "max_price_usd": 50,
            "frequency_limit": "monthly",
            "require_notification": True
        }
    )
    print(f"✓ Granted: {perm5['scope']} (Level {perm5['level']})")
    print(f"  Constraints:")
    if perm5.get('constraints'):
        for key, value in perm5['constraints'].items():
            print(f"    • {key}: {value}")
    
    # Check current state
    print("\n📊 CURRENT PERMISSION STATE")
    print("-" * 80)
    current_state = await get_current_permissions_resource(CURRENT_USER_ID)
    print(f"User: {current_state['user_id']}")
    print(f"Total Permissions: {current_state['permission_count']}")
    print(f"Highest Level Reached: {current_state['highest_level']}")
    
    # Show audit trail
    print("\n📜 AUDIT TRAIL (Last 5 Events)")
    print("-" * 80)
    audit = await get_permission_audit_resource(CURRENT_USER_ID)
    for event in audit['events'][-5:]:
        print(f"{event['timestamp']}: {event['action']} - {event['scope']} ({event['outcome']})")
    
    # Demonstrate revocation
    print("\n❌ REVOCATION DEMO")
    print("-" * 80)
    print("User: 'Stop auto-ordering coffee'")
    
    revoked = await revoke_permission(perm5['permission_id'])
    if revoked:
        print(f"✓ Revoked: {perm5['scope']}")
        print("  Agent gracefully degrades to Level 3 (history + preferences)")
        print("  No relationship rupture!")
    
    print("\n" + "=" * 80)
    print("DEMO COMPLETE - Permission Marketing in Action!")
    print("=" * 80)


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_permission_flow())

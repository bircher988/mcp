# Permission Marketing MCP: From Interruption to Delegation

A comprehensive Model Context Protocol (MCP) implementation of Seth Godin's **Permission Marketing** framework, designed for the Agentic AI era.

## 📋 Overview

This project demonstrates how to operationalize Permission Marketing principles in AI agent systems, enabling a shift from **interruption** (unwanted messages) to **delegation** (trusted autonomous action).

### What's Included

- **Comprehensive PlantUML Diagram** ([permission-marketing-mcp-system.puml](permission-marketing-mcp-system.puml))
  - Architecture overview (MCP tools, resources, prompts)
  - Permission ladder mapping (Godin's 5 levels → technical scopes)
  - Permission escalation flow (complete user journey)
  - Permission resource schema (data model)
  - Key insights on interruption → delegation transition

- **Reference Implementation** (Python MCP server structure)

## 🎯 Core Concept

> **Permission Marketing** is the privilege (not the right) of delivering anticipated, personal, and relevant messages to people who actually want to receive them.
> 
> — Seth Godin, 1999

In the Agentic AI age, this expands beyond messages to **actions**:

- Can the agent remember my preferences?
- Can it act on my behalf?
- Within what constraints and guardrails?

## 📊 The Permission Ladder

Seth Godin's original ladder, mapped to technical implementation:

| Level | Label | Permission Type | Auto-Grant | Technical Scopes | Example |
|-------|-------|----------------|------------|------------------|---------|
| **1** | Situational | One-time interaction | ✅ Yes | `catalog.browse`, `product.search` | Browse products |
| **2** | Brand Trust | Customer returns, engages | ❌ No | `preferences.save`, `recommendations.receive` | Remember favorites |
| **3** | Personal Relationship | Cross-session personalization | ❌ No | `history.read`, `profile.personalize` | Show past orders |
| **4** | Points Permission | Loyalty-based deeper access | ❌ No | `loyalty.read`, `offers.personalized` | VIP pricing |
| **5** | Agentic (Intravenous) | Delegated decision-making | ❌ No | `orders.auto_create`, `payment.authorize` | Auto-reorder |

### Key Principle

Each level represents **earned permission**, not assumed rights. The agent climbs the ladder by:
1. Delivering value at current level
2. Demonstrating reliability and trustworthiness
3. Requesting permission to deepen relationship
4. Respecting constraints and enabling easy revocation

## 🏗️ MCP Architecture

### Tools

The MCP server exposes six core tools:

```python
@mcp.tool()
async def request_permission(
    scope: str,              # e.g., "orders.auto_create"
    reason: str,             # Why this permission is needed
    duration: str,           # "session", "1 year", "until_revoked"
    constraints: Dict = None # Level 5 guardrails (required for agentic)
) -> PermissionGrant:
    """Request user permission for specific scope with clear value proposition"""

@mcp.tool()
async def check_permission(scope: str) -> bool:
    """Verify if agent currently has permission for scope"""

@mcp.tool()
async def revoke_permission(permission_id: str) -> bool:
    """Revoke previously granted permission (user-initiated or auto-expire)"""

@mcp.tool()
async def list_permissions(user_id: str) -> List[Permission]:
    """Retrieve all current permissions for user"""

@mcp.tool()
async def escalate_permission(
    current_scope: str,
    desired_scope: str,
    reason: str
) -> EscalationRequest:
    """Request to climb permission ladder (Level N → Level N+1)"""

@mcp.tool()
async def explain_permission(scope: str) -> Explanation:
    """Return human-readable explanation of what scope enables"""
```

### Resources

Three key resources expose permission state:

- `resource://permissions/{user_id}/current` - Current granted permissions
- `resource://permissions/{user_id}/ladder` - Available escalation paths
- `resource://permissions/{user_id}/audit` - Permission history (GDPR compliance)

### Prompts

Templates for consistent permission conversations:

- `permission_request_template` - Formats requests with value proposition
- `value_exchange_template` - Explains benefit-for-data trade
- `denial_handler_template` - Graceful handling of refusals

## 🎬 Example Journey: Coffee Auto-Reorder

The diagram illustrates a complete user journey from first visit to autonomous delegation:

### Session 1: Situational Permission (Level 1)
```
User: "Show me coffee beans"
Agent: [Browses catalog - auto-granted, no permission request needed]
```

### Session 1: Brand Trust (Level 2)
```
User: "I like this Ethiopian Yirgacheffe"
Agent: "May I remember your coffee preferences for next time? 
        I'll suggest similar options."
User: "Sure"
→ GRANT: preferences.save (expires: 1 year)
```

### Session 2: Personal Relationship (Level 3)
```
User: "What did I order before?"
Agent: "To show your past orders, I need access to your purchase history."
User: "Makes sense, go ahead"
→ GRANT: history.read (permanent)
```

### Session 3: Agentic Delegation (Level 5)
```
Agent: "I notice you buy Ethiopian Yirgacheffe every month. 
        Want me to auto-reorder when you're running low?"
User: "How would that work?"
Agent: "I'll monitor usage and order 2 weeks before depletion.
        Max $50/order, notification before each purchase.
        Cancel anytime with 'stop auto-ordering'."
User: "Okay, but only that specific coffee"
→ GRANT: orders.auto_create with CONSTRAINTS:
  • product_id: "ETH-YRG-001"
  • max_price_usd: 50
  • frequency_limit: monthly
  • require_notification: true
```

### Future: Autonomous Action
```
Agent: [Detects low inventory]
Agent: [Validates constraints: price ✓, frequency ✓]
Agent: [Creates order]
Agent → User: "☕ I've ordered your Ethiopian Yirgacheffe ($42). Arrives Thursday."
```

## 🛡️ Level 5 Guardrails (Critical!)

**Without constraints, delegation becomes unwanted automation** (back to interruption marketing).

Required guardrails for agentic permissions:

### Constraints (What boundaries exist)
- Product/category restrictions
- Price caps and budget limits
- Frequency constraints (daily, weekly, monthly)
- Time windows (business hours, specific dates)

### Guardrails (When to escalate back to user)
- `require_confirmation_if`: Conditions triggering manual approval
  - Price increase > 10%
  - Product unavailable (substitute offered)
  - Payment method expired
- `auto_revoke_if`: Automatic permission expiration
  - 6 months of inactivity
  - 3 consecutive failures
  - User account downgrade
- `notify_on`: Events requiring notification
  - order_created
  - constraint_violation_detected
  - approaching_budget_limit

## 📦 Permission State Schema

Each permission grant is stored as:

```json
{
  "permission_id": "P789",
  "level": 5,
  "scope": "orders.auto_create",
  "granted_at": "2025-02-10T14:22:00Z",
  "expires_at": null,
  "source": "explicit_delegation",
  "context": "User said: 'Okay, but only that specific coffee'",
  "last_used": "2025-02-25T08:00:00Z",
  "use_count": 2,
  "constraints": {
    "product_id": "ETH-YRG-001",
    "max_price_usd": 50,
    "frequency_limit": "monthly",
    "require_notification": true
  },
  "guardrails": {
    "require_confirmation_if": ["price_increase > 10%"],
    "auto_revoke_if": ["inactivity > 6 months"],
    "notify_on": ["order_created"]
  }
}
```

## 🔄 Revocation & Graceful Degradation

Users must be able to withdraw permission easily:

```
User: "Stop auto-ordering coffee"
Agent: revoke_permission("P789")
→ Permission revoked, agent drops from Level 5 to Level 3
Agent: "Done! I've stopped auto-ordering. You can still browse 
        and order manually, and I'll remember your preferences."
```

**Key Principle: No relationship rupture on revocation.**

The agent gracefully degrades to the highest remaining permission level, preserving the relationship asset.

## 🎨 How to View the Diagram

### Option 1: VS Code (Recommended)
1. Install the [PlantUML extension](https://marketplace.visualstudio.com/items?itemName=jebbs.plantuml)
2. Open `permission-marketing-mcp-system.puml`
3. Press `Alt+D` (or `Option+D` on Mac) to preview

### Option 2: Online
1. Visit [PlantUML Online Server](http://www.plantuml.com/plantuml/uml/)
2. Copy/paste the `.puml` file contents
3. View rendered diagram

### Option 3: CLI
```bash
# Install PlantUML
brew install plantuml  # macOS
# or download from https://plantuml.com/download

# Generate PNG
plantuml permission-marketing-mcp-system.puml

# Generate SVG (better for zooming)
plantuml -tsvg permission-marketing-mcp-system.puml
```

## 🧑‍💻 Implementation Guide

### 1. Set Up MCP Server

```bash
# Install MCP SDK
pip install mcp

# Create server structure
mkdir permission_marketing_mcp
cd permission_marketing_mcp
touch __init__.py server.py models.py database.py
```

### 2. Define Permission Models

```python
# models.py
from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime

class PermissionGrant(BaseModel):
    permission_id: str
    level: int  # 1-5 (Godin's ladder)
    scope: str
    granted_at: datetime
    expires_at: Optional[datetime]
    source: str  # "verbal_consent", "explicit_delegation", etc.
    context: str  # User's words at grant time
    last_used: Optional[datetime]
    use_count: int
    constraints: Optional[Dict] = None
    guardrails: Optional[Dict] = None

class PermissionRequest(BaseModel):
    scope: str
    reason: str
    duration: str
    constraints: Optional[Dict] = None
```

### 3. Implement MCP Server

```python
# server.py
from mcp.server import Server
from mcp.types import Tool, Resource, Prompt
import mcp.server.stdio
from models import PermissionGrant, PermissionRequest
from database import PermissionDB

app = Server("permission-marketing-mcp")
db = PermissionDB()

@app.tool()
async def request_permission(
    scope: str,
    reason: str,
    duration: str = "session",
    constraints: dict | None = None
) -> dict:
    """Request user permission for specific scope"""
    
    # Determine permission level from scope
    level = determine_permission_level(scope)
    
    # Level 5 requires constraints
    if level == 5 and not constraints:
        raise ValueError("Agentic permissions (Level 5) require explicit constraints")
    
    # Format conversational request
    request_text = format_permission_request(scope, reason, level, constraints)
    
    # Present to user (in real implementation, this would be interactive)
    # For now, we'll assume grant
    
    # Create grant record
    grant = PermissionGrant(
        permission_id=generate_id(),
        level=level,
        scope=scope,
        granted_at=datetime.now(),
        expires_at=calculate_expiry(duration),
        source="explicit_consent",
        context=f"Requested for: {reason}",
        use_count=0,
        constraints=constraints
    )
    
    # Store in database
    db.save_grant(grant)
    
    # Log audit event
    db.log_event("GRANT", grant)
    
    return grant.dict()

@app.tool()
async def check_permission(scope: str) -> bool:
    """Check if current agent has permission for scope"""
    return db.has_permission(scope)

@app.tool()
async def revoke_permission(permission_id: str) -> bool:
    """Revoke previously granted permission"""
    success = db.revoke(permission_id)
    if success:
        db.log_event("REVOKE", permission_id, source="user_initiated")
    return success

@app.resource("permissions/{user_id}/current")
async def get_current_permissions(user_id: str) -> dict:
    """Get current permission state for user"""
    return db.get_user_permissions(user_id)

# Run server
if __name__ == "__main__":
    mcp.server.stdio.run(app)
```

### 4. Configure MCP Client

```json
{
  "mcpServers": {
    "permission-marketing": {
      "command": "python",
      "args": ["/path/to/permission_marketing_mcp/server.py"],
      "env": {
        "PERMISSION_DB_PATH": "/path/to/permissions.db"
      }
    }
  }
}
```

## 📚 Key Insights

### What Changes in the Agentic AI Era?

| **Pre-AI Permission Marketing** | **Agentic AI Permission Marketing** |
|--------------------------------|-------------------------------------|
| Permission to **send messages** | Permission to **take actions** |
| Static email lists | Dynamic conversation context |
| Pre-defined automation flows | Adaptive agent decision-making |
| Binary opt-in/opt-out | Multi-level permission ladder |
| Revoke via unsubscribe link | Revoke via natural language |
| Compliance checkboxes | Conversational consent negotiation |

### Why This Matters

1. **Ethical AI**: Agents that respect user autonomy and consent
2. **Trust Building**: Transparent permission requests build long-term relationships
3. **GDPR Compliance**: Explicit consent, purpose limitation, right to withdraw
4. **Competitive Advantage**: Permission becomes a durable relationship asset
5. **User Experience**: Delegation without loss of control

## 🔗 Related Concepts

- **OAuth 2.0 / OIDC**: Similar scope-based permission model for API access
- **GDPR Consent Management**: Legal framework for data processing permissions
- **Smart Home Permissions**: IoT device authorization patterns (Alexa, Google Home)
- **Banking Delegation**: Dual control, maker-checker patterns
- **Healthcare Proxy**: Bounded delegation with legal oversight

## 📖 References

- Godin, Seth. *Permission Marketing: Turning Strangers into Friends and Friends into Customers* (1999)
- Coignard, Jérôme. "From Interruption to Delegation: Permission Marketing in the Agentic AI Age" (Dec 2025)
- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [GDPR Articles 6-7: Lawfulness and Conditions for Consent](https://gdpr-info.eu/)

## 🚀 Next Steps

1. **Implement Backend**: Build Python MCP server with SQLite/PostgreSQL
2. **Add UI Layer**: Create conversational interface for permission requests
3. **Multi-Channel Sync**: Extend to voice, messaging apps, email
4. **GDPR Module**: Add data portability, right-to-deletion, consent withdrawal
5. **Analytics Dashboard**: Visualize permission ladder progression
6. **A/B Testing**: Optimize permission request phrasing for conversion
7. **Integration Examples**: E-commerce, SaaS, IoT, healthcare use cases

## 📝 License

This is a conceptual framework and reference implementation. Adapt freely for your use case.

---

**Built with ❤️ for the Agentic AI era**

*Permission is not a checkbox—it's an ongoing, renewable relationship asset that must be earned and can be lost.*

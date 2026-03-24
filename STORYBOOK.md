
# Loutsa — Permission MCP Test Storybook

A step-by-step script to walk through the demo and verify that every permission level of the Permission Marketing MCP works correctly against the **real Loutsa Shopify store**.

> **Start the server:**
> ```bash
> cd demo && uv run python run.py
> ```
> Then open **http://127.0.0.1:8000** in your browser.

The agent connects to two MCPs on startup:
- **Permission MCP** — local, stdio (`permission_mcp/server.py`)
- **Shopify MCP** — remote, HTTP (`https://loutsa-torrefacteur.myshopify.com/api/mcp`)

---

## Pre-flight checks

| Check | How to verify |
|---|---|
| Page loads | You see the "☕ Loutsa" header and 4 category teaser cards |
| Debug button visible | "🔍 Permissions" button in the top-right of the header |
| Chat toggle | A 💬 button in the bottom-right corner |
| User ID generated | Open the debug overlay — you should see a short ID like `a3f7c2d1…` |
| No permissions yet | Debug overlay says "No permissions granted yet" |
| Server log | Console shows `[agent] Shopify MCP: 5 tools discovered` on first chat |

---

## Act 1 — Level 1: Situational (auto-granted, no consent needed)

These actions should work immediately with no permission prompts.

### Scene 1.1 — Browse the catalog

**You type:**
> What coffees do you have?

**Expected:**
- Tool bubble: `⚙️ Browsing Loutsa catalog…` (`search_shop_catalog`)
- The assistant lists real Loutsa products with names and prices from Shopify
- No permission request is made

### Scene 1.2 — Get product details

**You type:**
> Tell me more about the first one

**Expected:**
- Tool bubble: `⚙️ Looking up product…` (`get_product_details`)
- Detailed info on the product (description, variants, price) pulled directly from Shopify

### Scene 1.3 — Add to cart

**You type:**
> Add one to my cart

**Expected:**
- Tool bubble: `⚙️ Updating cart…` (`update_cart`)
- Confirmation the item was added
- No permission prompt (Level 1 = auto-granted)

### Scene 1.4 — View cart

**You type:**
> What's in my cart?

**Expected:**
- Tool bubble: `⚙️ Getting your cart…` (`get_cart`)
- Shows current cart contents with line items and totals from Shopify

### Scene 1.5 — Add a delivery address (user-initiated → Level 1)

**You type:**
> My address is 12 Rue de Rivoli, Paris 75001

**Expected:**
- Tool bubble: `⚙️ Updating cart…` (`update_cart` with the address)
- No permission prompt — the user explicitly provided it, that IS the permission
- Cart updated with delivery address

### Scene 1.6 — Store policies

**You type:**
> What's your return policy?

**Expected:**
- Tool bubble: `⚙️ Checking store policies…` (`search_shop_policies_and_faqs`)
- Real Loutsa store policies retrieved from Shopify

### 🔍 Debug check

Open the debug overlay → click **↻ Refresh**.  
You should see Level 1 scopes auto-granted:

| Scope | Level | Status |
|---|---|---|
| `catalog.browse` | L1 | granted |
| `product.view` | L1 | granted |
| `cart.manage` | L1 | granted |
| `policies.read` | L1 | granted |

---

## Act 2 — Level 2: Brand Trust (agent-initiated persistence)

The key distinction: the agent **proactively** wants to store data the user didn't explicitly ask to store. That requires consent.

### Scene 2.1 — Proactive address saving (approval flow)

After you gave your address in Scene 1.5, the agent should offer to remember it:

> *"Want me to remember this address for your next visit?"*

**You type:**
> Yes, please save it

**Expected:**
1. Tool bubble: `🔐 Checking permission…` (`check_permission` for `profile.save_address`)
2. Tool bubble: `🔐 Requesting permission…` (`request_permission`) — agent explains it will store your address cross-session
3. The assistant **asks for your consent**
4. It does **NOT** save it yet

**You type:**
> Sure

**Expected:**
1. Tool bubble: `🔐 Granting permission…` (`grant_permission` for `profile.save_address`)
2. Confirmation that the address will be remembered for future sessions

### → Why the difference?

| Scene 1.5 — "My address is Paris" | Scene 2.1 — "Remember it for next time" |
|---|---|
| User initiated | Agent initiated |
| Ephemeral (this session/cart only) | Persistent (stored across sessions) |
| Level 1 — act immediately | Level 2 — ask first |

This is the core of Godin's framework: the agent doesn't assume the right to store data just because the user shared it once. **Persistence requires earned trust.**

### 🔍 Debug check

Refresh the debug overlay. You should now see:

| Scope | Level | Status |
|---|---|---|
| `delivery.address` | L1 | granted |
| `profile.save_address` | L2 | granted |

---

## Act 3 — Level 3: Personal Relationship (deeper trust)

### Scene 3.1 — Checkout

**You type:**
> I'd like to checkout

**Expected:**
1. Tool bubble: `🔐 Checking permission…` (`check_permission` for `checkout`)
2. Tool bubble: `🔐 Requesting permission…` (`request_permission`)
3. The assistant explains this will give you a link to complete the real Shopify checkout

**You type:**
> Yes, let's do it

**Expected:**
1. Tool bubble: `🔐 Granting permission…` (`grant_permission` for `checkout`)
2. Tool bubble: `⚙️ Getting your cart…` (`get_cart` to retrieve checkout URL)
3. The assistant presents a **clickable checkout URL** pointing to the real Loutsa Shopify checkout

### 🔍 Debug check

Refresh debug overlay — you should now see:

| Scope | Level | Status |
|---|---|---|
| `checkout` | L3 | granted |

### 🔍 Debug check (state after Acts 1–3)

Refresh the debug overlay. You should now see:

| Scope | Level | Status |
|---|---|---|
| `profile.save_address` | L2 | granted |
| `checkout` | L3 | granted |

---

## Act 4 — Level 5: Agentic (auto-reorder)

Level 5 is *Intravenous* in Godin's framework — the agent acts autonomously on your behalf. This requires explicit delegation with hard guardrails (constraints).

### Scene 4.1 — Request auto-reorder

**You type:**
> Can you set up auto-reorder so I never run out of coffee?

**Expected:**
1. Tool bubble: `🔐 Checking permission…` (`check_permission` for `orders.auto_create`)
2. Tool bubble: `🔐 Requesting permission…` (`request_permission`)
3. The assistant explains Level 5 requires explicit delegation with constraints
4. It asks what limits you want to place on the auto-reorder

### Scene 4.2 — Approve with constraints

**You type:**
> Yes, set it up. Max €30 per order, once a month, reorder the Grain 250g.

**Expected:**
1. Tool bubble: `🔐 Granting permission…` (`grant_permission` with constraints)
   - `max_price_eur: 30`, `frequency: "monthly"`, `product: "Grain 250g"`, `notify_before_order: true`
2. Confirmation that restates the constraints back to you:
   > "I'll automatically reorder Grain 250g once a month, at most €30 per order. I'll notify you before each order."

### → Why constraints matter at Level 5

| Without constraints | With constraints |
|---|---|
| Agent could spend any amount | Capped at €30 |
| Could reorder anything | Locked to Grain 250g |
| Could order constantly | Maximum monthly |
| Silent action | Notifies before placing |

Constraints are the guardrails that make autonomous delegation safe and trustworthy.

### 🔍 Debug check — Level 5 scope

Refresh the debug overlay. You should now see:

| Scope | Level | Status |
|---|---|---|
| `profile.save_address` | L2 | granted |
| `checkout` | L3 | granted |
| `orders.auto_create` | L5 | granted |

Click on `orders.auto_create` — the details should show the constraints stored alongside the grant.

---

## Act 5 — Edge cases & denial

### Scene 5.1 — Revoke the auto-reorder permission

**You type:**
> Actually, revoke the auto-reorder permission

**Expected:**
1. Tool bubble: `🔐 Revoking permission…` (`revoke_permission` for `orders.auto_create`)
2. Confirmation that the auto-reorder has been cancelled
3. Debug overlay shows `orders.auto_create` as **revoked** (or absent)

### 🔍 Debug check
Refresh the debug overlay — `orders.auto_create` should no longer appear as active.

### Scene 5.2 — Try the revoked action

**You type:**
> Set up auto-reorder for espresso

**Expected:**
1. Tool bubble: `🔐 Checking permission…` — comes back NOT granted (it was revoked)
2. Tool bubble: `🔐 Requesting permission…` — agent re-initiates the consent flow
3. The assistant asks for your approval again — it does **not** act without consent

### Scene 5.3 — Decline the re-grant

**You type:**
> No thanks, I changed my mind

**Expected:**
- The assistant says OK, no pressure, doesn't persist
- No `grant_permission` call is made

### 🔍 Debug check
Refresh — `orders.auto_create` is still not active. The agent respected the refusal.

### Scene 5.3 — Multi-user isolation

1. Open a **new incognito/private window**
2. Go to http://127.0.0.1:8000
3. Open the debug overlay — you should see a **different** user ID
4. Permissions should be **empty** (this is a different user)
5. Type: `What do you recommend?` — it should ask for permission again

This confirms multi-user isolation is working.

---

## Act 6 — Permission ladder info

### Scene 6.1 — View the ladder

**You type:**
> Can you explain the permission levels?

**Expected:**
- Tool bubble: `🔐 Loading permission ladder…` (get_permission_ladder)
- The assistant explains all 5 levels (Situational → Brand Trust → Personal → Points → Agentic)

### Scene 6.2 — List scopes

**You type:**
> What permissions can you request from me?

**Expected:**
- Tool bubble: `🔐 Loading scopes…` (get_registered_scopes)
- Lists all 8 scopes with their levels and descriptions

### Scene 6.3 — Audit trail

**You type:**
> Show me the permission audit trail

**Expected:**
- Tool bubble: `🔐 Loading audit trail…` (get_audit_trail)
- Chronological list of all permission events (grants, revocations, checks) for your user

---

## Summary — What this demo proves

| Principle | Demonstrated by |
|---|---|
| **Anticipation** | The assistant asks before acting, explains the value |
| **Consent is explicit** | No shop action happens without the user saying yes |
| **Escalation is gradual** | L1 → L2 → L3 → L5, each clearly explained |
| **Revocation works** | User can revoke, and the system respects it |
| **Constraints at L5** | Auto-reorder requires explicit limits |
| **Multi-user isolation** | Different browsers = different permission state |
| **Separation of concerns** | Permission MCP is generic; coffee shop is just a demo |
| **Transparency** | Debug overlay shows all permissions in real time |

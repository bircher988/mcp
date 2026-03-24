# Slide — Demo Introduction

---

## What you are about to see

A **live AI shopping agent** that asks before it acts.

---

### The scenario

> You open **Bean & Brew** — a specialty coffee shop.  
> An AI assistant is available in the chat.  
> It knows the catalog. It can help you order.  
> But it will **never place an order, save your preferences, or act autonomously** until you say so — explicitly, step by step.

---

### What the demo shows

| Step | What happens | Permission level |
|------|-------------|-----------------|
| 1 | You ask about products | **L1 · Situational** — auto-granted, no prompt |
| 2 | Agent offers to remember your taste | **L2 · Brand Trust** — asks for opt-in |
| 3 | You log in; cart is persisted | **L3 · Personal Relationship** — auth required |
| 4 | Loyalty points unlock a reorder shortcut | **L4 · Points Permission** — enrolment required |
| 5 | You delegate: "just reorder my usual every month" | **L5 · Agentic** — explicit delegation + constraints |

---

### The key insight

> The agent is **not restricted by code alone**.  
> Every escalation is a recorded, auditable consent event — stored in the Permission Marketing MCP.  
> The LLM cannot skip a level. It cannot self-grant. The user's "Yes" is always in the loop.

---

### Stack visible in the demo

- **Frontend** — Bean & Brew web UI (FastAPI + WebSocket)
- **Agent** — Claude via the Anthropic API
- **Permission MCP** — local stdio server (`permission_mcp/server.py`)
- **Shopify MCP** — streamable HTTP, product catalog & cart

---

*Next slide → live walkthrough*

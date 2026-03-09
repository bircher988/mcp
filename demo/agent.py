"""
Bean & Brew — Agent
====================
Bridges OpenRouter (OpenAI-compatible) LLM with:
  • Permission MCP server  (via stdio  — manages consent)
  • Shopify native MCP     (via HTTP   — real Loutsa coffee store)

The agent exposes BOTH as "tools" to the LLM so it can seamlessly
check permissions before performing shop actions.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from contextlib import AsyncExitStack
from typing import Any, AsyncIterator

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

# ────────────────────────────────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────────────────────────────────

_PERM_SERVER = str(Path(__file__).resolve().parent.parent / "permission_mcp" / "server.py")
SHOPIFY_MCP_URL = "https://loutsa-torrefacteur.myshopify.com/api/mcp"

# Scopes mapped to Shopify MCP tools — registered with the Permission MCP
_SHOP_SCOPES = [
    {"scope": "catalog.browse",      "level": 1, "description": "Search the Loutsa coffee catalog"},
    {"scope": "product.view",        "level": 1, "description": "View coffee product details"},
    {"scope": "cart.manage",         "level": 1, "description": "Add items to cart and view cart"},
    {"scope": "policies.read",       "level": 1, "description": "Read store policies and FAQs"},
    {"scope": "delivery.address",    "level": 1, "description": "Add a delivery address to the current cart (user-initiated)"},
    {"scope": "profile.save_address","level": 2, "description": "Remember delivery address across future sessions"},
    {"scope": "checkout",            "level": 3, "description": "Proceed to checkout and place an order"},
]

SYSTEM_PROMPT = """\
You are the friendly assistant for **Loutsa**, a French artisan coffee roaster \
(loutsa-torrefacteur.myshopify.com). Help customers discover and buy great coffee.

## How permissions work

You have access to two kinds of tools:
1. **Permission tools** (from the Permission MCP): check_permission,
   request_permission, grant_permission, revoke_permission, list_permissions,
   get_permission_ladder, get_registered_scopes, get_audit_trail.
2. **Shop tools** (from the Shopify MCP): search_shop_catalog,
   get_product_details, get_cart, update_cart, search_shop_policies_and_faqs.

The current user's ID is provided in the first user message as [user_id: ...].
Use that user_id in ALL permission tool calls.

## Permission rules per action

| Action | Scope | Level | Trigger |
|--------|-------|-------|---------|
| Search catalog, view products, policies | catalog.browse / product.view / policies.read | 1 — auto-granted | Always |
| Add items to cart, view cart | cart.manage | 1 — auto-granted | Always |
| Add a delivery address **the user just provided** | delivery.address | 1 — auto-granted | User asked for it |
| **Proactively** saving address for future sessions | profile.save_address | 2 — needs approval | Agent initiates |
| Proceed to checkout URL | checkout | 3 — needs approval | Financial action |

### The key distinction
- **User-initiated** actions (the user explicitly asked) → treat as Level 1, act immediately.
- **Agent-initiated** persistence (the agent wants to store data the user didn't ask to store) → requires explicit permission first.

Operational rules:
1. If the user says "add my address" or provides an address → call `update_cart` directly (Level 1, no permission check needed).
2. After successfully adding the address, you MUST always follow up with: "Want me to remember this address for your next visit?" — if yes, check/grant `profile.save_address` (Level 2) before confirming you'll save it.
3. For checkout, MUST check/grant `checkout` scope (Level 3) before sharing the checkout URL. Do NOT include the checkout URL in the same response as an address update — address and checkout are separate steps.
4. For any Level 2+ scope you need, if NOT already granted:
   a. Call `request_permission`, explain the value to the user.
   b. Ask the user to approve. Do NOT call `grant_permission` yourself.
   c. When the user agrees, THEN call `grant_permission`.
   d. Proceed.

All Level 1 actions can be performed freely without any permission check.

## Cart behaviour
- A cart is created automatically when you first call `update_cart` without a cart_id.
- Store the returned `cart_id` internally and reuse it for the same user.
- After adding items + delivery address, call `get_cart` to show the checkout URL.
- Never share the raw cart_id with the user — just show the checkout URL.

## Style
- Respond in the same language the user writes in (French or English).
- Be warm, knowledgeable about specialty coffee — like a real barista.
- Format products attractively when presenting them.
- Suggest next steps naturally, never pressure.
- When presenting the checkout URL, format it as a clickable link.
"""

DEFAULT_MODEL = "openai/gpt-4o"


# ────────────────────────────────────────────────────────────────────────────
# Agent
# ────────────────────────────────────────────────────────────────────────────

class Agent:
    def __init__(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.model = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
        self.base_url = "https://openrouter.ai/api/v1"
        self._conversations: dict[str, list[dict[str, Any]]] = {}  # per-user
        self._perm_tools: list[dict[str, Any]] = []   # discovered from Permission MCP
        self._shopify_tools: list[dict[str, Any]] = []  # discovered from Shopify MCP
        self._session: ClientSession | None = None
        self._stack: AsyncExitStack | None = None
        self._cart_ids: dict[str, str] = {}  # user_id → Shopify cart GID

    def _get_messages(self, user_id: str) -> list[dict[str, Any]]:
        """Return (or create) the conversation history for a user."""
        if user_id not in self._conversations:
            self._conversations[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
        return self._conversations[user_id]

    # ── lifecycle ──────────────────────────────────────────────────────────

    async def start(self):
        """Spawn Permission MCP, discover both MCPs' tools, register scopes."""
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()

        server_params = StdioServerParameters(
            command="uv",
            args=["run", "--project", str(Path(__file__).resolve().parent),
                  "python", _PERM_SERVER],
        )
        read_stream, write_stream = await self._stack.enter_async_context(
            stdio_client(server_params)
        )
        self._session = await self._stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self._session.initialize()

        # Discover Permission MCP tools → OpenAI schema
        result = await self._session.list_tools()
        self._perm_tools = [
            {"type": "function", "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.inputSchema,
            }}
            for t in result.tools
        ]

        # Register coffee shop scopes with the Permission MCP
        await self._call_perm_mcp("register_scopes", {"scopes": _SHOP_SCOPES})

        # Discover Shopify MCP tools once at startup
        try:
            async with streamablehttp_client(SHOPIFY_MCP_URL) as (sh_r, sh_w, _):
                async with ClientSession(sh_r, sh_w) as sh:
                    await sh.initialize()
                    sh_result = await sh.list_tools()
                    self._shopify_tools = [
                        {"type": "function", "function": {
                            "name": t.name,
                            "description": t.description or "",
                            "parameters": t.inputSchema,
                        }}
                        for t in sh_result.tools
                    ]
            print(f"[agent] Shopify MCP: {len(self._shopify_tools)} tools discovered")
        except Exception as exc:
            print(f"[agent] Warning: could not discover Shopify tools: {exc}")

    async def stop(self):
        if self._stack:
            await self._stack.aclose()
            self._stack = None
            self._session = None

    # ── tools list (permission + shop) ─────────────────────────────────────

    def _all_tools(self) -> list[dict[str, Any]]:
        """Combined tool list for the LLM: permission tools + Shopify tools."""
        return self._perm_tools + self._shopify_tools

    def _is_perm_tool(self, name: str) -> bool:
        return any(t["function"]["name"] == name for t in self._perm_tools)

    # ── chat ───────────────────────────────────────────────────────────────

    async def chat(self, user_message: str, user_id: str = "customer"):
        """Start a chat turn. Returns an AsyncChatStream."""
        messages = self._get_messages(user_id)
        # Inject user_id context on first real message
        if len(messages) == 1:
            user_message = f"[user_id: {user_id}]\n{user_message}"
        messages.append({"role": "user", "content": user_message})
        return AsyncChatStream(self, user_id)

    async def _run_turn(self, user_id: str, *, on_token=None, on_tool_start=None, on_tool_end=None):
        """Execute LLM turns until a final text response (handles tool loops)."""
        tools = self._all_tools()
        messages = self._get_messages(user_id)

        while True:
            # ── call LLM (streamed) ────────────────────────────────────
            payload = {
                "model": self.model,
                "messages": messages,
                "tools": tools or None,
                "stream": True,
            }

            content = ""
            tc_raw: list[dict] = []

            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}",
                             "Content-Type": "application/json"},
                    json={k: v for k, v in payload.items() if v is not None},
                ) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        err = f"LLM error {resp.status_code}: {body.decode()}"
                        if on_token:
                            await on_token(err)
                        messages.append({"role": "assistant", "content": err})
                        return

                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})

                        if delta.get("content"):
                            content += delta["content"]
                            if on_token:
                                await on_token(delta["content"])

                        if delta.get("tool_calls"):
                            for tc in delta["tool_calls"]:
                                idx = tc["index"]
                                while len(tc_raw) <= idx:
                                    tc_raw.append({"id": "", "function": {"name": "", "arguments": ""}})
                                entry = tc_raw[idx]
                                if tc.get("id"):
                                    entry["id"] = tc["id"]
                                fn = tc.get("function", {})
                                if fn.get("name"):
                                    entry["function"]["name"] += fn["name"]
                                if fn.get("arguments"):
                                    entry["function"]["arguments"] += fn["arguments"]

            # ── no tool calls → done ───────────────────────────────────
            if not tc_raw:
                messages.append({"role": "assistant", "content": content})
                return

            # ── record tool_calls in history ───────────────────────────
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": content or None}
            assistant_msg["tool_calls"] = [
                {"id": tc["id"], "type": "function", "function": tc["function"]}
                for tc in tc_raw
            ]
            messages.append(assistant_msg)

            # ── execute each tool call ─────────────────────────────────
            for tc in tc_raw:
                fn_name = tc["function"]["name"]
                try:
                    fn_args = json.loads(tc["function"]["arguments"]) if tc["function"]["arguments"] else {}
                except json.JSONDecodeError:
                    fn_args = {}

                if on_tool_start:
                    await on_tool_start(fn_name, fn_args)

                result = await self._execute_tool(fn_name, fn_args, user_id)

                if on_tool_end:
                    await on_tool_end(fn_name, result)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })
            # loop back to let LLM process tool results

    # ── tool dispatch ──────────────────────────────────────────────────

    async def _execute_tool(self, name: str, args: dict, user_id: str) -> str:
        """Route tool call to Permission MCP or Shopify MCP."""
        if self._is_perm_tool(name):
            return await self._call_perm_mcp(name, args)
        return await self._call_shopify_mcp(name, args, user_id)

    async def _call_perm_mcp(self, name: str, args: dict) -> str:
        if not self._session:
            return json.dumps({"error": "Permission MCP not connected"})
        try:
            result = await self._session.call_tool(name, arguments=args)
            return "\n".join(
                b.text if hasattr(b, "text") else str(b)
                for b in result.content
            )
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    async def _call_shopify_mcp(self, name: str, args: dict, user_id: str) -> str:
        # Inject persisted cart_id for cart operations
        if name in ("update_cart", "get_cart") and user_id in self._cart_ids:
            args.setdefault("cart_id", self._cart_ids[user_id])
        try:
            async with streamablehttp_client(SHOPIFY_MCP_URL) as (r, w, _):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    result = await session.call_tool(name, arguments=args)
                    text = "\n".join(
                        b.text if hasattr(b, "text") else str(b)
                        for b in result.content
                    )
            # Persist cart_id returned by update_cart
            if name == "update_cart":
                try:
                    data = json.loads(text)
                    cid = (data.get("cart") or {}).get("id") or data.get("id")
                    if cid:
                        self._cart_ids[user_id] = cid
                except (json.JSONDecodeError, AttributeError):
                    pass
            return text
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    async def get_user_permissions(self, user_id: str) -> list[dict]:
        """Fetch all permissions for a user from the Permission MCP."""
        raw = await self._call_perm_mcp("list_permissions", {"user_id": user_id})
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []

    def reset(self, user_id: str | None = None):
        if user_id:
            self._conversations.pop(user_id, None)
        else:
            self._conversations.clear()


# ────────────────────────────────────────────────────────────────────────────
# Streaming wrapper for WebSocket
# ────────────────────────────────────────────────────────────────────────────

class AsyncChatStream:
    def __init__(self, agent: Agent, user_id: str):
        self._agent = agent
        self._user_id = user_id

    async def events(self) -> AsyncIterator[dict]:
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        async def on_token(tok: str):
            await queue.put({"type": "token", "data": tok})

        async def on_tool_start(name: str, args: dict):
            await queue.put({"type": "tool_start", "data": {"tool": name, "args": args}})

        async def on_tool_end(name: str, result: str):
            try:
                parsed = json.loads(result)
            except (json.JSONDecodeError, TypeError):
                parsed = result
            await queue.put({"type": "tool_end", "data": {"tool": name, "result": parsed}})

        async def run():
            try:
                await self._agent._run_turn(
                    self._user_id,
                    on_token=on_token,
                    on_tool_start=on_tool_start,
                    on_tool_end=on_tool_end,
                )
            finally:
                await queue.put(None)

        task = asyncio.create_task(run())
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
        finally:
            if not task.done():
                task.cancel()

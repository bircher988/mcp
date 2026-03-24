"""
Bean & Brew — Agent
====================
Bridges OpenAI LLM with:
  • Permission MCP server  (via stdio  — manages consent)
  • Shopify native MCP     (via HTTP   — real Loutsa coffee store)

The agent exposes BOTH as "tools" to the LLM so it can seamlessly
check permissions before performing shop actions.

History summarisation: when a conversation exceeds SUMMARY_THRESHOLD
non-system messages, old messages are compressed into a single summary
message, keeping only the most recent SUMMARY_KEEP_RECENT messages.
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
    {"scope": "orders.auto_create",  "level": 5, "description": "Autonomously place repeat orders on behalf of the user (auto-reorder) — requires explicit constraints"},
]

# Static part: identity, behavioral rules, style.
# Tool names, scope lists, and permission levels are intentionally absent here —
# they are loaded dynamically from the Permission MCP at startup and appended below.
_SYSTEM_PROMPT_STATIC = """\
You are the friendly assistant for **Loutsa**, a French artisan coffee roaster \
(loutsa-torrefacteur.myshopify.com). Help customers discover and buy great coffee.

The current user's ID is provided in the first user message as [user_id: ...].
Use that user_id in ALL permission tool calls.

## Permission workflow — ALL scoped actions

**Every shop action is gated by a scope. You MUST call `check_permission`
before EVERY shop tool call, including read-only catalog searches.**

Example of the required call sequence — browsing the catalog:
  1. call `check_permission(user_id=..., scope="catalog.browse")`
  2. → returns `{"granted": true}` (auto-granted for L1)
  3. call `search_shop_catalog(...)`

NEVER call a Shopify MCP tool (`search_shop_catalog`, `get_product_details`,
`update_cart`, `get_cart`, `search_shop_policies_and_faqs`) without first
calling `check_permission` for the matching scope.

Level 1 scopes are **auto-granted instantly** — `check_permission` returns
`"granted": true` immediately (or `false` on first call, in which case call
`request_permission` which returns `"status": "granted"` instantly). This is
transparent; do NOT mention it to the user. Just check, get the grant, proceed.

For Level 2+ scopes, follow the explicit consent workflow below.

### Scope → shop tool mapping
| Scope | Shop tool(s) |
|---|---|
| `catalog.browse` | `search_shop_catalog` |
| `product.view` | `get_product_details` |
| `cart.manage` | `update_cart`, `get_cart` |
| `policies.read` | `search_shop_policies_and_faqs` |
| `delivery.address` | `update_cart` with address fields |
| `profile.save_address` | storing address cross-session (agent-initiated) |
| `checkout` | `get_cart` to retrieve checkout URL |
| `orders.auto_create` | autonomous repeat ordering |

## Permission workflow for Level 2+ scopes

Before any Level 2+ action, call `check_permission` first.
If NOT already granted:
  1. Call `request_permission` and present the returned `value_proposition` to the user.
  2. Ask the user to approve. Do NOT call `grant_permission` yet — wait for explicit consent.
  3. **When the user agrees (yes / ok / sure / go ahead / etc.) → your VERY FIRST
     tool call MUST be `grant_permission` for that scope. Do not call any other
     tool before `grant_permission` succeeds.**
     Never say "I've saved it" or "done" without first calling `grant_permission`.
  4. Only after `grant_permission` returns `"status": "granted"` should you proceed
     with the action (e.g., fetching the cart, saving data).

## Cart behaviour

- A cart is created automatically on the first shop cart action (no cart_id needed).
- Reuse the same cart for the entire session.
- Never share the raw cart_id with the user — present the checkout URL instead.
- Address updates and checkout are separate steps — never include the checkout URL
  in the same response as an address update.
- Do **not** proactively present the checkout URL unless the user has explicitly
  asked to checkout AND the `checkout` permission has already been verified.
- When the user explicitly asks to checkout / complete their order:
  1. Call `check_permission` for `checkout` first — never skip this step.
  2. If not yet granted, call `request_permission` and present the value proposition.
  3. Wait for explicit user approval, then call `grant_permission`.
  4. Only after the `checkout` permission is confirmed, call `get_cart` and present the checkout URL.
- After successfully adding a delivery address, always ask:
  "Want me to remember this address for your next visit?"
  If yes, request and grant the address-persistence scope before confirming.

## Level 5 — Agentic auto-reorder (orders.auto_create)

When the user asks to set up automatic or recurring coffee orders:
1. Call `check_permission` for `orders.auto_create`.
2. If not granted, call `request_permission` and explain Level 5 requires explicit delegation.
3. Before calling `grant_permission`, negotiate explicit constraints with the user:
   - **max_price_eur**: maximum spend per auto-order (e.g. 30.0)
   - **frequency**: how often to re-order (e.g. "monthly", "bi-weekly")
   - **product**: which product to reorder (e.g. "Grain 250g")
   - **notify_before_order**: always true — the agent notifies before placing
4. Only call `grant_permission` once the user has confirmed all constraints.
   Pass them as a `constraints` dict — the server **requires** constraints for Level 5.
5. After granting, state the constraints back to the user so they know exactly
   what they have delegated. Example: "I'll automatically reorder Grain 250g once
   a month, at most €30 per order. I'll notify you before each order."

## Style

- Respond in the same language the user writes in (French or English).
- Be warm, knowledgeable about specialty coffee — like a real barista.
- Format products attractively when presenting them.
- Suggest next steps naturally, never pressure.
- When presenting the checkout URL, format it as a clickable link.
"""

DEFAULT_MODEL = "gpt-4o"

SUMMARY_THRESHOLD = 20   # trigger summarisation after this many non-system messages
SUMMARY_KEEP_RECENT = 6  # keep last N non-system messages after summarising

# Retry delays (seconds) for 429 rate-limit responses — tried in order
_RETRY_DELAYS = [15, 30, 60, 90, 120]


# ────────────────────────────────────────────────────────────────────────────
# Agent
# ────────────────────────────────────────────────────────────────────────────

class Agent:
    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        self.model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
        self.base_url = "https://api.openai.com/v1"
        self._conversations: dict[str, list[dict[str, Any]]] = {}  # per-user
        self._perm_tools: list[dict[str, Any]] = []   # discovered from Permission MCP
        self._shopify_tools: list[dict[str, Any]] = []  # discovered from Shopify MCP
        self._session: ClientSession | None = None
        self._stack: AsyncExitStack | None = None
        self._cart_ids: dict[str, str] = {}  # user_id → Shopify cart GID
        self._dynamic_context: str = ""  # ladder + scopes fetched from Permission MCP at startup

    def _get_messages(self, user_id: str) -> list[dict[str, Any]]:
        """Return (or create) the conversation history for a user."""
        if user_id not in self._conversations:
            system_content = _SYSTEM_PROMPT_STATIC
            if self._dynamic_context:
                system_content += "\n\n" + self._dynamic_context
            self._conversations[user_id] = [{"role": "system", "content": system_content}]
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

        # Build dynamic context from the MCP server itself (ladder + registered scopes)
        self._dynamic_context = await self._fetch_permission_context()

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

    async def _fetch_permission_context(self) -> str:
        """Fetch ladder and registered scopes from the MCP server and format as a context block."""
        try:
            ladder_raw = await self._call_perm_mcp("get_permission_ladder", {})
            scopes_raw = await self._call_perm_mcp("get_registered_scopes", {})
            ladder_data = json.loads(ladder_raw)
            scopes_data = json.loads(scopes_raw)

            lines = ["## Permission context (loaded from Permission MCP at startup)", ""]

            lines.append("### Permission ladder")
            for entry in ladder_data.get("ladder", []):
                auto = " — auto-granted" if entry.get("auto_grant") else ""
                lines.append(
                    f"- Level {entry['level']} **{entry['label']}**{auto}: "
                    f"{entry['description']}. "
                    f"Requires: {entry['requires']}. "
                    f"Value: {entry['value_proposition']}."
                )

            lines.append("")
            lines.append("### Registered scopes")
            for level_str, scopes in sorted(
                scopes_data.get("scopes_by_level", {}).items(), key=lambda x: int(x[0])
            ):
                for s in scopes:
                    auto = " (auto-granted)" if int(level_str) == 1 else ""
                    lines.append(
                        f"- `{s['scope']}` → Level {level_str}{auto}: {s.get('description', '')}"
                    )

            return "\n".join(lines)
        except Exception as exc:
            print(f"[agent] Warning: could not build permission context: {exc}")
            return ""

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

    # ── history summarisation ──────────────────────────────────────────────

    async def _maybe_summarise(self, user_id: str) -> None:
        """Compress old history into a summary when it grows too long.

        Keeps: [system_prompt, summary_message, *last SUMMARY_KEEP_RECENT messages]
        """
        messages = self._get_messages(user_id)
        non_system = [m for m in messages if m["role"] != "system"]
        if len(non_system) <= SUMMARY_THRESHOLD:
            return

        system_msg = messages[0]
        to_summarise = messages[1: -SUMMARY_KEEP_RECENT]
        recent = messages[-SUMMARY_KEEP_RECENT:]

        summary_prompt = (
            "You are a summarisation assistant. "
            "Produce a concise but complete summary of the following conversation excerpt. "
            f"CRITICAL: The user_id for ALL permission tool calls is: {user_id} — always preserve this exactly. "
            "Preserve key facts: user_id, what the user asked, what products/items were discussed, "
            "cart state, permissions granted or requested, and any pending actions. "
            "Reply with the summary only, no extra commentary.\n\n"
            + "\n".join(
                f"{m['role'].upper()}: {m.get('content') or ''}"
                for m in to_summarise
                if m.get("content")
            )
        )

        summary: str | None = None
        for attempt in range(len(_RETRY_DELAYS) + 1):
            if attempt > 0:
                wait = _RETRY_DELAYS[attempt - 1]
                print(f"[agent] summarisation 429 — retrying in {wait}s (attempt {attempt}/{len(_RETRY_DELAYS)})...")
                await asyncio.sleep(wait)
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}",
                                 "Content-Type": "application/json"},
                        json={
                            "model": self.model,
                            "messages": [{"role": "user", "content": summary_prompt}],
                            "stream": False,
                        },
                    )
                    if resp.status_code == 429 and attempt < len(_RETRY_DELAYS):
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    summary = data["choices"][0]["message"]["content"].strip()
                    break
            except Exception as exc:
                if attempt < len(_RETRY_DELAYS):
                    continue
                print(f"[agent] summarisation failed after {attempt + 1} attempts, keeping full history: {exc}")
                return
        if summary is None:
            print("[agent] summarisation gave up — keeping full history")
            return

        self._conversations[user_id] = [
            system_msg,
            {"role": "assistant",
             "content": f"[Conversation summary — older messages compressed]\nUser ID: {user_id}\n{summary}"},
            *recent,
        ]
        print(
            f"[agent] history summarised for {user_id!r}: "
            f"{len(to_summarise)} messages → 1 summary + {len(recent)} recent"
        )

    async def _run_turn(self, user_id: str, *, on_token=None, on_tool_start=None, on_tool_end=None):
        """Execute LLM turns until a final text response (handles tool loops)."""
        await self._maybe_summarise(user_id)
        tools = self._all_tools()
        messages = self._get_messages(user_id)

        while True:
            # ── call LLM (streamed) with retry on 429 ─────────────────
            payload = {
                "model": self.model,
                "messages": messages,
                "tools": tools or None,
                "stream": True,
            }

            content = ""
            tc_raw: list[dict] = []

            for attempt in range(len(_RETRY_DELAYS) + 1):
                if attempt > 0:
                    wait = _RETRY_DELAYS[attempt - 1]
                    print(f"[agent] 429 TPM rate limit — retrying in {wait}s (attempt {attempt}/{len(_RETRY_DELAYS)})...")
                    await asyncio.sleep(wait)

                _got_429 = False
                content = ""
                tc_raw = []

                async with httpx.AsyncClient(timeout=120) as client:
                    async with client.stream(
                        "POST",
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}",
                                 "Content-Type": "application/json"},
                        json={k: v for k, v in payload.items() if v is not None},
                    ) as resp:
                        if resp.status_code == 429:
                            _got_429 = True
                        elif resp.status_code != 200:
                            body = await resp.aread()
                            err = f"LLM error {resp.status_code}: {body.decode()}"
                            if on_token:
                                await on_token(err)
                            messages.append({"role": "assistant", "content": err})
                            return
                        else:
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

                if _got_429 and attempt < len(_RETRY_DELAYS):
                    continue
                if _got_429:
                    err = f"LLM error 429: rate limit exhausted after {len(_RETRY_DELAYS)} retries"
                    if on_token:
                        await on_token(err)
                    messages.append({"role": "assistant", "content": err})
                    return
                break  # success — exit retry loop

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
        """Fetch all permissions for a user from the Permission MCP.

        Normalises the MCP response (dict with 'permissions' map) into a flat
        list of grant dicts that the browser's renderPermissions() can iterate.
        """
        raw = await self._call_perm_mcp("list_permissions", {"user_id": user_id})
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []

        # MCP returns {"permissions": {scope: grant_dict, ...}, ...}
        perms_map = data.get("permissions", {}) if isinstance(data, dict) else {}
        if isinstance(perms_map, dict):
            return [
                {"scope": scope, **info} if isinstance(info, dict)
                else {"scope": scope, "status": "granted"}
                for scope, info in perms_map.items()
            ]
        # Fallback: already a list
        return data if isinstance(data, list) else []

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

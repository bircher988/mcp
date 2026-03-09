/* ============================================================
   Bean & Brew — Chat widget  (WebSocket client)
   ============================================================ */

(() => {
  const toggle   = document.getElementById("chat-toggle");
  const panel    = document.getElementById("chat-panel");
  const closeBtn = document.getElementById("chat-close");
  const form     = document.getElementById("chat-form");
  const input    = document.getElementById("chat-input");
  const msgList  = document.getElementById("chat-messages");

  // Debug overlay elements
  const debugToggle  = document.getElementById("debug-toggle");
  const debugOverlay = document.getElementById("debug-overlay");
  const debugClose   = document.getElementById("debug-close");
  const debugContent = document.getElementById("debug-content");
  const debugRefresh = document.getElementById("debug-refresh");
  const debugUserId  = document.getElementById("debug-user-id");

  let ws = null;
  let curEl = null;   // assistant message element being streamed
  let curText = "";

  // ── user identity ─────────────────────────────────────────
  let userId = localStorage.getItem("bb_user_id");
  if (!userId) {
    userId = crypto.randomUUID();
    localStorage.setItem("bb_user_id", userId);
  }
  debugUserId.textContent = userId.slice(0, 8) + "…";

  // ── open / close chat ─────────────────────────────────────
  toggle.addEventListener("click", () => {
    panel.classList.remove("hidden");
    toggle.classList.add("hidden");
    input.focus();
    ensureWs();
  });
  closeBtn.addEventListener("click", () => {
    panel.classList.add("hidden");
    toggle.classList.remove("hidden");
  });

  // ── debug overlay ─────────────────────────────────────────
  debugToggle.addEventListener("click", () => {
    debugOverlay.classList.remove("hidden");
    ensureWs();
    requestPermissions();
  });
  debugClose.addEventListener("click", () => {
    debugOverlay.classList.add("hidden");
  });
  debugRefresh.addEventListener("click", () => {
    ensureWs();
    requestPermissions();
  });

  function requestPermissions() {
    if (!ws || ws.readyState !== 1) return;
    ws.send(JSON.stringify({ type: "get_permissions", user_id: userId }));
  }

  function renderPermissions(perms) {
    if (!perms || !Array.isArray(perms) || perms.length === 0) {
      debugContent.innerHTML = '<p class="perm-no-perms">No permissions granted yet. Start chatting to request some!</p>';
      return;
    }
    debugContent.innerHTML = perms.map(p => {
      const level = p.level || "?";
      const status = (p.status || "granted").toLowerCase();
      const scope = p.scope || p.scope_id || "unknown";
      return `<div class="perm-row">
        <span class="perm-scope">${escHtml(scope)}</span>
        <span class="perm-level" data-level="${level}">L${level}</span>
        <span class="perm-status ${status}">${status}</span>
      </div>`;
    }).join("");
  }

  function escHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  // ── WebSocket ─────────────────────────────────────────────
  function ensureWs() {
    if (ws && ws.readyState <= 1) return;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws/chat`);
    ws.onmessage = onMsg;
    ws.onclose = () => { ws = null; };
  }

  const PERM_TOOLS = new Set([
    "request_permission", "grant_permission", "check_permission",
    "revoke_permission", "list_permissions", "get_permission_ladder",
    "get_registered_scopes", "get_audit_trail", "register_scopes",
  ]);

  function onMsg(ev) {
    let e;
    try { e = JSON.parse(ev.data); } catch { return; }

    switch (e.type) {
      case "token":
        if (!curEl) startAssistant();
        curText += e.data;
        curEl.querySelector(".msg-content").textContent = curText;
        scrollEnd();
        break;

      case "tool_start": {
        const isPerm = PERM_TOOLS.has(e.data.tool);
        const icon = isPerm ? "🔐" : "⚙️";
        addToolBubble(`${icon} ${friendly(e.data.tool)}…`, isPerm);
        break;
      }

      case "tool_end":
        break;

      case "done":
        removeTyping();
        curEl = null;
        curText = "";
        break;

      case "permissions":
        renderPermissions(e.data);
        break;

      case "error":
        addAssistant(`⚠️ ${e.data}`);
        break;
    }
  }

  // ── send ──────────────────────────────────────────────────
  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const txt = input.value.trim();
    if (!txt) return;
    addUser(txt);
    input.value = "";
    ensureWs();
    addTyping();
    ws.send(JSON.stringify({ message: txt, user_id: userId }));
  });

  // ── DOM helpers ───────────────────────────────────────────
  function addUser(text) {
    const d = document.createElement("div");
    d.className = "msg user";
    d.innerHTML = `<div class="msg-content"></div>`;
    d.querySelector(".msg-content").textContent = text;
    msgList.appendChild(d);
    scrollEnd();
  }

  function addAssistant(text) {
    const d = document.createElement("div");
    d.className = "msg assistant";
    d.innerHTML = `<div class="msg-content"></div>`;
    d.querySelector(".msg-content").textContent = text;
    msgList.appendChild(d);
    scrollEnd();
    return d;
  }

  function startAssistant() {
    removeTyping();
    curText = "";
    curEl = addAssistant("");
  }

  function addToolBubble(text, isPerm) {
    const d = document.createElement("div");
    d.className = "msg tool" + (isPerm ? " perm" : "");
    d.innerHTML = `<div class="msg-content"></div>`;
    d.querySelector(".msg-content").textContent = text;
    msgList.appendChild(d);
    scrollEnd();
  }

  function addTyping() {
    removeTyping();
    const d = document.createElement("div");
    d.className = "typing-indicator";
    d.id = "typing";
    d.innerHTML = "<span></span><span></span><span></span>";
    msgList.appendChild(d);
    scrollEnd();
  }

  function removeTyping() {
    const el = document.getElementById("typing");
    if (el) el.remove();
  }

  function scrollEnd() {
    msgList.scrollTop = msgList.scrollHeight;
  }

  // ── friendly names ────────────────────────────────────────
  function friendly(name) {
    const m = {
      search_shop_catalog:          "Browsing Loutsa catalog",
      get_product_details:          "Looking up product",
      get_cart:                     "Getting your cart",
      update_cart:                  "Updating cart",
      search_shop_policies_and_faqs:"Checking store policies",
      request_permission:           "Requesting permission",
      grant_permission:             "Granting permission",
      check_permission:             "Checking permission",
      list_permissions:             "Listing permissions",
      revoke_permission:            "Revoking permission",
      get_permission_ladder:        "Loading permission ladder",
      get_registered_scopes:        "Loading scopes",
      get_audit_trail:              "Loading audit trail",
      register_scopes:              "Registering scopes",
    };
    return m[name] || name.replace(/_/g, " ");
  }
})();

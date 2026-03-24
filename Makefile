.PHONY: help install install-mcp install-demo run-mcp run-demo inspect clean

PYTHON        := python3
DEMO_DIR      := demo
MCP_VENV      := .venv
DEMO_VENV     := $(DEMO_DIR)/.venv

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ── Install ──────────────────────────────────────────────────────────────────

install: install-mcp install-demo ## Install all dependencies

install-mcp: ## Install MCP server dependencies
	$(PYTHON) -m venv $(MCP_VENV)
	$(MCP_VENV)/bin/pip install -q --upgrade pip
	$(MCP_VENV)/bin/pip install -q -r requirements.txt

install-demo: ## Install demo app dependencies (uses uv)
	cd $(DEMO_DIR) && uv sync

# ── Run ───────────────────────────────────────────────────────────────────────

run-demo: ## Start the Bean & Brew demo app (port 8000)
	cd $(DEMO_DIR) && uv run python run.py

run-demo-port: ## Start the demo on a custom port: make run-demo-port PORT=3000
	cd $(DEMO_DIR) && uv run python run.py --port $(PORT)

run-mcp: ## Run the MCP server directly (stdio)
	$(DEMO_VENV)/bin/python permission_mcp/server.py

# ── Inspect ───────────────────────────────────────────────────────────────────

inspect: ## Open MCP Inspector (Swagger-like UI) for the MCP server
	@echo "→ Opening MCP Inspector. When the browser opens, click 'Connect' to load your tools."
	npx @modelcontextprotocol/inspector $(DEMO_VENV)/bin/python permission_mcp/server.py

# ── Clean ─────────────────────────────────────────────────────────────────────

clean: ## Remove virtual environments and caches
	rm -rf $(MCP_VENV)
	rm -rf $(DEMO_DIR)/.venv
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete

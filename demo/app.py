"""
Bean & Brew — FastAPI Web App
Serves the shop UI and handles chat via WebSocket.
"""

from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agent import Agent

load_dotenv(Path(__file__).resolve().parent / ".env")

app = FastAPI(title="Bean & Brew Coffee Shop")

STATIC = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

agent: Agent | None = None


@app.on_event("startup")
async def startup():
    global agent
    agent = Agent()
    await agent.start()


@app.on_event("shutdown")
async def shutdown():
    if agent:
        await agent.stop()


@app.get("/")
async def index():
    return FileResponse(str(STATIC / "index.html"))


@app.websocket("/ws/chat")
async def chat_ws(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                msg = {"message": raw}

            if not agent:
                await ws.send_text(json.dumps({"type": "error", "data": "Agent not ready."}))
                continue

            user_id = msg.get("user_id", "customer")

            # Handle debug permission query
            if msg.get("type") == "get_permissions":
                perms = await agent.get_user_permissions(user_id)
                await ws.send_text(json.dumps({"type": "permissions", "data": perms}))
                continue

            text = msg.get("message", "").strip()
            if not text:
                continue

            stream = await agent.chat(text, user_id=user_id)
            async for event in stream.events():
                await ws.send_text(json.dumps(event))
            await ws.send_text(json.dumps({"type": "done"}))
    except WebSocketDisconnect:
        pass

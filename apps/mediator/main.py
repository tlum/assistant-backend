# apps/mediator/main.py
# MediatorAgent – exposes POST /v1/chat/completions (OpenAI-style)

import os, asyncio, uuid, logging
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Request, Header, HTTPException
from libs.bus import publish, subscribe_once        # already in repo
from libs.llm import chat                           # already in repo

# ──────────────────────────────────────────────────────────────
# CONFIG
MEDIATOR_API_KEY: str = os.getenv("MEDIATOR_API_KEY", "")
if not MEDIATOR_API_KEY:
    raise RuntimeError("MEDIATOR_API_KEY env-var not set (secret mount missing)")

GATHER_TIMEOUT_SEC: float = 0.4
log = logging.getLogger("mediator")
app = FastAPI()
# ──────────────────────────────────────────────────────────────


async def gather_agent_notes(corr_id: str) -> str:
    """Collect AGENT_NOTE events for a short window."""
    notes: List[str] = []

    async def _collect() -> None:
        async for evt in subscribe_once(corr_id):
            if evt.get("type", "").startswith("AGENT_NOTE"):
                notes.append(evt["payload"])

    try:
        await asyncio.wait_for(_collect(), timeout=GATHER_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        pass

    return "\n".join(f"- {n}" for n in notes)


def _require_api_key(authorization: Optional[str]) -> None:
    """Raise 401 unless Authorization: Bearer <token> matches secret."""
    token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if token != MEDIATOR_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def _extract_user_message(body: Dict[str, Any]) -> str:
    """
    Return the content of the last 'user' role in body['messages'].
    Vapi sends messages = [system, assistant?, user]
    """
    for msg in reversed(body["messages"]):
        if msg["role"] == "user":
            return msg["content"]
    raise HTTPException(status_code=422, detail="No user message found")


@app.post("/v1/chat/completions")
async def completions(
    req: Request,
    authorization: str | None = Header(None),
):
    # 1 ▸ API-key auth
    _require_api_key(authorization)

    # 2 ▸ Parse request body
    body: Dict[str, Any] = await req.json()
    user_msg: str = _extract_user_message(body)

    corr_id: str = str(uuid.uuid4())

    # 3 ▸ Fan-out the user message
    await publish(
        {
            "id": corr_id,
            "type": "NEW_USER_MSG",
            "payload": {"text": user_msg},
        }
    )

    # 4 ▸ Collect helper-agent notes (non-blocking)
    notes: str = await gather_agent_notes(corr_id)

    # 5 ▸ Synthesize reply
    prompt = (
        f"User said:\n{user_msg}\n\n"
        f"Helper notes:\n{notes or '(none)'}\n\n"
        "Craft the best single-turn assistant reply."
    )
    reply: str = await chat(prompt)

    # 6 ▸ Publish BOT_REPLY for logging / other consumers
    await publish(
        {
            "id": corr_id,
            "type": "BOT_REPLY",
            "payload": {"text": reply},
        }
    )

    # 7 ▸ Return OpenAI-style response
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": reply,
                }
            }
        ]
    }


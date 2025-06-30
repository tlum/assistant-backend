# MediatorAgent – exposes /v1/chat/completions (OpenAI-style)

import os, asyncio, uuid, logging
from fastapi import FastAPI, Request, Header, HTTPException

from libs.bus import publish, subscribe_once    # publish already exists
from libs.llm import chat                       # same helper used by echo-agent

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG
MEDIATOR_API_KEY = os.getenv("MEDIATOR_API_KEY")
if not MEDIATOR_API_KEY:
    raise RuntimeError("MEDIATOR_API_KEY env-var not set (secret mount missing)")

# ──────────────────────────────────────────────────────────────────────────────
app = FastAPI()
log = logging.getLogger("mediator")


async def gather_agent_notes(correlation_id: str, timeout: float = 0.4) -> str:
    """
    Wait `timeout` seconds for any events tagged with the correlation_id.
    Returns a newline-joined string of their payloads.
    """
    notes: list[str] = []

    async def _collect() -> None:
        async for evt in subscribe_once(correlation_id):
            if evt.get("type", "").startswith("AGENT_NOTE"):
                notes.append(evt["payload"])

    try:
        await asyncio.wait_for(_collect(), timeout=timeout)
    except asyncio.TimeoutError:
        pass

    return "\n".join(f"- {n}" for n in notes)


@app.post("/v1/chat/completions")
async def completions(
    req: Request,
    x_api_key: str = Header(...),
):
    # ─── API-key check ────────────────────────────────────────────────────────
    if x_api_key != MEDIATOR_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    body = await req.json()
    user_msg = body["messages"][-1]["content"]

    corr_id = str(uuid.uuid4())  # correlate downstream events

    # 1⃣  publish user message so helper agents can react
    await publish(
        {
            "id": corr_id,
            "type": "NEW_USER_MSG",
            "payload": {"text": user_msg},
        }
    )

    # 2⃣  wait briefly for helper notes
    notes = await gather_agent_notes(corr_id)

    # 3⃣  synthesis prompt
    prompt = (
        f"User said:\n{user_msg}\n\n"
        f"Helpful background information from other agents (may be empty):\n{notes}\n\n"
        "Craft the best single-turn assistant reply."
    )
    reply = await chat(prompt)

    # 4⃣  publish final reply
    await publish(
        {
            "id": corr_id,
            "type": "BOT_REPLY",
            "payload": {"text": reply},
        }
    )

    # 5⃣  OpenAI-compatible response
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


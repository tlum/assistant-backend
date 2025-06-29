# MediatorAgent – exposes /v1/chat/completions (OpenAI-style)

from fastapi import FastAPI, Request
from libs.bus import publish, subscribe_once  # you already have publish
from libs.llm import chat                     # same helper used by echo-agent
import asyncio, uuid, logging

app = FastAPI()
log = logging.getLogger("mediator")

# helper: collect notes other agents publish against this correlation-id
async def gather_agent_notes(correlation_id: str, timeout: float = 0.4) -> str:
    """
    Wait `timeout` seconds for any events tagged with the correlation_id.
    Returns a newline-joined string of their payloads.
    """
    notes = []

    async def _collect():
        async for evt in subscribe_once(correlation_id):  # stop when timeout hits
            if evt.get("type", "").startswith("AGENT_NOTE"):
                notes.append(evt["payload"])

    try:
        await asyncio.wait_for(_collect(), timeout=timeout)
    except asyncio.TimeoutError:
        pass

    return "\n".join(f"- {n}" for n in notes)

@app.post("/v1/chat/completions")
async def completions(req: Request):
    body = await req.json()
    user_msg = body["messages"][-1]["content"]

    # unique id so downstream agents can correlate replies
    corr_id = str(uuid.uuid4())

    # 1️⃣ fan-out the user message
    await publish({
        "id": corr_id,
        "type": "NEW_USER_MSG",
        "payload": {"text": user_msg},
    })

    # 2️⃣ wait briefly for any helper agents
    notes = await gather_agent_notes(corr_id)

    # 3️⃣ synthesis prompt
    prompt = (
        f"User said:\n{user_msg}\n\n"
        f"Helpful background information from other agents (may be empty):\n{notes}\n\n"
        "Craft the best single-turn assistant reply."
    )
    reply = await chat(prompt)

    # 4️⃣ publish the final BOT_REPLY (so logging / UI feeds can consume it)
    await publish({
        "id": corr_id,
        "type": "BOT_REPLY",
        "payload": {"text": reply},
    })

    # 5️⃣ return OpenAI-compatible JSON
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


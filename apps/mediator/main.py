# apps/mediator/main.py
# MediatorAgent – POST /v1/chat/completions (OpenAI-compatible)

import os, asyncio, uuid, logging, time, itertools, json
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from libs.bus import publish, subscribe_once
from libs.llm import chat_completion
from libs import tracer, tools

# ───────────────────────── CONFIG ────────────────────────────
MEDIATOR_API_KEY = os.getenv("MEDIATOR_API_KEY", "")
if not MEDIATOR_API_KEY:
    raise RuntimeError("MEDIATOR_API_KEY env-var not set")

GATHER_TIMEOUT_SEC = 0.4
log = logging.getLogger("mediator")
app = FastAPI()
# ─────────────────────────────────────────────────────────────


async def gather_agent_notes(corr_id: str) -> str:
    notes: List[str] = []

    async def _collect():
        async for evt in subscribe_once(corr_id):
            if evt.get("type", "").startswith("AGENT_NOTE"):
                notes.append(evt["payload"])

    try:
        await asyncio.wait_for(_collect(), timeout=GATHER_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        pass
    return "\n".join(f"- {n}" for n in notes)


def _require_api_key(authorization: Optional[str]) -> None:
    token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if token != MEDIATOR_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def _extract_user_message(body: Dict[str, Any]) -> str:
    for msg in reversed(body.get("messages", [])):
        if msg.get("role") == "user":
            return msg["content"]
    raise HTTPException(status_code=422, detail="No user message found")


@app.post("/v1/chat/completions")
async def completions(req: Request, authorization: str | None = Header(None)):
    trace_id = tracer.new_id()
    wall_start = time.time()
    _require_api_key(authorization)

    body: Dict[str, Any] = await req.json()
    user_msg = _extract_user_message(body)
    tracer.write("mediator_calls", trace_id, vapi_request=body)

    corr_id = uuid.uuid4().hex
    await publish({"id": corr_id, "type": "NEW_USER_MSG", "payload": {"text": user_msg}})

    notes = await gather_agent_notes(corr_id)

    # Build outbound messages (preserving original order)
    outbound_msgs = body["messages"].copy()
    if notes:
        outbound_msgs.append({"role": "system", "content": f"Helper notes:\n{notes}"})

    # Function schema allowed for this call
    functions_schema = None
    if body.get("tools"):
        wanted = {t["function"]["name"] for t in body["tools"]}
        functions_schema = [s for s in tools.json_schema() if s["name"] in wanted]

    # ─── First LLM call ───────────────────────────────────────
    openai_resp = await chat_completion(
        messages=outbound_msgs,
        temperature=body.get("temperature", 1),
        stream=False,
        functions=functions_schema,
    )

    first_msg = openai_resp.choices[0].message
    reply_content = first_msg.content or ""        # may be None if function_call
    usage_dict = openai_resp.usage.model_dump()
    
    # ─── Tool call branch ─────────────────────────────────────
    if first_msg.function_call:
        fc = first_msg.function_call
        tool_result = tools.call(fc.name, json.loads(fc.arguments or "{}"))

        follow_msgs = (
            outbound_msgs
            + [first_msg]  # assistant w/ function_call
            + [{"role": "tool", "name": fc.name, "content": tool_result}]
        )

        openai_resp = await chat_completion(
            messages=follow_msgs,
            temperature=body.get("temperature", 1),
            stream=False,
        )
        second_msg = openai_resp.choices[0].message
        reply_content = second_msg.content or ""
        usage_dict = openai_resp.usage.model_dump()

    # Publish final bot reply
    await publish({"id": corr_id, "type": "BOT_REPLY", "payload": {"text": reply_content}})

    tracer.write(
        "openai_calls",
        trace_id,
        request={"model": openai_resp.model, "messages": outbound_msgs},
        usage=usage_dict,
    )

    envelope = {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": openai_resp.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": reply_content,
                    "refusal": None,
                    "annotations": [],
                },
                "logprobs": None,
                "finish_reason": "stop",
            }
        ],
        "usage": usage_dict,
        "service_tier": "default",
    }

    tracer.write(
        "mediator_calls",
        trace_id,
        vapi_response=envelope,
        latency_ms=int((time.time() - wall_start) * 1000),
    )

    # ─── Simple streaming path (content only, no tool call) ──
    if body.get("stream") and not first_msg.function_call:
        def sse_chunks():
            yield (
                "data: "
                + json.dumps(
                    {
                        "id": envelope["id"],
                        "object": "chat.completion.chunk",
                        "created": envelope["created"],
                        "model": envelope["model"],
                        "choices": [
                            {"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}
                        ],
                    }
                )
                + "\n\n"
            )

            for part in itertools.islice(
                (reply_content[i : i + 40] for i in range(0, len(reply_content), 40)),
                None,
            ):
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "id": envelope["id"],
                            "object": "chat.completion.chunk",
                            "created": envelope["created"],
                            "model": envelope["model"],
                            "choices": [
                                {"index": 0, "delta": {"content": part}, "finish_reason": None}
                            ],
                        }
                    )
                    + "\n\n"
                )

            yield (
                "data: "
                + json.dumps(
                    {
                        "id": envelope["id"],
                        "object": "chat.completion.chunk",
                        "created": envelope["created"],
                        "model": envelope["model"],
                        "choices": [
                            {"index": 0, "delta": {}, "finish_reason": "stop"}
                        ],
                    }
                )
                + "\n\n"
            )
            yield "data: [DONE]\n\n"

        return StreamingResponse(sse_chunks(), media_type="text/event-stream")

    return JSONResponse(envelope)


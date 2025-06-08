# main.py

import os
from fastapi import FastAPI, Request, HTTPException, Depends, Header, status
from starlette.responses import JSONResponse
import openai # <--- KEEP THIS LINE
from openai import OpenAI # <--- Add this line
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────
app = FastAPI()

# Make sure you’ve set these in Cloud Run (or in your local env for testing)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERVICE_API_KEY = os.getenv("SERVICE_API_KEY")

logger.info(f"OPENAI_API_KEY: {'Set' if OPENAI_API_KEY else 'Not Set'}")
logger.info(f"SERVICE_API_KEY: {'Set' if SERVICE_API_KEY else 'Not Set'}")

if not OPENAI_API_KEY or not SERVICE_API_KEY:
    logger.error("OPENAI_API_KEY and SERVICE_API_KEY must be set. Exiting.")
    raise RuntimeError("OPENAI_API_KEY and SERVICE_API_KEY must be set")

# Initialize the OpenAI client here
openai_client = OpenAI() # This will automatically pick up OPENAI_API_KEY from env var
logger.info("OpenAI API client initialized.")


# ─── Dependency: verify incoming Bearer token matches VAPI_API_KEY ────────────
async def verify_inbound_secret(authorization: str = Header(...)):
    """
    Expect header: Authorization: Bearer <SERVICE_API_KEY>
    """
    scheme, _, token = authorization.partition(" ")
    logger.info(f"Attempting to verify token. Scheme: {scheme}, Token starts with: {token[:5]}...")
    if scheme.lower() != "bearer" or token != SERVICE_API_KEY:
        logger.warning("Invalid or missing API token provided.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token"
        )
    logger.info("API token verified successfully.")


# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    logger.info("Health check endpoint hit.")
    return {"status": "ok"}

# ─── OpenAI ChatCompletion proxy (Custom LLM endpoint) ────────────────────────
@app.post(
    "/chat/completions",
    dependencies=[Depends(verify_inbound_secret)]
)
async def chat_completions(request: Request):
    logger.info("Chat completions endpoint hit.")
    payload = await request.json()
    logger.info(f"Received raw payload: {payload}")

    # Define a set of valid parameters for chat.completions.create
    valid_openai_params = {
        "messages", "model", "frequency_penalty", "logit_bias", "logprobs",
        "top_logprobs", "max_tokens", "n", "presence_penalty", "response_format",
        "seed", "service_tier", "stop", "stream", "temperature", "tool_choice",
        "tools", "top_p", "user"
    }

    # Create a new payload containing only valid parameters
    cleaned_payload = {k: v for k, v in payload.items() if k in valid_openai_params}

    #
    # ─── 2) HAND OFF TO YOUR DISPATCHER ──────────────────────────
    #
    # Extract session & user text
    session_id = payload.get("call", {}).get("id") or payload.get("session_id")
    # Last message is the user’s turn
    messages = cleaned_payload.get("messages", [])
    user_text = ""
    if messages and messages[-1]["role"] == "user":
        user_text = messages[-1]["content"]

    # Call your Dispatcher / AgentRegistry
    # You’ll write this function to emit Event → agents → reply_text
    from dispatcher import dispatch_input
    reply_text = await dispatch_input(
        session_id=session_id,
        user_input=user_text,
        channel="voice"  # or derive from payload
    )

    # Build a ChatCompletion‐style response for Vapi
    completion = {
        "id": f"local-{session_id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": cleaned_payload.get("model"),
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": reply_text
                },
                "finish_reason": "stop"
            }
        ]
    }
    return JSONResponse(completion)


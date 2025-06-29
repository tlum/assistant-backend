"""libs/bus.py
A thin, *async‑friendly* helper around Google Cloud Pub/Sub that provides two
capabilities used throughout the micro‑service architecture:

1. **publish** – fire‑and‑forget JSON messages to the shared `assistant-events`
   topic.
2. **subscribe_once** – an async generator that yields messages with a matching
   `id` (correlation‑id) for up to *timeout* seconds.  The MediatorAgent relies
   on this to gather responses from other agents within a single HTTP request
   window.

The module auto‑detects the GCP project ID whether running on Cloud Run,
locally with `PROJECT_ID` env‑var, or via `google.auth.default()`.  It lazily
creates (and re‑uses) both the publisher **and** a single pull‑subscription
(`assistant-mediator`) so every Mediator request can filter messages without
creating a new subscription per request.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import google.auth
from google.cloud import pubsub_v1

# ────────────────────────────────────────────────────────────────────
#  Project & Topic resolution
# ────────────────────────────────────────────────────────────────────
PROJECT_ID = (
    os.getenv("GOOGLE_CLOUD_PROJECT")
    or os.getenv("PROJECT_ID")
    or os.getenv("GCP_PROJECT")
)
if not PROJECT_ID:
    # Falls back to ADC (useful in local dev with `gcloud auth application-default login`)
    _, PROJECT_ID = google.auth.default()

TOPIC_ID = os.getenv("PUBSUB_TOPIC", "assistant-events")

# ────────────────────────────────────────────────────────────────────
#  Publisher – shared singleton
# ────────────────────────────────────────────────────────────────────
_publisher = pubsub_v1.PublisherClient()

async def publish(message: dict[str, Any], *, ordering_key: str | None = None) -> None:
    """Asynchronously publish *message* to the shared topic.

    Uses `loop.run_in_executor` so that the blocking `.result()` call does not
    stall FastAPI's event loop.
    """

    topic_path = _publisher.topic_path(PROJECT_ID, TOPIC_ID)
    data = json.dumps(message, separators=(",", ":")).encode("utf-8")

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: _publisher.publish(
            topic_path, data=data, ordering_key=ordering_key or ""
        ).result(),
    )

# ────────────────────────────────────────────────────────────────────
#  Subscriber helpers (lightweight – no streaming pulls)
# ────────────────────────────────────────────────────────────────────
_subscriber = pubsub_v1.SubscriberClient()
_TOPIC_PATH = _publisher.topic_path(PROJECT_ID, TOPIC_ID)
_SUB_ID = os.getenv("MEDIATOR_SUB", "assistant-mediator")  # one shared pull sub
_SUB_PATH = _subscriber.subscription_path(PROJECT_ID, _SUB_ID)

@asynccontextmanager
async def _pull(max_messages: int = 20, timeout: float = 1.0):
    """Async context manager that pulls up to *max_messages* within *timeout*.

    Yields the list of `ReceivedMessage` objects, and *always* ACKs them (success
    or error) on exit so they don't redeliver.
    """
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        None,
        lambda: _subscriber.pull(
            request={
                "subscription": _SUB_PATH,
                "max_messages": max_messages,
                "return_immediately": False,
            },
            timeout=timeout,
        ),
    )
    try:
        yield response.received_messages
    finally:
        ack_ids = [m.ack_id for m in response.received_messages]
        if ack_ids:
            _subscriber.acknowledge(request={"subscription": _SUB_PATH, "ack_ids": ack_ids})

async def subscribe_once(
    correlation_id: str,
    *,
    timeout: float = 0.4,
) -> AsyncGenerator[dict[str, Any], None]:
    """Yield Pub/Sub messages whose JSON body `id` matches *correlation_id*.

    Stops silently when *timeout* seconds have elapsed.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        # Pull attempts block for `remaining` seconds at most.
        async with _pull(max_messages=20, timeout=max(0.05, remaining)) as msgs:
            for msg in msgs:
                try:
                    data = json.loads(msg.message.data.decode("utf-8"))
                except Exception:
                    continue  # skip malformed JSON
                if data.get("id") == correlation_id:
                    yield data
        # tiny sleep to avoid tight loop when no messages present
        await asyncio.sleep(0.05)

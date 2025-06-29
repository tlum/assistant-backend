"""
Thin Pub/Sub helper used by the dispatcher service.

Usage:
    await bus.publish({"type": "TEST", "msg": "ping"})
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from google.cloud import pubsub_v1

# ── Config driven by env vars so it works in Cloud Run and locally ──
PROJECT_ID = os.getenv("GCP_PROJECT") or os.getenv("PROJECT_ID")
TOPIC_ID = os.getenv("PUBSUB_TOPIC", "assistant-events")

_publisher = pubsub_v1.PublisherClient()
_TOPIC_PATH = _publisher.topic_path(PROJECT_ID, TOPIC_ID)


async def publish(message: dict[str, Any], *, ordering_key: str | None = None) -> None:
    """
    Fire-and-forget publish that still plays nicely with `async` FastAPI
    by off-loading the blocking `.result()` call to a thread pool.
    """
    data = json.dumps(message, separators=(",", ":")).encode("utf-8")

    # Pub/Sub Future.result() is blocking ⇒ run it in the default executor
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: _publisher.publish(
            _TOPIC_PATH, data=data, ordering_key=ordering_key or ""
        ).result()
    )

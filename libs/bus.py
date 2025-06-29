# libs/bus.py
"""
Thin Pub/Sub helper used by the dispatcher service.

Usage:
    await publish({"type": "TEST", "msg": "ping"})
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import google.auth
from google.cloud import pubsub_v1

# ────────────────────────────────────────────────────────────────────
# Resolve project ID
#   1) Cloud Run sets GOOGLE_CLOUD_PROJECT
#   2) Local dev: export PROJECT_ID=...
#   3) Fall back to google.auth.default()
# ────────────────────────────────────────────────────────────────────
PROJECT_ID = (
    os.getenv("GOOGLE_CLOUD_PROJECT")
    or os.getenv("PROJECT_ID")
    or os.getenv("GCP_PROJECT")
)
if not PROJECT_ID:
    _, PROJECT_ID = google.auth.default()

TOPIC_ID = os.getenv("PUBSUB_TOPIC", "assistant-events")

_publisher = pubsub_v1.PublisherClient()


async def publish(message: dict[str, Any], *, ordering_key: str | None = None) -> None:
    """
    Fire-and-forget publish that plays nicely with FastAPI's async loop by
    off-loading the blocking Future.result() to a thread pool executor.
    """
    if not PROJECT_ID:
        raise RuntimeError(
            "Pub/Sub publish requires a GCP project ID. "
            "Set GOOGLE_CLOUD_PROJECT or PROJECT_ID."
        )

    topic_path = _publisher.topic_path(PROJECT_ID, TOPIC_ID)
    data = json.dumps(message, separators=(",", ":")).encode("utf-8")

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: _publisher.publish(
            topic_path, data=data, ordering_key=ordering_key or ""
        ).result(),
    )


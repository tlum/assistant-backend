# ────────────────────────────────────────────────────────────────────
# Subscribe helpers (very lightweight)
# ────────────────────────────────────────────────────────────────────
import time
from contextlib import asynccontextmanager

_subscriber = pubsub_v1.SubscriberClient()
_SUB_ID = os.getenv("MEDIATOR_SUB", "assistant-mediator")  # one shared pull sub
_SUB_PATH = _subscriber.subscription_path(PROJECT_ID, _SUB_ID)
_TOPIC_PATH = _publisher.topic_path(PROJECT_ID, TOPIC_ID)

# ensure the pull subscription exists exactly once
def _ensure_subscription() -> None:
    try:
        _subscriber.get_subscription(request={"subscription": _SUB_PATH})
    except Exception:
        _subscriber.create_subscription(
            request={"name": _SUB_PATH, "topic": _TOPIC_PATH, "ack_deadline_seconds": 30}
        )

_ensure_subscription()

@asynccontextmanager
async def _pull(max_messages: int = 10, timeout: float = 1.0):
    """
    Async context manager that yields a list of Pub/Sub ReceivedMessage objects.
    Uses executor.run_in_executor so we don't block FastAPI's event loop.
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
        # ACK everything we grabbed so it doesn't re-deliver
        ack_ids = [m.ack_id for m in response.received_messages]
        if ack_ids:
            _subscriber.acknowledge(
                request={"subscription": _SUB_PATH, "ack_ids": ack_ids}
            )

async def subscribe_once(correlation_id: str, *, timeout: float = 0.4):
    """
    Async generator: yields JSON-decoded dicts whose `"id"` matches `correlation_id`.
    Returns as soon as `timeout` elapses (no error thrown).
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        async with _pull(max_messages=20, timeout=remaining) as msgs:
            for m in msgs:
                try:
                    data = json.loads(m.message.data.decode("utf-8"))
                except Exception:
                    continue
                if data.get("id") == correlation_id:
                    yield data
        # tiny sleep to avoid tight loop when no messages
        await asyncio.sleep(0.05)


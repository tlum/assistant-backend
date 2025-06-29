"""
Tiny Firestore wrapper for the early prototype.

Example:
    # read
    plan = await state.get_doc("plan_state", "current")
    # write / merge
    await state.set_doc("plan_state", "current", {"status": "INIT"})
"""

from __future__ import annotations

import os
from typing import Any

from google.cloud import firestore_async

PROJECT_ID = os.getenv("GCP_PROJECT") or os.getenv("PROJECT_ID")

_db = firestore_async.Client(project=PROJECT_ID)


async def get_doc(collection: str, doc_id: str) -> dict[str, Any] | None:
    doc_ref = _db.collection(collection).document(doc_id)
    snap = await doc_ref.get()
    return snap.to_dict() if snap.exists else None


async def set_doc(
    collection: str, doc_id: str, data: dict[str, Any], *, merge: bool = True
) -> None:
    doc_ref = _db.collection(collection).document(doc_id)
    await doc_ref.set(data, merge=merge)

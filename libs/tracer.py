# libs/tracer.py
import time, uuid, logging, json
from google.cloud import firestore

_db = firestore.Client()
_log = logging.getLogger("trace")
_log.setLevel(logging.INFO)

def new_id() -> str:
    return uuid.uuid4().hex

def write(kind: str, trace_id: str, **doc):
    """Store one JSON doc in Firestore and emit the same to Cloud Logging."""
    payload = {"trace_id": trace_id, "ts": int(time.time()*1000), **doc}
    _db.collection(kind).add(payload)
    _log.info(json.dumps({"kind": kind, **payload}, default=str))


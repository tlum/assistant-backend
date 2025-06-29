# apps/dispatcher/main.py
from fastapi import FastAPI
from libs.bus import publish  # adjust import to match your helper

app = FastAPI()

@app.post("/dispatch")
async def dispatch(event: dict):
    await publish(event)       # or await bus.publish(event)
    return {"status": "ok"}

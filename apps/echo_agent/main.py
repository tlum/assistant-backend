# apps/echo_agent/main.py
from fastapi import FastAPI
import logging

app = FastAPI()
logger = logging.getLogger("echo-agent")

@app.post("/event")
async def handle(event: dict):
    logger.info("Received %s", event)
    return {"ack": True}

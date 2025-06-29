@app.post("/event")
async def handle(event: dict):
    logger.info("Received %s", json.dumps(event))
    return {"ack": True}

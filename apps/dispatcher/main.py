@app.post("/dispatch")
async def dispatch(event: dict):
    await bus.publish(event)
    return {"status": "ok"}

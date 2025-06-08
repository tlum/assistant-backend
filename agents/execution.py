# agents/execution.py

import os
from agents.base import Agent, AgentResponse, Event
from openai import OpenAI

SYSTEM_PROMPT = (
    "You are the ExecutionAgent: you interpret user requests to move the current plan forward."
)

class ExecutionAgent(Agent):
    name = "ExecutionAgent"
    client = OpenAI()  # picks up OPENAI_API_KEY

    def can_handle(self, event: Event) -> bool:
        return event.type == "user_input"

    async def handle(self, event: Event) -> AgentResponse:
        user_text = event.payload["text"]
        resp = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role":"system", "content": SYSTEM_PROMPT},
                {"role":"user",   "content": user_text}
            ]
        )
        content = resp.choices[0].message.content
        return AgentResponse(self.name, content)


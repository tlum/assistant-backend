# agents/planner.py

from agents.base import Agent, AgentResponse, Event
from openai import OpenAI

SYSTEM_PROMPT = (
    "You are the PlannerAgent: maintain and update a generic plan graph given user inputs."
)

class PlannerAgent(Agent):
    name = "PlannerAgent"
    client = OpenAI()

    def can_handle(self, event: Event) -> bool:
        # you could look for keywords or a flag in payload
        return event.type == "user_input" and "plan" in event.payload["text"].lower()

    async def handle(self, event: Event) -> AgentResponse:
        resp = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role":"system","content":SYSTEM_PROMPT},
                {"role":"user",  "content":event.payload["text"]}
            ]
        )
        return AgentResponse(self.name, resp.choices[0].message.content)


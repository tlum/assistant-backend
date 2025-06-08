# agents/mediator.py

from agents.base import Agent, AgentResponse, Event

class MediatorAgent(Agent):
    name = "MediatorAgent"

    def can_handle(self, event: Event) -> bool:
        # always available to merge at the end
        return event.type == "user_input"

    async def handle(self, event: Event) -> AgentResponse:
        # In a real system you'd merge or choose between other agents' outputs.
        # Here we'll send a placeholder if nothing else did.
        return AgentResponse(self.name, "How can I help with that?")  


# agents/base.py

from typing import Any, Dict, List
import inspect, asyncio

class Event:
    def __init__(self, session_id: str, type: str, payload: Dict[str,Any]):
        self.session_id = session_id
        self.type = type
        self.payload = payload

class AgentResponse:
    def __init__(self, agent_name: str, content: str):
        self.agent_name = agent_name
        self.content = content

class Agent:
    name: str  # override in subclass

    def can_handle(self, event: Event) -> bool:
        """Return True if this agent should see the event."""
        raise NotImplementedError

    async def handle(self, event: Event) -> AgentResponse:
        """Process the event and return an AgentResponse (or None)."""
        raise NotImplementedError

class AgentRegistry:
    def __init__(self, agents: List[Agent]):
        self.agents = agents

    async def handle(self, event: Event) -> List[AgentResponse]:
        tasks = []
        for agent in self.agents:
            if agent.can_handle(event):
                # schedule each agent concurrently
                tasks.append(agent.handle(event))
        # wait for all and filter out None
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return [r for r in results if isinstance(r, AgentResponse)]


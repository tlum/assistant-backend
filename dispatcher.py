# dispatcher.py

import asyncio
from agents.base import Event, AgentResponse, AgentRegistry
from agents.execution import ExecutionAgent
from agents.planner import PlannerAgent
from agents.mediator import MediatorAgent

# 1) register your agents in priority order
registry = AgentRegistry([
    ExecutionAgent(),
    PlannerAgent(),
    # …add your other agents here…
    MediatorAgent(),          # mediator last so it can merge others
])

async def dispatch_input(session_id: str, user_input: str, channel: str) -> str:
    # wrap the user utterance in an Event
    evt = Event(
        session_id=session_id,
        type="user_input",
        payload={"text": user_input, "channel": channel}
    )

    # fan out to all agents that 'can_handle'
    responses = await registry.handle(evt)

    # pick the Mediator’s reply if present
    for resp in responses:
        if resp.agent_name == "MediatorAgent":
            return resp.content

    # otherwise fall back to the first agent response
    return responses[0].content if responses else ""


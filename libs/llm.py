# libs/llm.py
#
# Small helper so every agent can make a single chat-completion call
# without repeating boilerplate.  Switch the model_name or base_url
# any time you like.

from langchain_openai import ChatOpenAI

_llm = ChatOpenAI(
    model_name="gpt-3.5-turbo",
    temperature=0.3,
    # If you’ll host your own model gateway later, add:
    # base_url="https://my-gateway/v1",
)

async def chat(prompt: str) -> str:
    """Return one assistant message for the given prompt."""
    resp = await _llm.ainvoke(prompt)
    return resp.content.strip()


# Optional helper used by echo-agent’s first demo
async def get_thought(user_msg: str) -> str:
    prompt = (
        f"As a helpful assistant, reply with one short 'thought' about: "
        f"{user_msg!r}"
    )
    return await chat(prompt)


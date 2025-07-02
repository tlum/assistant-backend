# libs/llm.py
#
# Thin, dependency-free wrapper around the official OpenAI async client.
# • One place to set your default production model
# • Supports streaming and future function-calling
# • Returns the raw OpenAI response object (with .usage, .model, etc.)

from openai import AsyncOpenAI
from typing import List, Dict, Any, Optional

client = AsyncOpenAI()  # Needs OPENAI_API_KEY in env
DEFAULT_MODEL = "gpt-4.1-nano-2025-04-14"


async def chat_completion(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    temperature: float = 1.0,
    stream: bool = False,
    tools: Optional[List[Dict[str, Any]]] = None,
):
    """
    Async wrapper for openai.chat.completions.create().
    Returns the raw OpenAI response.
    """
    return await client.chat.completions.create(
        model=model or DEFAULT_MODEL,
        messages=messages,
        temperature=temperature,
        stream=stream,
        tools=tools or None,
)


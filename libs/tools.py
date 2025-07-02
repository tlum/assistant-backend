from typing import Callable, Dict, Any, List
_registry: Dict[str, Callable[..., str]] = {}

def tool(name: str, description: str = ""):
    def _wrap(fn: Callable[..., str]):
        fn.__doc__ = description or fn.__doc__ or ""
        _registry[name] = fn
        return fn
    return _wrap

def json_schema() -> List[dict]:
    return [
        {
            "name": n,
            "description": fn.__doc__,
            "parameters": {"type": "object", "properties": {}, "required": []},
        }
        for n, fn in _registry.items()
    ]

def call(name: str, arguments: Dict[str, Any]) -> str:
    if name not in _registry:
        raise ValueError(f"Tool {name} not registered")
    return _registry[name](**arguments)

@tool(
    "endCall",
    "Use this function to end the call. Only call it when explicitly instructed.",
)
def _end_call() -> str:
    return "__END_CALL__"

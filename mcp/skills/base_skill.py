from typing import Any, Awaitable, Callable, Dict, Optional


ProgressCallback = Optional[Callable[[str], Awaitable[None]]]


class BaseSkill:
    async def execute(self, context: Dict[str, Any], callback: ProgressCallback = None) -> Dict[str, Any]:
        raise NotImplementedError("Subclasses must implement execute()")


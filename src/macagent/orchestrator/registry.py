from __future__ import annotations

from macagent.domain.errors import ExecutionError
from macagent.domain.models import Action, ActionName, ActionResult
from macagent.tools.base import ActionHandler


class ActionRegistry:
    def __init__(self) -> None:
        self._handlers: dict[ActionName, ActionHandler] = {}

    def register(self, action_name: ActionName, handler: ActionHandler) -> None:
        self._handlers[action_name] = handler

    def dispatch(self, action: Action) -> ActionResult:
        handler = self._handlers.get(action.name)
        if handler is None:
            raise ExecutionError(f"No handler registered for {action.name}")
        return handler.handle(action)

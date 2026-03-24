from __future__ import annotations

from typing import Protocol

from macagent.domain.models import Action, ActionResult


class ActionHandler(Protocol):
    def handle(self, action: Action) -> ActionResult:
        ...

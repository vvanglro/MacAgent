from __future__ import annotations

from typing import Protocol

from macagent.domain.models import Action, ActionPlan


class ActionParser(Protocol):
    def parse(self, text: str) -> Action | ActionPlan:
        """Convert natural language into one action or an action plan."""

from __future__ import annotations

from typing import Protocol

from macagent.domain.models import Action


class ActionParser(Protocol):
    def parse(self, text: str) -> Action:
        """Convert natural language into an Action."""

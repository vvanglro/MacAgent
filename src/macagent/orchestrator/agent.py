from __future__ import annotations

from macagent.domain.models import ActionResult
from macagent.nlu.parser import ActionParser
from macagent.orchestrator.guardrails import validate_action
from macagent.orchestrator.registry import ActionRegistry


class MacAgent:
    def __init__(self, parser: ActionParser, registry: ActionRegistry, require_confirmation: bool = True) -> None:
        self.parser = parser
        self.registry = registry
        self.require_confirmation = require_confirmation

    def run(self, text: str, auto_confirm: bool = False) -> ActionResult:
        action = self.parser.parse(text)
        validate_action(action)

        should_confirm = self.require_confirmation and action.requires_confirmation and not auto_confirm
        if should_confirm:
            return ActionResult(
                ok=False,
                action=action.name,
                message="Action requires confirmation. Re-run with --yes to execute.",
                metadata={"requires_confirmation": True},
            )

        return self.registry.dispatch(action)

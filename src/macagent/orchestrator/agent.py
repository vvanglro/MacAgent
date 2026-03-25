from __future__ import annotations

from macagent.domain.models import Action, ActionPlan, ActionResult
from macagent.nlu.parser import ActionParser
from macagent.orchestrator.guardrails import validate_action
from macagent.orchestrator.registry import ActionRegistry


class MacAgent:
    def __init__(self, parser: ActionParser, registry: ActionRegistry, require_confirmation: bool = True) -> None:
        self.parser = parser
        self.registry = registry
        self.require_confirmation = require_confirmation

    def run(self, text: str, auto_confirm: bool = False) -> ActionResult:
        plan = self._ensure_plan(self.parser.parse(text))
        for action in plan.actions:
            validate_action(action)

        requires_confirmation = any(action.requires_confirmation for action in plan.actions)
        should_confirm = self.require_confirmation and requires_confirmation and not auto_confirm
        if should_confirm:
            return ActionResult(
                ok=False,
                action=self._confirmation_action(plan),
                message="Action requires confirmation. Re-run with --yes to execute.",
                metadata={"requires_confirmation": True, "steps": [action.name.value for action in plan.actions]},
            )

        if len(plan.actions) == 1:
            return self.registry.dispatch(plan.actions[0])

        results = [self.registry.dispatch(action) for action in plan.actions]
        return ActionResult(
            ok=all(result.ok for result in results),
            action=results[-1].action,
            message=" -> ".join(result.message for result in results),
            metadata={
                "steps": [
                    {
                        "action": result.action.value,
                        "message": result.message,
                        "ok": result.ok,
                    }
                    for result in results
                ]
            },
        )

    def _ensure_plan(self, parsed: Action | ActionPlan) -> ActionPlan:
        if isinstance(parsed, ActionPlan):
            return parsed
        return ActionPlan(actions=[parsed])

    def _confirmation_action(self, plan: ActionPlan):
        for action in plan.actions:
            if action.requires_confirmation:
                return action.name
        return plan.actions[-1].name

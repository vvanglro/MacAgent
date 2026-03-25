from __future__ import annotations

from macagent.domain.models import Action, ActionName, ActionPlan, ActionResult
from macagent.nlu.parser import ActionParser
from macagent.reporting import Reporter, emit_progress
from macagent.orchestrator.guardrails import validate_action
from macagent.orchestrator.react import ReActPlanner
from macagent.orchestrator.registry import ActionRegistry


class MacAgent:
    def __init__(
        self,
        parser: ActionParser,
        registry: ActionRegistry,
        require_confirmation: bool = True,
        reporter: Reporter | None = None,
        planner: ReActPlanner | None = None,
    ) -> None:
        self.parser = parser
        self.registry = registry
        self.require_confirmation = require_confirmation
        self.reporter = reporter
        self.planner = planner or ReActPlanner()

    def run(self, text: str, auto_confirm: bool = False) -> ActionResult:
        plan = self._ensure_plan(self.parser.parse(text))
        self._attach_read_instruction(plan, text)
        goal = self.planner.derive_goal(plan)
        preview_actions = self.planner.preview(goal)

        for action in preview_actions:
            validate_action(action)

        requires_confirmation = any(action.requires_confirmation for action in preview_actions)
        should_confirm = self.require_confirmation and requires_confirmation and not auto_confirm
        if should_confirm:
            return ActionResult(
                ok=False,
                action=self._confirmation_action(preview_actions),
                message="Action requires confirmation. Re-run with --yes to execute.",
                metadata={"requires_confirmation": True, "steps": [action.name.value for action in preview_actions]},
            )

        results: list[ActionResult] = []
        traces: list[dict[str, str]] = []
        while True:
            step = self.planner.next_step(goal, results)
            if step is None:
                return self._finalize(goal, results, traces)

            emit_progress(self.reporter, f"思考：{step.thought}")
            traces.append({"thought": step.thought, "action": step.action.name.value})
            result = self.registry.dispatch(step.action)
            results.append(result)

    def _ensure_plan(self, parsed: Action | ActionPlan) -> ActionPlan:
        if isinstance(parsed, ActionPlan):
            return parsed
        return ActionPlan(actions=[parsed])

    def _confirmation_action(self, actions: list[Action]):
        for action in actions:
            if action.requires_confirmation:
                return action.name
        return actions[-1].name

    def _attach_read_instruction(self, plan: ActionPlan, text: str) -> None:
        for action in plan.actions:
            if action.name == ActionName.WECHAT_READ_LAST_MESSAGE and "instruction" not in action.params:
                action.params["instruction"] = text

    def _finalize(self, goal: Action, results: list[ActionResult], traces: list[dict[str, str]]) -> ActionResult:
        if not results:
            raise RuntimeError("ReAct loop finished without executing any action")

        final_result = results[-1]
        metadata = dict(final_result.metadata)
        metadata["steps"] = [
            {
                "action": result.action.value,
                "message": result.message,
                "ok": result.ok,
            }
            for result in results
        ]
        metadata["react_trace"] = traces
        metadata["goal"] = goal.name.value

        return ActionResult(
            ok=all(result.ok for result in results),
            action=final_result.action,
            message=final_result.message,
            metadata=metadata,
        )

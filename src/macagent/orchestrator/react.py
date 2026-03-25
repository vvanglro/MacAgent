from __future__ import annotations

from dataclasses import dataclass

from macagent.domain.errors import ExecutionError
from macagent.domain.models import Action, ActionName, ActionPlan, ActionResult


@dataclass(frozen=True)
class ReActStep:
    thought: str
    action: Action


class ReActPlanner:
    def derive_goal(self, plan: ActionPlan) -> Action:
        prioritized_actions = [
            ActionName.WECHAT_SEND_MESSAGE,
            ActionName.WECHAT_READ_LAST_MESSAGE,
            ActionName.CHROME_SEARCH,
            ActionName.CHROME_FOCUS_ADDRESS_BAR,
            ActionName.WECHAT_OPEN,
        ]

        for action_name in prioritized_actions:
            matched = next((action for action in plan.actions if action.name == action_name), None)
            if matched is not None:
                return matched

        raise ExecutionError("No actionable goal found in plan")

    def preview(self, goal: Action) -> list[Action]:
        return [step.action for step in self._steps_for_goal(goal)]

    def next_step(self, goal: Action, completed_results: list[ActionResult]) -> ReActStep | None:
        steps = self._steps_for_goal(goal)
        if len(completed_results) >= len(steps):
            return None
        return steps[len(completed_results)]

    def _steps_for_goal(self, goal: Action) -> list[ReActStep]:
        if goal.name == ActionName.WECHAT_SEND_MESSAGE:
            contact = str(goal.params.get("contact", "")).strip()
            return [
                ReActStep(
                    thought="先确保微信已经打开并处于前台，避免后续发送失败。",
                    action=Action(name=ActionName.WECHAT_OPEN),
                ),
                ReActStep(
                    thought=f"微信已经就绪，现在把消息发送给 {contact}。",
                    action=Action(
                        name=ActionName.WECHAT_SEND_MESSAGE,
                        params=dict(goal.params),
                        requires_confirmation=goal.requires_confirmation,
                    ),
                ),
            ]

        if goal.name == ActionName.WECHAT_READ_LAST_MESSAGE:
            contact = str(goal.params.get("contact", "")).strip()
            thought = (
                f"先打开微信，再读取和 {contact} 的聊天内容。"
                if contact
                else "先打开微信，再读取当前聊天窗口内容。"
            )
            return [
                ReActStep(
                    thought=thought,
                    action=Action(name=ActionName.WECHAT_OPEN),
                ),
                ReActStep(
                    thought="微信已就绪，现在根据用户意图分析聊天截图。",
                    action=Action(name=ActionName.WECHAT_READ_LAST_MESSAGE, params=dict(goal.params)),
                ),
            ]

        if goal.name == ActionName.CHROME_SEARCH:
            query = str(goal.params.get("query", "")).strip() or "macagent"
            return [
                ReActStep(
                    thought=f"直接在 Chrome 中搜索 `{query}` 就能完成目标。",
                    action=Action(name=ActionName.CHROME_SEARCH, params=dict(goal.params)),
                )
            ]

        if goal.name == ActionName.CHROME_FOCUS_ADDRESS_BAR:
            return [
                ReActStep(
                    thought="先把 Chrome 切到前台并聚焦地址栏。",
                    action=Action(name=ActionName.CHROME_FOCUS_ADDRESS_BAR, params=dict(goal.params)),
                )
            ]

        if goal.name == ActionName.WECHAT_OPEN:
            return [
                ReActStep(
                    thought="用户只需要打开微信，直接执行即可。",
                    action=Action(name=ActionName.WECHAT_OPEN),
                )
            ]

        raise ExecutionError(f"Unsupported goal for ReAct planner: {goal.name}")

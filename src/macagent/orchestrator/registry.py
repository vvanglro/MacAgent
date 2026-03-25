from __future__ import annotations

from macagent.domain.errors import ExecutionError
from macagent.domain.models import Action, ActionName, ActionResult
from macagent.reporting import Reporter, emit_progress
from macagent.tools.base import ActionHandler


class ActionRegistry:
    def __init__(self, reporter: Reporter | None = None) -> None:
        self._handlers: dict[ActionName, ActionHandler] = {}
        self.reporter = reporter

    def register(self, action_name: ActionName, handler: ActionHandler) -> None:
        self._handlers[action_name] = handler

    def dispatch(self, action: Action) -> ActionResult:
        handler = self._handlers.get(action.name)
        if handler is None:
            raise ExecutionError(f"No handler registered for {action.name}")
        emit_progress(self.reporter, f"开始执行动作：{_action_display_name(action)}")
        return handler.handle(action)


def _action_display_name(action: Action) -> str:
    return {
        ActionName.WECHAT_OPEN: "打开微信",
        ActionName.WECHAT_READ_LAST_MESSAGE: "读取微信聊天",
        ActionName.WECHAT_SEND_MESSAGE: "发送微信消息",
        ActionName.CHROME_FOCUS_ADDRESS_BAR: "聚焦 Chrome 地址栏",
        ActionName.CHROME_SEARCH: "Chrome 搜索",
    }.get(action.name, action.name.value)

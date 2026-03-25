from __future__ import annotations

from urllib.parse import quote_plus

from macagent.domain.errors import ExecutionError
from macagent.domain.models import Action, ActionName, ActionResult
from macagent.reporting import Reporter, emit_progress
from macagent.tools.executor import CommandExecutor


class ChromeFocusAddressBarHandler:
    def __init__(self, executor: CommandExecutor, reporter: Reporter | None = None) -> None:
        self.executor = executor
        self.reporter = reporter

    def handle(self, action: Action) -> ActionResult:
        emit_progress(self.reporter, "正在激活 Chrome 并聚焦地址栏")
        script = (
            'tell application "Google Chrome" to activate\n'
            'delay 0.5\n'
            'tell application "System Events" to keystroke "l" using command down'
        )
        self.executor.run_or_raise(["osascript", "-e", script])
        return ActionResult(ok=True, action=ActionName.CHROME_FOCUS_ADDRESS_BAR, message="Chrome 地址栏已聚焦")


class ChromeSearchHandler:
    def __init__(self, executor: CommandExecutor, reporter: Reporter | None = None) -> None:
        self.executor = executor
        self.reporter = reporter

    def handle(self, action: Action) -> ActionResult:
        query = str(action.params.get("query", "")).strip()
        if not query:
            raise ExecutionError("query is required")

        emit_progress(self.reporter, f"正在打开 Chrome 搜索：{query}")
        url = f"https://www.google.com/search?q={quote_plus(query)}"
        self.executor.run_or_raise(["open", "-a", "Google Chrome", url])
        return ActionResult(ok=True, action=ActionName.CHROME_SEARCH, message=f"已在 Chrome 搜索: {query}")

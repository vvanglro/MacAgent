import pytest

from macagent.domain.errors import ExecutionError
from macagent.domain.models import Action, ActionName
from macagent.tools.chrome import ChromeSearchHandler


class FakeExecutor:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def run_or_raise(self, command: list[str], timeout: int = 20):
        self.commands.append(command)


def test_chrome_search_uses_open_command() -> None:
    executor = FakeExecutor()
    handler = ChromeSearchHandler(executor)

    handler.handle(Action(name=ActionName.CHROME_SEARCH, params={"query": "mac agent"}))

    assert executor.commands
    assert executor.commands[0][:3] == ["open", "-a", "Google Chrome"]
    assert "mac+agent" in executor.commands[0][-1]


def test_chrome_search_rejects_missing_query() -> None:
    executor = FakeExecutor()
    handler = ChromeSearchHandler(executor)

    with pytest.raises(ExecutionError):
        handler.handle(Action(name=ActionName.CHROME_SEARCH, params={}))

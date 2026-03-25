from macagent.domain.models import Action, ActionName, ActionResult
from macagent.orchestrator.registry import ActionRegistry


class DummyHandler:
    def handle(self, action: Action) -> ActionResult:
        return ActionResult(ok=True, action=action.name, message="ok")


def test_registry_dispatches_to_registered_handler() -> None:
    reg = ActionRegistry()
    reg.register(ActionName.CHROME_SEARCH, DummyHandler())

    result = reg.dispatch(Action(name=ActionName.CHROME_SEARCH, params={"query": "x"}))

    assert result.ok is True
    assert result.message == "ok"


def test_registry_emits_progress_message_before_dispatch() -> None:
    messages: list[str] = []
    reg = ActionRegistry(reporter=messages.append)
    reg.register(ActionName.CHROME_SEARCH, DummyHandler())

    reg.dispatch(Action(name=ActionName.CHROME_SEARCH, params={"query": "x"}))

    assert messages == ["开始执行动作：Chrome 搜索"]

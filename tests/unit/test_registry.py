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

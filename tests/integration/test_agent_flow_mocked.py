from macagent.domain.models import Action, ActionName, ActionResult
from macagent.orchestrator.agent import MacAgent
from macagent.orchestrator.registry import ActionRegistry


class FakeParser:
    def parse(self, text: str) -> Action:
        return Action(name=ActionName.CHROME_SEARCH, params={"query": text})


class FakeHandler:
    def handle(self, action: Action) -> ActionResult:
        return ActionResult(ok=True, action=action.name, message=f"ran {action.params['query']}")


def test_agent_full_flow_with_mocks() -> None:
    reg = ActionRegistry()
    reg.register(ActionName.CHROME_SEARCH, FakeHandler())

    agent = MacAgent(parser=FakeParser(), registry=reg)
    result = agent.run("macagent")

    assert result.ok is True
    assert result.message == "ran macagent"

from macagent.domain.models import Action, ActionName, ActionPlan, ActionResult
from macagent.orchestrator.agent import MacAgent
from macagent.orchestrator.registry import ActionRegistry


class FakeParser:
    def parse(self, text: str) -> ActionPlan:
        return ActionPlan(actions=[Action(name=ActionName.CHROME_SEARCH, params={"query": text})])


class MultiStepParser:
    def parse(self, text: str) -> ActionPlan:
        return ActionPlan(
            actions=[
                Action(name=ActionName.WECHAT_OPEN),
                Action(
                    name=ActionName.WECHAT_SEND_MESSAGE,
                    params={"contact": "hulk", "text": text},
                    requires_confirmation=True,
                ),
            ]
        )


class ReadLastMessageParser:
    def parse(self, text: str) -> ActionPlan:
        return ActionPlan(actions=[Action(name=ActionName.WECHAT_READ_LAST_MESSAGE)])


class FakeHandler:
    def handle(self, action: Action) -> ActionResult:
        return ActionResult(ok=True, action=action.name, message=f"ran {action.params['query']}")


class EchoHandler:
    def __init__(self, message: str) -> None:
        self.message = message

    def handle(self, action: Action) -> ActionResult:
        return ActionResult(ok=True, action=action.name, message=self.message)


def test_agent_full_flow_with_mocks() -> None:
    reg = ActionRegistry()
    reg.register(ActionName.CHROME_SEARCH, FakeHandler())

    agent = MacAgent(parser=FakeParser(), registry=reg)
    result = agent.run("macagent")

    assert result.ok is True
    assert result.message == "ran macagent"


def test_agent_executes_multi_step_plan_in_order() -> None:
    reg = ActionRegistry()
    reg.register(ActionName.WECHAT_OPEN, EchoHandler("微信已打开"))
    reg.register(ActionName.WECHAT_SEND_MESSAGE, EchoHandler("消息已发送给 hulk"))

    agent = MacAgent(parser=MultiStepParser(), registry=reg)
    result = agent.run("hello", auto_confirm=True)

    assert result.ok is True
    assert result.message == "微信已打开 -> 消息已发送给 hulk"
    assert result.metadata["steps"] == [
        {"action": "wechat.open", "message": "微信已打开", "ok": True},
        {"action": "wechat.send_message", "message": "消息已发送给 hulk", "ok": True},
    ]


def test_agent_requires_confirmation_before_running_multi_step_plan() -> None:
    reg = ActionRegistry()
    reg.register(ActionName.WECHAT_OPEN, EchoHandler("微信已打开"))
    reg.register(ActionName.WECHAT_SEND_MESSAGE, EchoHandler("消息已发送给 hulk"))

    agent = MacAgent(parser=MultiStepParser(), registry=reg)
    result = agent.run("hello")

    assert result.ok is False
    assert result.metadata["requires_confirmation"] is True
    assert result.metadata["steps"] == ["wechat.open", "wechat.send_message"]


def test_agent_executes_read_last_message_action() -> None:
    reg = ActionRegistry()
    reg.register(ActionName.WECHAT_READ_LAST_MESSAGE, EchoHandler("当前聊天最后一条消息: hello"))

    agent = MacAgent(parser=ReadLastMessageParser(), registry=reg)
    result = agent.run("读取当前聊天最后一条消息")

    assert result.ok is True
    assert result.message == "当前聊天最后一条消息: hello"

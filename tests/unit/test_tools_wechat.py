from macagent.domain.models import Action, ActionName
from macagent.tools.wechat import WeChatSendMessageHandler


class FakeExecutor:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def run_or_raise(self, command: list[str], timeout: int = 20):
        self.commands.append(command)


def test_wechat_handler_invokes_osascript_and_restores_clipboard() -> None:
    executor = FakeExecutor()
    handler = WeChatSendMessageHandler(executor)

    handler.handle(Action(name=ActionName.WECHAT_SEND_MESSAGE, params={"contact": "hulk", "text": "hello"}))

    assert executor.commands
    assert executor.commands[0][0] == "osascript"
    assert "savedClipboard" in executor.commands[0][2]
    assert "set the clipboard to savedClipboard" in executor.commands[0][2]

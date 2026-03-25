from __future__ import annotations

from macagent.domain.models import Action, ActionName, ActionResult
from macagent.tools.executor import CommandExecutor


class WeChatSendMessageHandler:
    def __init__(self, executor: CommandExecutor) -> None:
        self.executor = executor

    def handle(self, action: Action) -> ActionResult:
        contact = str(action.params["contact"]).strip()
        text = str(action.params["text"]).strip()

        script = (
            'set savedClipboard to the clipboard\n'
            'try\n'
            f'  set contactName to "{_escape(contact)}"\n'
            f'  set msgText to "{_escape(text)}"\n'
            '  tell application "WeChat" to activate\n'
            '  delay 1\n'
            '  tell application "System Events"\n'
            '    set the clipboard to contactName\n'
            '    keystroke "f" using command down\n'
            '    delay 0.5\n'
            '    keystroke "v" using command down\n'
            '    delay 1\n'
            '    key code 36\n'
            '    delay 1\n'
            '    set the clipboard to msgText\n'
            '    keystroke "v" using command down\n'
            '    delay 0.5\n'
            '    key code 36\n'
            '  end tell\n'
            '  set the clipboard to savedClipboard\n'
            'on error errMsg number errNum\n'
            '  set the clipboard to savedClipboard\n'
            '  error errMsg number errNum\n'
            'end try'
        )
        self.executor.run_or_raise(["osascript", "-e", script], timeout=30)
        return ActionResult(ok=True, action=ActionName.WECHAT_SEND_MESSAGE, message=f"消息已发送给 {contact}")


def _escape(value: str) -> str:
    return value.replace('\\', '\\\\').replace('"', '\\"')
